# database.py
import sqlite3
import pandas as pd
from datetime import datetime

def create_connection(db_file):
    """
    Create a database connection to the SQLite database
    
    Parameters:
    db_file (str): Path to the database file
    
    Returns:
    sqlite3.Connection: Database connection object
    """
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return None

def create_table(conn):
    """
    Create resumes table if it doesn't exist
    
    Parameters:
    conn (sqlite3.Connection): Database connection object
    """
    try:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS resumes (
                name TEXT,
                mobile TEXT PRIMARY KEY,
                email TEXT,
                graduation TEXT,
                company TEXT,
                role TEXT,
                calculated_duration INTEGER,
                total_experience INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error creating table: {e}")

# def insert_resume_data(conn, row):
#     """
#     Insert or replace resume data into the database
    
#     Parameters:
#     conn (sqlite3.Connection): Database connection object
#     row (pandas.Series): Row of resume data
#     """
#     try:
#         cursor = conn.cursor()
#         cursor.execute('''
#             INSERT OR REPLACE INTO resumes 
#             (name, mobile, email, graduation, company, role, calculated_duration, total_experience)
#             VALUES (?, ?, ?, ?, ?, ?, ?, ?)
#         ''', (
#             row['Name'], 
#             row['Mobile'], 
#             row['Email'], 
#             row['Graduation'], 
#             row['Company'], 
#             row['Role'], 
#             row['Calculated_Duration'], 
#             row['Total_Experience']
#         ))
#         conn.commit()
#     except sqlite3.Error as e:
#         print(f"Error inserting data: {e}")

def insert_resume_data(conn, row):
    """
    Insert or replace resume data into the database only if no matching record exists 
    with a timestamp less than the current date
    
    Parameters:
    conn (sqlite3.Connection): Database connection object
    row (pandas.Series): Row of resume data
    """
    try:
        cursor = conn.cursor()
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # Check if a matching record already exists
        cursor.execute('''
            SELECT COUNT(*) 
            FROM resumes 
            WHERE mobile = ? AND created_at < ?
        ''', (row['Mobile'], current_date))
        
        existing_count = cursor.fetchone()[0]
        
        # Only insert if no matching record exists
        if existing_count == 0:
            cursor.execute('''
                INSERT INTO resumes 
                (name, mobile, email, graduation, company, role, calculated_duration, total_experience, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                row['Name'], 
                row['Mobile'], 
                row['Email'], 
                row['Graduation'], 
                row['Company'], 
                row['Role'], 
                row['Calculated_Duration'], 
                row['Total_Experience'],
                current_date
            ))
            conn.commit()
            return True
        else:
            print(f"Skipping insertion for mobile {row['Mobile']} - matching record exists")
            return False
    
    except sqlite3.Error as e:
        print(f"Error processing data: {e}")
        return False

def fetch_resumes(conn):
    """
    Fetch all resumes from the database
    
    Parameters:
    conn (sqlite3.Connection): Database connection object
    
    Returns:
    pandas.DataFrame: DataFrame with resume data
    """
    try:
        query = "SELECT * FROM resumes"
        return pd.read_sql_query(query, conn)
    except sqlite3.Error as e:
        print(f"Error fetching resumes: {e}")
        return pd.DataFrame()

def update_resume(conn, row):
    """
    Update an existing resume in the database
    
    Parameters:
    conn (sqlite3.Connection): Database connection object
    row (pandas.Series): Updated resume data
    """
    try:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE resumes 
            SET name = ?, email = ?, graduation = ?, company = ?, role = ?, 
                calculated_duration = ?, total_experience = ?
            WHERE mobile = ?
        ''', (
            row['Name'], 
            row['Email'], 
            row['Graduation'], 
            row['Company'], 
            row['Role'], 
            row['Calculated_Duration'], 
            row['Total_Experience'],
            row['Mobile'],
            row['created_at']
        ))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error updating resume: {e}")

def delete_resume(conn, mobile):
    """
    Delete a resume from the database by mobile number
    
    Parameters:
    conn (sqlite3.Connection): Database connection object
    mobile (str): Mobile number of the resume to delete
    """
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM resumes WHERE mobile = ?', (mobile,))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error deleting resume: {e}")

def search_resumes(conn, name='', company='', graduation='', created_at=''):
    """
    Search resumes based on name, company, or graduation
    
    Parameters:
    conn (sqlite3.Connection): Database connection object
    name (str): Name to search for
    company (str): Company to search for
    graduation (str): Graduation to search for
    
    Returns:
    pandas.DataFrame: DataFrame with matching resume data
    """
    try:
        query = "SELECT * FROM resumes WHERE 1=1"
        params = []
        
        if name:
            query += " AND name LIKE ?"
            params.append(f"%{name}%")
        
        if company:
            query += " AND company LIKE ?"
            params.append(f"%{company}%")
        
        if graduation:
            query += " AND graduation LIKE ?"
            params.append(f"%{graduation}%")
        
        if created_at:
            query += " AND created_at >= ?"
            params.append(created_at)
        
        return pd.read_sql_query(query, conn, params=params)
    except sqlite3.Error as e:
        print(f"Error searching resumes: {e}")
        return pd.DataFrame()
