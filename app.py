"""
Logic:
- Connect to Firestore and authenticate with service account from Streamlit secrets
- Provide CRUD operations for todo items with scoring (10, 7, 5, 2)
- Display todo list with add/edit/delete functionality and colored score selection
- Cache data for performance
- Handle API operations with simple retries
- Clean, minimalist UI with inline task editing and organized sidebar
- Option to hide/show completed tasks in the main page for easy access
- Allow reordering tasks with up/down movement controls
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import uuid
import time
import random
import firebase_admin
from firebase_admin import credentials, firestore
from functools import wraps
import os
import json

# Score options with colors
SCORE_OPTIONS = {
    10: "🔴 Important-Urgent (10)",
    7: "🟡 Important-Not Urgent (7)",
    5: "🟢 Not Important-Urgent (5)",
    2: "⚪ Not Important-Not Urgent (2)"
}

# Score to color mapping
SCORE_COLORS = {
    10: "#ff5252",  # Red
    7: "#ffd740",   # Yellow
    5: "#4caf50",   # Green
    2: "#e0e0e0"    # Light Gray
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

# Initialize Firebase
@st.cache_resource
def get_firebase_app():
    """
    Input: None
    Process: Initializes Firebase app with credentials from Streamlit secrets
    Output: Firebase app instance
    """
    if not firebase_admin._apps:
        try:
            # Get credentials from Streamlit secrets
            firebase_config = st.secrets["firebase"]
            
            # Convert the AttrDict to a regular dictionary
            firebase_config_dict = dict(firebase_config)
            
            # Create a credentials object from the dictionary
            cred = credentials.Certificate(firebase_config_dict)
            
            # Initialize the app
            return firebase_admin.initialize_app(cred)
        except Exception as e:
            # If there's an error with the secrets format, try an alternative approach
            st.error(f"Error initializing Firebase: {str(e)}")
            
            # Create a temporary JSON file with the credentials
            firebase_config = st.secrets["firebase"]
            temp_cred_path = "/tmp/firebase_credentials.json"
            
            with open(temp_cred_path, "w") as f:
                json.dump(dict(firebase_config), f)
            
            # Use the file path for credentials
            cred = credentials.Certificate(temp_cred_path)
            
            # Initialize the app
            return firebase_admin.initialize_app(cred)
    return firebase_admin.get_app()

@st.cache_resource
def get_firestore_db():
    """
    Input: None
    Process: Gets Firestore database instance
    Output: Firestore database client
    """
    # Ensure Firebase app is initialized
    get_firebase_app()
    
    # Return Firestore client
    return firestore.client()

@retry_with_backoff(retries=3)
def initialize_collection():
    """
    Input: None
    Process: Ensures the todos collection exists
    Output: None
    """
    # This is a no-op for Firestore as collections are created implicitly
    # But we can use this to check connectivity
    db = get_firestore_db()
    todos_ref = db.collection('todos')
    # Just check if we can access the collection
    todos_ref.limit(1).get()

@st.cache_data(ttl=600)  # Cache data for 10 minutes
def load_data():
    """
    Input: None
    Process: Loads todo data from Firestore, ensures position field exists
    Output: Returns DataFrame with todos sorted by position
    """
    try:
        db = get_firestore_db()
        
        # Ensure collection exists
        initialize_collection()
        
        # Get all todos
        todos_ref = db.collection('todos')
        todos = todos_ref.stream()
        
        # Convert to list of dictionaries
        todos_list = []
        for todo in todos:
            todo_dict = todo.to_dict()
            todo_dict['id'] = todo.id  # Add document ID
            todos_list.append(todo_dict)
        
        if todos_list:
            # Convert to DataFrame
            df = pd.DataFrame(todos_list)
            
            # Ensure score column exists and has valid values
            if 'score' not in df.columns:
                df['score'] = 1  # Default score
            
            # Convert score to numeric, replacing invalid values with 2
            df['score'] = pd.to_numeric(df['score'], errors='coerce').fillna(2)
            
            # Convert any tasks with score 1 to score 2 (the new lowest priority)
            df.loc[df['score'] == 1, 'score'] = 2
            
            # Ensure position column exists
            if 'position' not in df.columns:
                # If position doesn't exist, create it based on current order
                df['position'] = range(len(df))
                
                # Update positions in Firestore
                for idx, row in df.iterrows():
                    db.collection('todos').document(row['id']).update({'position': idx})
            
            # Convert position to numeric and sort by it
            df['position'] = pd.to_numeric(df['position'], errors='coerce').fillna(0)
            df = df.sort_values('position')
            
            return df
        else:
            return pd.DataFrame({'task': [], 'status': [], 'score': [], 'id': [], 'position': []})
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        # Return empty DataFrame with required columns
        return pd.DataFrame({'task': [], 'status': [], 'score': [], 'id': [], 'position': []})

@retry_with_backoff(retries=3)
def add_todo(task, score):
    """
    Input: task text and score
    Process: Adds new todo to Firestore with score and position at top
    Output: None
    """
    try:
        db = get_firestore_db()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Get current todos to determine position
        todos_ref = db.collection('todos')
        todos = todos_ref.stream()
        
        # Find the minimum position value (to place new task at top)
        min_position = 0
        for todo in todos:
            todo_dict = todo.to_dict()
            if 'position' in todo_dict:
                position_value = todo_dict['position']
                # Convert to int if it's a NumPy type
                if hasattr(position_value, 'item'):
                    position_value = position_value.item()
                if position_value < min_position:
                    min_position = position_value
        
        # New position is one less than the minimum (to place at top)
        new_position = min_position - 1
        
        # Create new todo document
        new_todo = {
            'task': task,
            'status': 'pending',
            'score': int(score),  # Ensure score is a native Python int
            'position': int(new_position),  # Ensure position is a native Python int
            'created_at': now,
            'updated_at': now
        }
        
        # Add to Firestore
        db.collection('todos').add(new_todo)
        
        # Clear cache to refresh data
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Error adding todo: {str(e)}")
        raise

@retry_with_backoff(retries=3)
def update_todo(doc_id, task, status, score):
    """
    Input: document ID, updated task, status and score
    Process: Updates todo in Firestore
    Output: None
    """
    try:
        db = get_firestore_db()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Update document
        todo_ref = db.collection('todos').document(doc_id)
        todo_ref.update({
            'task': task,
            'status': status,
            'score': int(score),  # Ensure score is a native Python int
            'updated_at': now
        })
        
        # Clear cache to refresh data
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Error updating todo: {str(e)}")
        raise

@retry_with_backoff(retries=3)
def delete_todo(doc_id):
    """
    Input: document ID
    Process: Deletes todo from Firestore
    Output: None
    """
    try:
        db = get_firestore_db()
        
        # Delete document
        todo_ref = db.collection('todos').document(doc_id)
        todo_ref.delete()
        
        # Clear cache to refresh data
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Error deleting todo: {str(e)}")
        raise

@retry_with_backoff(retries=3)
def move_todo_up(doc_id, current_position, df):
    """
    Input: document ID, current position, and dataframe of todos
    Process: Moves todo up in the list by swapping positions with the task above it
    Output: None
    """
    try:
        db = get_firestore_db()
        
        # Find the task immediately above this one
        df_sorted = df.sort_values('position')
        
        # Get positions higher than current (smaller position value = higher in list)
        higher_positions = df_sorted[df_sorted['position'] < current_position]['position'].values
        
        if len(higher_positions) > 0:
            # Get the closest higher position
            target_position = max(higher_positions)
            
            # Convert NumPy types to native Python types
            target_position = int(target_position)
            current_position = int(current_position)
            
            # Find the task with this position
            target_task = df_sorted[df_sorted['position'] == target_position].iloc[0]
            target_id = target_task['id']
            
            # Swap positions
            db.collection('todos').document(doc_id).update({
                'position': target_position,
                'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            
            db.collection('todos').document(target_id).update({
                'position': current_position,
                'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            
            # Clear cache to refresh data
            st.cache_data.clear()
    except Exception as e:
        st.error(f"Error moving todo up: {str(e)}")
        raise

@retry_with_backoff(retries=3)
def move_todo_down(doc_id, current_position, df):
    """
    Input: document ID, current position, and dataframe of todos
    Process: Moves todo down in the list by swapping positions with the task below it
    Output: None
    """
    try:
        db = get_firestore_db()
        
        # Find the task immediately below this one
        df_sorted = df.sort_values('position')
        
        # Get positions lower than current (larger position value = lower in list)
        lower_positions = df_sorted[df_sorted['position'] > current_position]['position'].values
        
        if len(lower_positions) > 0:
            # Get the closest lower position
            target_position = min(lower_positions)
            
            # Convert NumPy types to native Python types
            target_position = int(target_position)
            current_position = int(current_position)
            
            # Find the task with this position
            target_task = df_sorted[df_sorted['position'] == target_position].iloc[0]
            target_id = target_task['id']
            
            # Swap positions
            db.collection('todos').document(doc_id).update({
                'position': target_position,
                'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            
            db.collection('todos').document(target_id).update({
                'position': current_position,
                'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            
            # Clear cache to refresh data
            st.cache_data.clear()
    except Exception as e:
        st.error(f"Error moving todo down: {str(e)}")
        raise

# Page config
st.set_page_config(
    page_title="Todo List App", 
    page_icon="✅",
    layout="wide"
)

# Custom CSS for better UI
st.markdown("""
<style>
    /* Main container styling */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Clean task list styling */
    .task-item {
        display: flex;
        align-items: center;
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
        background-color: rgba(255, 255, 255, 0.1);
        border-radius: 6px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        transition: all 0.2s ease;
    }
    .task-item:hover {
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.15);
        background-color: rgba(255, 255, 255, 0.15);
    }
    
    /* Priority dot */
    .priority-dot {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        margin-right: 12px;
        flex-shrink: 0;
    }
    
    /* Task text */
    .task-text {
        flex-grow: 1;
        margin: 0;
        font-size: 1rem;
    }
    .completed-task {
        text-decoration: line-through;
        opacity: 0.7;
    }
    
    /* Task actions */
    .task-actions {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    /* Action buttons */
    .stButton > button {
        border-radius: 4px;
        font-weight: 500;
    }
    
    /* Add form styling */
    .add-form {
        padding: 1.5rem;
        border-radius: 8px;
        margin-bottom: 2rem;
        background-color: rgba(255, 255, 255, 0.05);
    }
    
    /* Hide default streamlit elements */
    .stExpander {
        border: none !important;
        box-shadow: none !important;
    }
    
    /* Hide expander header */
    .streamlit-expanderHeader {
        display: none !important;
    }
    
    /* Task edit dialog */
    .task-edit-dialog {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0, 0, 0, 0.5);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 1000;
    }
    
    /* Improve button styling */
    button[data-testid="baseButton-secondary"] {
        background-color: transparent !important;
        border: none !important;
        padding: 0.3rem !important;
        min-width: 2rem !important;
        color: inherit !important;
    }
    
    /* Improve form elements */
    [data-testid="stForm"] {
        background-color: rgba(255, 255, 255, 0.05);
        border-radius: 8px;
        padding: 1rem;
    }
    
    /* Improve progress bar in dark mode */
    .stat-card .progress-bg {
        background-color: rgba(255, 255, 255, 0.1);
        border-radius: 4px;
    }
    
    .stat-card .progress-fill {
        background-color: #4CAF50;
        border-radius: 4px;
    }
    
    /* Ensure emoji visibility */
    .priority-emoji {
        filter: none !important;
        margin-left: 8px;
        font-size: 0.8rem;
    }
    
    /* Improve sidebar expanders */
    .sidebar .streamlit-expanderHeader {
        display: flex !important;
        color: inherit;
        background-color: transparent;
        font-weight: 500;
    }
    
    /* Improve stat cards */
    .stat-card {
        background-color: rgba(255, 255, 255, 0.05);
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
    
    /* Improve button contrast */
    .stButton > button:hover {
        border-color: rgba(255, 255, 255, 0.5) !important;
    }
</style>
""", unsafe_allow_html=True)

# Main content
st.title("✅ Todo List")

# Initialize show_completed in session state if not exists
if 'show_completed' not in st.session_state:
    st.session_state.show_completed = True

# Hide completed tasks toggle - moved from sidebar to main page
show_completed = st.toggle(
    "Show/Hide Completed Tasks",
    key="show_completed"  # This will use the value from session state without setting a default
)

# Add a horizontal line for visual separation
st.markdown("---")

# Load todos
try:
    df = load_data()
except Exception as e:
    st.error(f"An error occurred: {str(e)}")
    st.info("Please try refreshing the page in a few moments...")
    df = pd.DataFrame({'task': [], 'status': [], 'score': [], 'id': [], 'position': []})

# Sidebar with tabs
with st.sidebar:
    st.title("Todo List")
    
    # Tabs for different sections
    tab_options = ["📊 Statistics", "🔍 Debug Info"]
    selected_tab = st.radio(
        "View Options",
        options=tab_options,
        label_visibility="collapsed",
        key="sidebar_tabs"
    )
    
    # Stats tab
    if selected_tab == "📊 Statistics" and not df.empty:
        total = len(df)
        completed = len(df[df['status'] == 'completed'])
        pending = total - completed
        progress = completed / total if total > 0 else 0
        
        # Progress summary
        with st.expander("Progress", expanded=True):
            st.markdown(f"""
            <div class="stat-card">
                <div style="margin-bottom: 0.5rem;">
                    <div class="progress-bg" style="height: 8px;">
                        <div class="progress-fill" style="height: 8px; width: {progress * 100}%;"></div>
                    </div>
                </div>
                <p>Completed: {completed}/{total} ({int(progress * 100)}%)</p>
            </div>
            """, unsafe_allow_html=True)
        
        # Priority distribution
        with st.expander("Priority Distribution", expanded=False):
            for score, label in SCORE_OPTIONS.items():
                count = len(df[df['score'] == score])
                emoji = label.split()[0]
                label_text = label.split(emoji)[1].strip()
                
                # Create a horizontal bar chart
                bar_width = (count / total * 100) if total > 0 else 0
                st.markdown(f"""
                <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
                    <div style="width: 25px; text-align: center;">{emoji}</div>
                    <div style="width: 120px;">{label_text}</div>
                    <div class="progress-bg" style="flex-grow: 1; height: 12px;">
                        <div style="width: {bar_width}%; height: 12px; background-color: {SCORE_COLORS[score]}; border-radius: 3px;"></div>
                    </div>
                    <div style="width: 30px; text-align: right; margin-left: 5px;">{count}</div>
                </div>
                """, unsafe_allow_html=True)
        
        # Status summary
        with st.expander("Status Summary", expanded=False):
            st.markdown(f"""
            <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                <div>
                    <p style="font-size: 0.9rem; color: #757575; margin-bottom: 0;">Pending</p>
                    <p style="font-size: 1.5rem; font-weight: 500; margin: 0;">{pending}</p>
                </div>
                <div>
                    <p style="font-size: 0.9rem; color: #757575; margin-bottom: 0;">Completed</p>
                    <p style="font-size: 1.5rem; font-weight: 500; margin: 0;">{completed}</p>
                </div>
                <div>
                    <p style="font-size: 0.9rem; color: #757575; margin-bottom: 0;">Total</p>
                    <p style="font-size: 1.5rem; font-weight: 500; margin: 0;">{total}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    # Debug tab
    elif selected_tab == "🔍 Debug Info":
        with st.expander("Debug Information", expanded=True):
            if not df.empty:
                st.write({
                    'columns': list(df.columns),
                    'row_count': len(df),
                    'sample_row': df.iloc[0].to_dict() if not df.empty else None
                })
            else:
                st.write("No data available")

# Add new todo section - initially collapsed
with st.expander("➕ Add New Task", expanded=False):

    with st.form("add_todo_form", clear_on_submit=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            new_todo = st.text_input("Task Description", placeholder="Enter your task here...")
        with col2:
            new_score = st.selectbox(
                "Priority",
                options=list(SCORE_OPTIONS.keys()),
                format_func=lambda x: SCORE_OPTIONS[x],
                key="new_score"
            )
        
        col1, col2, col3 = st.columns([3, 1, 1])
        with col3:
            st.markdown('<div class="add-task-btn">', unsafe_allow_html=True)
            submitted = st.form_submit_button("Add Task", use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        if submitted and new_todo:
            try:
                add_todo(new_todo, new_score)
                st.success("Task added successfully!")
                time.sleep(1)  # Add delay for UI feedback
                st.rerun()
            except Exception as e:
                st.error(f"Failed to add task: {str(e)}")
    st.markdown('</div>', unsafe_allow_html=True)

# Display tasks
if not df.empty:
    # Sort by score (highest to lowest) and filter based on show_completed setting
    df = df.sort_values('score', ascending=False)
    if not show_completed:  # Use the toggle value directly
        df = df[df['status'] != 'completed']
    
    # Store task edit states
    if 'edit_states' not in st.session_state:
        st.session_state.edit_states = {}
        
    # Store the task being edited
    if 'editing_task' not in st.session_state:
        st.session_state.editing_task = None
        
    # Function to toggle task completion status
    def toggle_status(task_id, current_status, task_text, score):
        new_status = "pending" if current_status == "completed" else "completed"
        update_todo(task_id, task_text, new_status, score)
        st.rerun()
        
    # Function to delete a task
    def delete_task(task_id):
        delete_todo(task_id)
        st.success("Task deleted!")
        time.sleep(0.5)
        st.rerun()
    
    # Display all tasks in a clean list
    for idx, row in df.iterrows():
        task_id = row['id']
        priority_int = int(row['score'])
        position = row['position']
        dot_color = SCORE_COLORS.get(priority_int, "#e0e0e0")  # Default to light gray if score not found
        task_status = "completed" if row['status'] == 'completed' else "pending"
        task_class = "completed-task" if task_status == "completed" else ""
        
        # Create a container for each task
        task_container = st.container()
        
        # Create columns for task display and actions
        with task_container:
            # Create columns for the task and action buttons
            col1, col2, col3, col4, col5, col6 = st.columns([20, 1, 1, 1, 1, 1])
            
            with col1:
                # Task item with minimal info
                st.markdown(f"""
                <div class="task-item" id="task-{task_id}">
                    <div class="priority-dot" style="background-color: {dot_color};"></div>
                    <p class="task-text {task_class}">{row['task']}</p>
                    <span class="priority-emoji">{SCORE_OPTIONS.get(priority_int, "⚪ Unknown").split()[0]}</span>
                </div>
                """, unsafe_allow_html=True)
            
            # Action buttons as actual Streamlit buttons
            with col2:
                if st.button("✓", key=f"complete_{idx}", help=f"Mark as {'pending' if task_status == 'completed' else 'completed'}"):
                    toggle_status(task_id, task_status, row['task'], priority_int)
            
            with col3:
                # Set the editing task and show edit form
                if st.button("✎", key=f"edit_{idx}", help="Edit task"):
                    # Store current values in session state for editing
                    st.session_state.editing_task = {
                        'id': task_id,
                        'task': row['task'],
                        'status': task_status,
                        'score': priority_int
                    }
                    st.rerun()
            
            with col4:
                if st.button("🗑", key=f"delete_{idx}", help="Delete task"):
                    delete_task(task_id)
            
            # Add move up button
            with col5:
                if st.button("↑", key=f"up_{idx}", help="Move task up"):
                    move_todo_up(task_id, int(position), df)
                    st.rerun()
            
            # Add move down button
            with col6:
                if st.button("↓", key=f"down_{idx}", help="Move task down"):
                    move_todo_down(task_id, int(position), df)
                    st.rerun()
        
    # Show edit form if a task is being edited
    if st.session_state.editing_task:
        with st.form(key="edit_task_form"):
            st.subheader("Edit Task")
            
            edit_task = st.text_input("Task", value=st.session_state.editing_task['task'])
            
            col1, col2 = st.columns(2)
            
            with col1:
                edit_status = st.checkbox(
                    "Completed", 
                    value=True if st.session_state.editing_task['status'] == 'completed' else False
                )
                edit_status_value = "completed" if edit_status else "pending"
            
            with col2:
                edit_score = st.selectbox(
                    "Priority",
                    options=list(SCORE_OPTIONS.keys()),
                    format_func=lambda x: SCORE_OPTIONS[x],
                    index=list(SCORE_OPTIONS.keys()).index(st.session_state.editing_task['score']) 
                        if st.session_state.editing_task['score'] in SCORE_OPTIONS.keys() else 0
                )
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.form_submit_button("Update"):
                    update_todo(
                        st.session_state.editing_task['id'], 
                        edit_task, 
                        edit_status_value, 
                        edit_score
                    )
                    st.session_state.editing_task = None
                    st.success("Task updated!")
                    time.sleep(0.5)
                    st.rerun()
            
            with col2:
                if st.form_submit_button("Cancel"):
                    st.session_state.editing_task = None
                    st.rerun()
else:
    st.info("No tasks yet! Add your first task above.")

# # Cache info at the bottom
# st.info("ℹ️ Data is cached for 10 minutes") 