# main.py
import streamlit as st
import pandas as pd
import os
import tempfile
from datetime import datetime
import shutil

from resume_processor import extract_zip_and_process_resumes, process_resume_json_files, process_duration_column
from database import create_connection, create_table, insert_resume_data, fetch_resumes, update_resume, delete_resume, search_resumes


def main():
    st.title("Resume Processing and Management System")

    # Sidebar for navigation
    menu = ["Upload Resumes", "View Resumes", "Search Resumes"]
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "Upload Resumes":
        upload_resumes()
    elif choice == "View Resumes":
        view_resumes()
    elif choice == "Search Resumes":
        search_resume_page()

def upload_resumes():
    st.subheader("Upload Resume Zip File")
    
    uploaded_file = st.file_uploader("Choose a ZIP file", type=["zip"])
    
    if uploaded_file is not None:
        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save uploaded file
            zip_path = os.path.join(temp_dir, "uploaded_resumes.zip")
            with open(zip_path, "wb") as f:
                f.write(uploaded_file.getvalue())
            
            # Process folder paths
            output_folder = os.path.join(temp_dir, "processed_resumes")
            
            with st.spinner('Processing Resumes...'):
                # Extract and process resumes
                processed_files = extract_zip_and_process_resumes(zip_path, output_folder)
                
                # Clean JSON files (remove first and last lines)
                from resume_processor import clean_json_files
                clean_json_files(output_folder)
                
                # Process resume JSON files
                df, errors = process_resume_json_files(output_folder)
                
                # Process duration
                df = process_duration_column(df)
                
                # Select columns of interest
                df = df[['Name', 'Mobile', 'Email', 'Graduation', 'Company', 'Role', 'Calculated_Duration']]
                # Flatten mobile numbers if they're lists
                def flatten_mobile(mobile):
                    if isinstance(mobile, list):
                        # Join list elements, remove any non-numeric characters
                        return ''.join(filter(str.isdigit, str(mobile[0]))) if mobile else None
                    elif isinstance(mobile, str):
                        # Remove any non-numeric characters from string
                        return ''.join(filter(str.isdigit, mobile))
                    return mobile

                # Clean Mobile column
                df['Mobile'] = df['Mobile'].apply(flatten_mobile)

                # Remove any rows with empty Mobile numbers
                df = df.dropna(subset=['Mobile'])

                # Now group by
                #overall_exp = df.groupby(['Mobile'])['Calculated_Duration'].sum().reset_index()
                
                # Calculate total experience
                overall_exp = df.groupby(['Mobile'])['Calculated_Duration'].sum().reset_index()
                overall_exp.rename(columns={'Calculated_Duration': 'Total_Experience'}, inplace=True)
                df = df.merge(overall_exp, on='Mobile')
            
            # Create tabs for different views
            tab1, tab2, tab3 = st.tabs(["Detailed View", "Grouped View", "Summary Statistics"])
            
            with tab1:
                st.subheader("Detailed Resume Data")
                st.dataframe(df, use_container_width=True, height=600)
            
            with tab2:
                st.subheader("Grouped Resume Data")
                # Grouping options
                grouping_columns = st.multiselect(
                    "Select Columns to Group By", 
                    ['Name', 'Mobile', 'Email', 'Graduation', 'Company', 'Role'],
                    default=['Name', 'Mobile', 'Graduation']
                )

                # Ensure all grouping columns exist in the DataFrame
                valid_columns = [col for col in grouping_columns if col in df.columns]

                # Aggregation options
                agg_columns = {
                    'Company': 'first',
                    'Role': 'first',
                    'Calculated_Duration': 'sum',
                    'Total_Experience': 'first',
                    'Email': 'first'
                }

                # Perform grouping
                grouped_df = df.groupby(valid_columns).agg(agg_columns).reset_index()
                
                st.dataframe(grouped_df, use_container_width=True, height=600)
            
            with tab3:
                st.subheader("Summary Statistics")
                
                # Total candidates
                st.metric("Total Candidates", len(df['Name'].unique()))
                
                # Experience distribution
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Experience Distribution")
                    experience_dist = df.groupby('Total_Experience')['Name'].count()
                    st.bar_chart(experience_dist)
                
                with col2:
                    st.subheader("Top Companies")
                    top_companies = df['Company'].value_counts().head(5)
                    st.bar_chart(top_companies)
                
                # Graduation distribution
                st.subheader("Graduation Distribution")
                graduation_dist = df['Graduation'].value_counts()
                st.bar_chart(graduation_dist)
            
            # Option to save to SQLite
            if st.button("Save to Database"):
                # Establish DB connection and create table
                conn = create_connection("resumes.db")
                create_table(conn)
                
                # Insert data to database
                for _, row in df.iterrows():
                    insert_resume_data(conn, row)
                
                # Delete the temporary extract directory
                temp_extract_dir = os.path.join(output_folder, 'temp_pdfs')
                if os.path.exists(temp_extract_dir):
                    shutil.rmtree(temp_extract_dir)
                
                st.success("Resumes saved to database successfully!")
                
                # Close connection
                conn.close()

# ... (rest of the script remains the same)
def view_resumes():
    st.subheader("Resume Database")
    
    # Establish DB connection
    conn = create_connection("resumes.db")
    
    # Fetch resumes
    df = fetch_resumes(conn)
    df['Mobile'] = df['Mobile'].astype(str)
    
    # Display dataframe with editing capabilities
    edited_df = st.data_editor(df, 
                               num_rows="dynamic", 
                               column_config={
                                   "Mobile": st.column_config.TextColumn(disabled=True)
                               })
    
    # Handle updates
    if st.button("Save Changes"):
        for _, row in edited_df.iterrows():
            update_resume(conn, row)
        st.success("Changes saved successfully!")
    
    # Add delete functionality
    delete_mobile = st.text_input("Enter Mobile Number to Delete")
    if st.button("Delete Resume"):
        if delete_mobile:
            delete_resume(conn, delete_mobile)
            st.success(f"Resume for {delete_mobile} deleted!")
    
    conn.close()

def search_resume_page():
    st.subheader("Search Resumes")
    
    # Establish DB connection
    conn = create_connection("resumes.db")
    
    # Search fields
    search_name = st.text_input("Search by Name")
    search_company = st.text_input("Search by Company")
    search_graduation = st.text_input("Search by Graduation")
    
    # Perform search
    if st.button("Search"):
        results = search_resumes(conn, 
                                 name=search_name, 
                                 company=search_company, 
                                 graduation=search_graduation)
        
        if not results.empty:
            st.dataframe(results)
        else:
            st.warning("No results found.")
    conn.close()

if __name__ == "__main__":
    main()
