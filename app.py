"""
Logic:
- Connect to Google Sheet and authenticate with rate limiting
- Provide CRUD operations for todo items with scoring (10, 7, 5, 1)
- Display todo list with add/edit/delete functionality and colored score selection
- Cache data for performance
- Handle API quota limits with simple retries
"""

import streamlit as st
from google.oauth2 import service_account
import pandas as pd
from datetime import datetime
import uuid
import time
import random
import gspread
from functools import wraps

# Create a connection object and authenticate
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["connections"]["gsheets"],
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
    ],
)

# Score options with colors
SCORE_OPTIONS = {
    10: "🔴 High Priority (10)",
    7: "🟡 Medium-High (7)",
    5: "🟢 Medium (5)",
    1: "⚪ Low (1)"
}

def retry_with_backoff(retries=3, backoff_in_seconds=1):
    """
    Input: number of retries and backoff time
    Process: Retries function with exponential backoff
    Output: Decorated function with retry logic
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            x = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if x == retries:
                        raise e
                    sleep_time = (backoff_in_seconds * 2 ** x) + (random.random() * 0.1)
                    time.sleep(sleep_time)
                    x += 1
        return wrapper
    return decorator

@retry_with_backoff(retries=3)
def get_sheet():
    """
    Input: None
    Process: Creates connection to Google Sheet with retry logic
    Output: Returns worksheet object
    """
    gc = gspread.authorize(credentials)
    sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    sh = gc.open_by_url(sheet_url)
    worksheet = sh.get_worksheet(0)
    return worksheet

@retry_with_backoff(retries=3)
def initialize_sheet(worksheet):
    """
    Input: worksheet object
    Process: Initializes sheet with headers if needed
    Output: None
    """
    try:
        headers = ['id', 'task', 'status', 'score', 'created_at', 'updated_at']
        
        # Get current headers
        current_headers = worksheet.row_values(1) if worksheet.row_count > 0 else []
        
        # Clear and reinitialize if headers don't match
        if not current_headers or current_headers != headers:
            if worksheet.row_count > 0:
                worksheet.clear()
            time.sleep(1)  # Add delay to avoid quota issues
            worksheet.append_row(headers)
            st.info("Sheet initialized with proper headers.")
    except Exception as e:
        st.error(f"Error initializing sheet: {str(e)}")
        raise

@st.cache_data(ttl=600)  # Cache data for 10 minutes
def load_data():
    """
    Input: None
    Process: Loads todo data from Google Sheet
    Output: Returns DataFrame with todos and sheet info
    """
    try:
        worksheet = get_sheet()
        
        # Initialize sheet with headers
        initialize_sheet(worksheet)
        
        time.sleep(1)  # Add delay to avoid quota issues
        
        # Get all values including empty cells
        all_values = worksheet.get_all_values()
        
        if len(all_values) > 0:
            # Convert to DataFrame
            df = pd.DataFrame(all_values[1:], columns=all_values[0])
            # Remove empty rows
            df = df.dropna(how='all')
            
            # Ensure score column exists and has valid values
            if 'score' not in df.columns:
                df['score'] = 1  # Default score
            
            # Convert score to numeric, replacing invalid values with 1
            df['score'] = pd.to_numeric(df['score'], errors='coerce').fillna(1)
            
            # Debug info
            st.sidebar.expander("🔍 Debug Info").write({
                'columns': list(df.columns),
                'row_count': len(df),
                'sample_row': df.iloc[0].to_dict() if not df.empty else None
            })
            
            return df, {
                'worksheet': worksheet,
                'size': f"{worksheet.row_count} rows x {worksheet.col_count} columns"
            }
        else:
            return pd.DataFrame({'task': [], 'status': [], 'score': []}), {'worksheet': worksheet}
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        # Return empty DataFrame with required columns
        return pd.DataFrame({'task': [], 'status': [], 'score': []}), {'worksheet': None}

@retry_with_backoff(retries=3)
def add_todo(task, score):
    """
    Input: task text and score
    Process: Adds new todo to sheet with score
    Output: None
    """
    try:
        worksheet = get_sheet()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_row = [str(uuid.uuid4()), task, "pending", score, now, now]
        time.sleep(1)  # Add delay to avoid quota issues
        worksheet.append_row(new_row)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Error adding todo: {str(e)}")
        raise

def update_todo(row_idx, task, status, score):
    """
    Input: row index, updated task, status and score
    Process: Updates todo in sheet using batch update
    Output: None
    """
    worksheet = get_sheet()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Get the current row data to preserve id and created_at
    row_data = worksheet.row_values(row_idx + 2)  # Add 2 for header and 1-based index
    if not row_data:
        st.error("Could not find the todo item to update")
        return
        
    # Prepare the updated row with all columns
    updated_row = [
        row_data[0],  # Keep the original ID
        task,         # Update task
        status,       # Update status
        score,        # Update score
        row_data[4],  # Keep original created_at
        now          # Update updated_at
    ]
    
    # Update entire row at once using the new parameter order
    worksheet.update(values=[updated_row], range_name=f'A{row_idx + 2}:F{row_idx + 2}')
    st.cache_data.clear()

def delete_todo(row_idx):
    """
    Input: row index
    Process: Deletes todo from sheet
    Output: None
    """
    worksheet = get_sheet()
    worksheet.delete_rows(row_idx + 2)  # Add 2 to account for 0-based indexing and header row
    st.cache_data.clear()

# Page config
st.set_page_config(
    page_title="Todo List App", 
    page_icon="✅",
    layout="wide"
)

# Main content
st.title("✅ Todo List")

# Add new todo section
with st.form("add_todo_form", clear_on_submit=True):
    col1, col2 = st.columns([3, 1])
    with col1:
        new_todo = st.text_input("Add a new todo")
    with col2:
        new_score = st.selectbox(
            "Priority Score",
            options=list(SCORE_OPTIONS.keys()),
            format_func=lambda x: SCORE_OPTIONS[x],
            key="new_score"
        )
    submitted = st.form_submit_button("Add Todo")
    if submitted and new_todo:
        try:
            add_todo(new_todo, new_score)
            st.success("Todo added!")
            time.sleep(1)  # Add delay to avoid quota issues
            st.rerun()
        except Exception as e:
            st.error(f"Failed to add todo: {str(e)}")

try:
    # Load todos
    df, sheet_info = load_data()
    
    if not df.empty:
        # Sort by score (highest to lowest) and display todos
        df = df.sort_values('score', ascending=False)
        
        for idx, row in df.iterrows():
            try:
                col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
                
                with col1:
                    task = st.text_input("Task", row['task'], key=f"task_{idx}")
                
                with col2:
                    status = st.selectbox(
                        "Status",
                        options=['pending', 'completed'],
                        index=0 if row['status'] == 'pending' else 1,
                        key=f"status_{idx}"
                    )
                
                with col3:
                    current_score = int(row['score']) if pd.notnull(row['score']) else 1
                    score = st.selectbox(
                        "Priority",
                        options=list(SCORE_OPTIONS.keys()),
                        format_func=lambda x: SCORE_OPTIONS[x],
                        index=list(SCORE_OPTIONS.keys()).index(current_score) if current_score in SCORE_OPTIONS.keys() else 0,
                        key=f"score_{idx}"
                    )
                
                with col4:
                    if st.button("Update", key=f"update_{idx}"):
                        update_todo(idx, task, status, score)
                        st.success("Todo updated!")
                        time.sleep(1)  # Add delay to avoid quota issues
                        st.rerun()
                
                with col5:
                    if st.button("Delete", key=f"delete_{idx}"):
                        delete_todo(idx)
                        st.success("Todo deleted!")
                        time.sleep(1)  # Add delay to avoid quota issues
                        st.rerun()
            except Exception as e:
                st.error(f"Error displaying todo {idx}: {str(e)}")
                continue
    else:
        st.info("No todos yet! Add your first todo above.")

except Exception as e:
    st.error(f"An error occurred: {str(e)}")
    st.info("Please try refreshing the page in a few moments...")

# Sidebar
with st.sidebar:
    st.title("Todo List Info")
    
    # Refresh button
    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.success("Refreshing data...")
        time.sleep(1)  # Add delay to avoid quota issues
        st.rerun()
    
    # Stats
    if not df.empty:
        st.write("📊 Statistics")
        total = len(df)
        completed = len(df[df['status'] == 'completed'])
        
        # Score distribution
        st.write("Priority Distribution:")
        try:
            for score, label in SCORE_OPTIONS.items():
                count = len(df[df['score'] == score])
                st.write(f"{label}: {count}")
        except Exception as e:
            st.error(f"Error calculating priority distribution: {str(e)}")
        
        st.write(f"Total todos: {total}")
        st.write(f"Completed: {completed}")
        st.write(f"Pending: {total - completed}")
    
    # Cache info
    st.info("ℹ️ Data is cached for 10 minutes") 