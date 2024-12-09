# resume_processor.py
import os
import shutil
import tempfile
import zipfile
import sqlite3
import io
import json
import traceback
from typing import List, Dict
from llama_parse import LlamaParse
import pandas as pd
from pathlib import Path
from datetime import datetime
import re

# Set API key (Consider using environment variables in production)
os.environ["LLAMA_CLOUD_API_KEY"] = "llx-svCPu1UniVECsxWEeQINhixGgBZgSHjr4OcIp0o1VX57JMsm"

def extract_zip_and_process_resumes(zip_file_path: str, output_folder: str):
    """
    Process multiple PDF resumes from a zip file using LlamaParse.
    """
    os.makedirs(output_folder, exist_ok=True)

    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        temp_extract_dir = os.path.join(output_folder, 'temp_pdfs')
        os.makedirs(temp_extract_dir, exist_ok=True)
        zip_ref.extractall(temp_extract_dir)

    processed_files: List[str] = []
    for filename in os.listdir(temp_extract_dir):
        if filename.lower().endswith('.pdf'):
            pdf_path = os.path.join(temp_extract_dir, filename)

            try:
                documents_with_instruction = LlamaParse(
                    result_type="markdown",
                    parsing_instruction="""
                    Carefully extract structured resume information in json format:
                    - Extract Name, Mobile, and Email accurately.
                    - Identify all work experiences, including Company, Role, and Duration.
                    - Extract educational qualifications.
                    Desired Output Format:
                    - Name: Full Name
                    - Mobile: Contact Number
                    - Email: Email Address
                    - Graduation: Degree, Institution
                    - Work Experiences: Multiple entries possible
                      * Company Name
                      * Role/Position
                      * Duration of Employment
                    """
                ).load_data(pdf_path)

                base_filename = os.path.splitext(filename)[0]
                output_md_path = os.path.join(output_folder, f"{base_filename}_resume.json")

                with open(output_md_path, 'w', encoding='utf-8') as f:
                    f.write(documents_with_instruction[0].text)

                processed_files.append(output_md_path)
                print(f"Processed: {filename} -> {output_md_path}")

            except Exception as e:
                print(f"Error processing {filename}: {e}")

    shutil.rmtree(temp_extract_dir)
    return processed_files

def clean_json_files(folder_path):
    """
    Removes the first and last lines from JSON files in the specified folder.
    """
    for filename in os.listdir(folder_path):
        if filename.endswith(".json"):
            file_path = os.path.join(folder_path, filename)

            with open(file_path, 'r') as file:
                lines = file.readlines()

            if len(lines) > 2:
                cleaned_lines = lines[1:-1]
                with open(file_path, 'w') as file:
                    file.writelines(cleaned_lines)
            else:
                print(f"Skipping {filename}: not enough lines to process.")

def process_resume_json_files(folder_path):
    """
    Process all JSON resume files in a given folder with robust error handling.
    """
    all_resumes = []
    error_log = []

    for filename in os.listdir(folder_path):
        if filename.lower().endswith(('.json', '.jsonl')):
            file_path = os.path.join(folder_path, filename)

            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    file_content = file.read().strip()

                if not file_content:
                    error_log.append({
                        'filename': filename,
                        'error_type': 'Empty File',
                        'error_message': 'JSON file is empty'
                    })
                    continue

                resume_data = json.loads(file_content)

                if not isinstance(resume_data, dict):
                    error_log.append({
                        'filename': filename,
                        'error_type': 'Invalid JSON',
                        'error_message': 'JSON does not represent a dictionary'
                    })
                    continue

                graduation_info = resume_data.get('Graduation', {}) or {}
                graduation_degree = graduation_info.get('Degree', '') if isinstance(graduation_info, dict) else ''
                graduation_institution = graduation_info.get('Institution', '') if isinstance(graduation_info, dict) else ''
                graduation_str = f"{graduation_degree} - {graduation_institution}".strip(' -')

                if resume_data.get('Work Experiences'):
                    for experience in resume_data['Work Experiences']:
                        resume_row = {
                            'Name': resume_data.get('Name', ''),
                            'Mobile': resume_data.get('Mobile', ''),
                            'Email': resume_data.get('Email', ''),
                            'Graduation': graduation_str,
                            'Company': experience.get('Company', ''),
                            'Role': experience.get('Role', ''),
                            'Duration': experience.get('Duration', '')
                        }
                        all_resumes.append(resume_row)
                else:
                    resume_row = {
                        'Name': resume_data.get('Name', ''),
                        'Mobile': resume_data.get('Mobile', ''),
                        'Email': resume_data.get('Email', ''),
                        'Graduation': graduation_str,
                        'Company': '',
                        'Role': '',
                        'Duration': ''
                    }
                    all_resumes.append(resume_row)

            except json.JSONDecodeError as e:
                error_details = {
                    'filename': filename,
                    'error_type': 'JSON Decode Error',
                    'error_message': str(e),
                    'full_traceback': traceback.format_exc()
                }
                error_log.append(error_details)
                print(f"JSON Decode Error in {filename}: {e}")

            except Exception as e:
                error_details = {
                    'filename': filename,
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'full_traceback': traceback.format_exc()
                }
                error_log.append(error_details)
                print(f"Error processing file {filename}: {e}")

    df = pd.DataFrame(all_resumes)

    if error_log:
        print("\n--- Error Log ---")
        for error in error_log:
            print(f"Filename: {error['filename']}")
            print(f"Error Type: {error.get('error_type', 'Unknown')}")
            print(f"Error Message: {error.get('error_message', 'No details')}")
            if 'full_traceback' in error:
                print("Full Traceback:")
                print(error['full_traceback'])
            print("---")

    return df, error_log

def process_duration_column(df):
    """
    Process the Duration column to extract dates and calculate duration.
    """
    def parse_date(date_str):
        if pd.isna(date_str) or date_str == '':
            return None

        date_str = str(date_str).strip().lower()

        if date_str in ['present', 'running', 'current']:
            return datetime.now()

        date_formats = [
            '%b %Y', '%B %Y', '%Y-%m', '%m-%Y', '%b. %Y', '%B. %Y',
            '%d %b %Y', '%d %B %Y', '%b %d, %Y', '%B %d, %Y', 
            '%Y', '%m/%Y', '%Y/%m',
        ]

        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        months = {
            'jan': 1, 'january': 1, 'feb': 2, 'february': 2,
            'mar': 3, 'march': 3, 'apr': 4, 'april': 4,
            'may': 5, 'jun': 6, 'june': 6, 'jul': 7, 'july': 7,
            'aug': 8, 'august': 8, 'sep': 9, 'september': 9,
            'oct': 10, 'october': 10, 'nov': 11, 'november': 11,
            'dec': 12, 'december': 12
        }

        match = re.search(r'(\w+)\s*(\d{4})', date_str, re.IGNORECASE)
        if match:
            month_str, year = match.groups()
            month_num = months.get(month_str.lower()[:3], 1)
            try:
                return datetime(int(year), month_num, 1)
            except ValueError:
                pass

        return None

    def calculate_duration_in_months(start, end):
        if start is None:
            return 0

        if end is None:
            end = datetime.now()

        months = (end.year - start.year) * 12 + (end.month - start.month)
        return months

    df['Start_Date'] = df['Duration'].apply(
        lambda x: parse_date(x.split('–')[0].strip() if '–' in str(x) else 
                  x.split('-')[0].strip() if '-' in str(x) else x)
    )
    df['End_Date'] = df['Duration'].apply(
        lambda x: parse_date(x.split('–')[-1].strip() if '–' in str(x) else 
                  x.split('-')[-1].strip() if '-' in str(x) else None)
    )

    df['Calculated_Duration'] = df.apply(
        lambda row: calculate_duration_in_months(row['Start_Date'], row['End_Date']), 
        axis=1
    )
    df.loc[df['Calculated_Duration'].isna(), 'Calculated_Duration'] = 0

    return df
