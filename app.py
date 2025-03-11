"""
Logic:
- Connect to Google Sheet and authenticate
- Provide CRUD operations for todo items
- Display todo list with add/edit/delete functionality
- Cache data for performance
"""

import streamlit as st
from google.oauth2 import service_account
import pandas as pd
from datetime import datetime
import uuid

# Create a connection object and authenticate
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["connections"]["gsheets"],
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
    ],
)

def get_sheet():
    """
    Input: None
    Process: Creates connection to Google Sheet
    Output: Returns worksheet object
    """
    import gspread
    gc = gspread.authorize(credentials)
    sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    sh = gc.open_by_url(sheet_url)
    worksheet = sh.get_worksheet(0)
    return worksheet

def initialize_sheet(worksheet):
    """
    Input: worksheet object
    Process: Initializes sheet with headers if needed
    Output: None
    """
    headers = ['id', 'task', 'status', 'created_at', 'updated_at']
    
    # Get current headers
    current_headers = worksheet.row_values(1) if worksheet.row_count > 0 else []
    
    # Clear and reinitialize if headers don't match
    if not current_headers or current_headers != headers:
        if worksheet.row_count > 0:
            worksheet.clear()
        worksheet.append_row(headers)
        st.info("Sheet initialized with proper headers.")

@st.cache_data(ttl=600)  # Cache data for 10 minutes
def load_data():
    """
    Input: None
    Process: Loads todo data from Google Sheet
    Output: Returns DataFrame with todos and sheet info
    """
    worksheet = get_sheet()
    
    # Initialize sheet with headers
    initialize_sheet(worksheet)
    
    # Get all values including empty cells
    all_values = worksheet.get_all_values()
    
    if len(all_values) > 0:
        # Convert to DataFrame
        df = pd.DataFrame(all_values[1:], columns=all_values[0])
        # Remove empty rows
        df = df.dropna(how='all')
        
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
        return pd.DataFrame(), {'worksheet': worksheet}

def add_todo(task):
    """
    Input: task text
    Process: Adds new todo to sheet
    Output: None
    """
    worksheet = get_sheet()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_row = [str(uuid.uuid4()), task, "pending", now, now]
    worksheet.append_row(new_row)
    st.cache_data.clear()

def update_todo(row_idx, task, status):
    """
    Input: row index, updated task and status
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
        row_data[3],  # Keep original created_at
        now          # Update updated_at
    ]
    
    # Update entire row at once
    worksheet.update(f'A{row_idx + 2}:E{row_idx + 2}', [updated_row])
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
    new_todo = st.text_input("Add a new todo")
    submitted = st.form_submit_button("Add Todo")
    if submitted and new_todo:
        add_todo(new_todo)
        st.success("Todo added!")
        st.rerun()

try:
    # Load todos
    df, sheet_info = load_data()
    
    if not df.empty:
        # Verify required columns exist
        required_columns = ['task', 'status']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            st.error(f"Missing required columns: {', '.join(missing_columns)}")
            st.info("Reinitializing sheet with proper structure...")
            initialize_sheet(sheet_info['worksheet'])
            st.rerun()
        
        # Display todos
        for idx, row in df.iterrows():
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            
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
                if st.button("Update", key=f"update_{idx}"):
                    update_todo(idx, task, status)
                    st.success("Todo updated!")
                    st.rerun()
            
            with col4:
                if st.button("Delete", key=f"delete_{idx}"):
                    delete_todo(idx)
                    st.success("Todo deleted!")
                    st.rerun()
    else:
        st.info("No todos yet! Add your first todo above.")

except Exception as e:
    st.error(f"An error occurred: {str(e)}")
    st.info("Attempting to fix the sheet structure...")
    try:
        worksheet = get_sheet()
        initialize_sheet(worksheet)
        st.rerun()
    except Exception as e2:
        st.error(f"Could not fix sheet: {str(e2)}")
        st.info("Make sure your Google Sheet is properly set up and shared with the service account.")

# Sidebar
with st.sidebar:
    st.title("Todo List Info")
    
    # Refresh button
    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.success("Refreshing data...")
        st.rerun()
    
    # Stats
    if not df.empty and 'status' in df.columns:
        st.write("📊 Statistics")
        total = len(df)
        completed = len(df[df['status'] == 'completed'])
        st.write(f"Total todos: {total}")
        st.write(f"Completed: {completed}")
        st.write(f"Pending: {total - completed}")
    
    # Cache info
    st.info("ℹ️ Data is cached for 10 minutes") 