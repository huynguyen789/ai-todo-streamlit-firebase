"""
Logic:
- Connect to Firestore and authenticate with service account from Streamlit secrets
- Provide CRUD operations for todo items with scoring (10, 7, 5, 2)
- Display todo list with add/edit/delete functionality and colored score selection
- Support subtasks with parent-child relationships and visual indentation
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

# Default categories with colors
DEFAULT_CATEGORIES = {
    "work": {"name": "Work", "color": "#FF6B6B"},  # Coral Red
    "life": {"name": "Life", "color": "#4ECDC4"},  # Turquoise
    "projects": {"name": "Projects", "color": "#45B7D1"}  # Sky Blue
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
                    # Reduce sleep time for faster retries while maintaining exponential backoff
                    time.sleep(sleep_time / 2)
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

@retry_with_backoff(retries=2, backoff_in_seconds=0.5)
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

@retry_with_backoff(retries=2, backoff_in_seconds=0.5)
def initialize_categories():
    """
    Input: None
    Process: Ensures default categories exist in Firestore
    Output: None
    """
    try:
        db = get_firestore_db()
        categories_ref = db.collection('categories')
        
        # Check if categories collection is empty
        existing_categories = list(categories_ref.limit(1).stream())
        
        if not existing_categories:
            # Add default categories
            for category_id, category_data in DEFAULT_CATEGORIES.items():
                categories_ref.document(category_id).set({
                    'name': category_data['name'],
                    'color': category_data['color'],
                    'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
    except Exception as e:
        st.error(f"Error initializing categories: {str(e)}")
        raise

@st.cache_data(ttl=300)
def load_categories():
    """
    Input: None
    Process: Loads categories from Firestore
    Output: DataFrame with categories
    """
    try:
        db = get_firestore_db()
        categories_ref = db.collection('categories')
        categories = categories_ref.stream()
        
        categories_list = []
        for category in categories:
            category_dict = category.to_dict()
            category_dict['id'] = category.id
            categories_list.append(category_dict)
            
        if categories_list:
            return pd.DataFrame(categories_list)
        else:
            return pd.DataFrame({'id': [], 'name': [], 'color': [], 'created_at': [], 'updated_at': []})
    except Exception as e:
        st.error(f"Error loading categories: {str(e)}")
        return pd.DataFrame({'id': [], 'name': [], 'color': [], 'created_at': [], 'updated_at': []})

@retry_with_backoff(retries=3)
def add_category(name, color):
    """
    Input: category name and color
    Process: Adds new category to Firestore
    Output: None
    """
    try:
        db = get_firestore_db()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        new_category = {
            'name': name,
            'color': color,
            'created_at': now,
            'updated_at': now
        }
        
        db.collection('categories').add(new_category)
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Error adding category: {str(e)}")
        raise

@retry_with_backoff(retries=3)
def update_category(doc_id, name, color):
    """
    Input: document ID, updated name and color
    Process: Updates category in Firestore
    Output: None
    """
    try:
        db = get_firestore_db()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        category_ref = db.collection('categories').document(doc_id)
        category_ref.update({
            'name': name,
            'color': color,
            'updated_at': now
        })
        
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Error updating category: {str(e)}")
        raise

@retry_with_backoff(retries=3)
def delete_category(doc_id):
    """
    Input: document ID
    Process: Deletes category from Firestore and updates associated todos
    Output: None
    """
    try:
        db = get_firestore_db()
        
        # Delete the category
        category_ref = db.collection('categories').document(doc_id)
        category_ref.delete()
        
        # Update todos that used this category to use default category
        todos_ref = db.collection('todos')
        todos = todos_ref.where('category_id', '==', doc_id).stream()
        
        for todo in todos:
            todo_ref = todos_ref.document(todo.id)
            todo_ref.update({
                'category_id': 'work',  # Set to default category
                'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Error deleting category: {str(e)}")
        raise

@st.cache_data(ttl=300)  # Cache data for 5 minutes
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
            # Ensure category_id exists
            if 'category_id' not in todo_dict:
                todo_dict['category_id'] = 'work'  # Default to work category
            # Ensure parent_id exists
            if 'parent_id' not in todo_dict:
                todo_dict['parent_id'] = None  # Default to no parent
            # Ensure level exists
            if 'level' not in todo_dict:
                todo_dict['level'] = 0  # Default to level 0 (main task)
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
            # Return empty DataFrame with all required columns including category_id, parent_id, and level
            return pd.DataFrame({
                'task': [], 
                'status': [], 
                'score': [], 
                'id': [], 
                'position': [],
                'category_id': [],  # Add category_id column
                'parent_id': [],    # Add parent_id column
                'level': []         # Add level column
            })
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        # Return empty DataFrame with all required columns including category_id, parent_id, and level
        return pd.DataFrame({
            'task': [], 
            'status': [], 
            'score': [], 
            'id': [], 
            'position': [],
            'category_id': [],  # Add category_id column
            'parent_id': [],    # Add parent_id column
            'level': []         # Add level column
        })

@retry_with_backoff(retries=3)
def add_todo(task, score, category_id='work', parent_id=None, level=0):
    """
    Input: task text, score, category_id, parent_id (for subtasks), and level (nesting depth)
    Process: Adds new todo to Firestore with score, category, and parent-child relationship
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
            'category_id': category_id,
            'parent_id': parent_id,  # Add parent_id field
            'level': int(level),     # Add level field
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
def update_todo(doc_id, task, status, score, category_id=None, parent_id=None, level=None):
    """
    Input: document ID, updated task, status, score, optional category_id, parent_id, and level
    Process: Updates todo in Firestore
    Output: None
    """
    try:
        db = get_firestore_db()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Prepare update data
        update_data = {
            'task': task,
            'status': status,
            'score': int(score),  # Ensure score is a native Python int
            'updated_at': now
        }
        
        # Add category_id to update if provided
        if category_id is not None:
            update_data['category_id'] = category_id
            
        # Add parent_id to update if provided
        if parent_id is not None:
            update_data['parent_id'] = parent_id
            
        # Add level to update if provided
        if level is not None:
            update_data['level'] = int(level)
        
        # Update document
        todo_ref = db.collection('todos').document(doc_id)
        todo_ref.update(update_data)
        
        # Clear cache to refresh data
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Error updating todo: {str(e)}")
        raise

@retry_with_backoff(retries=3)
def delete_todo(doc_id):
    """
    Input: document ID
    Process: Deletes todo from Firestore and its subtasks
    Output: None
    """
    try:
        db = get_firestore_db()
        
        # Find all subtasks of this task
        todos_ref = db.collection('todos')
        subtasks = todos_ref.where('parent_id', '==', doc_id).stream()
        
        # Delete all subtasks first
        for subtask in subtasks:
            subtask_ref = todos_ref.document(subtask.id)
            subtask_ref.delete()
        
        # Delete the main task
        todo_ref = todos_ref.document(doc_id)
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

@retry_with_backoff(retries=3)
def add_subtask(parent_id, task, score):
    """
    Input: parent task ID, subtask text, and score
    Process: Adds new subtask to Firestore with parent relationship
    Output: None
    """
    try:
        db = get_firestore_db()
        
        # Get parent task to determine category and level
        parent_ref = db.collection('todos').document(parent_id)
        parent = parent_ref.get()
        
        if not parent.exists:
            st.error("Parent task not found")
            return
            
        parent_data = parent.to_dict()
        category_id = parent_data.get('category_id', 'work')
        parent_level = parent_data.get('level', 0)
        subtask_level = parent_level + 1
        
        # Add the subtask with parent_id and incremented level
        add_todo(
            task=task,
            score=score,
            category_id=category_id,
            parent_id=parent_id,
            level=subtask_level
        )
        
    except Exception as e:
        st.error(f"Error adding subtask: {str(e)}")
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
    
    /* Subtask styling */
    .subtask {
        margin-left: 30px;
        position: relative;
    }
    
    .subtask:before {
        content: '';
        position: absolute;
        left: -20px;
        top: 0;
        height: 100%;
        width: 2px;
        background-color: rgba(255, 255, 255, 0.1);
    }
    
    .subtask:after {
        content: '';
        position: absolute;
        left: -20px;
        top: 50%;
        height: 2px;
        width: 15px;
        background-color: rgba(255, 255, 255, 0.1);
    }
    
    .subtask .priority-dot {
        width: 10px;
        height: 10px;
    }
    
    .subtask .task-text {
        font-size: 0.95rem;
    }
</style>
""", unsafe_allow_html=True)

# Main content
st.title("✅ Todo List")

# Initialize show_completed in session state if not exists
if 'show_completed' not in st.session_state:
    st.session_state.show_completed = True

# Initialize rerun flag to avoid unnecessary reruns
if 'needs_rerun' not in st.session_state:
    st.session_state.needs_rerun = False

# Function to set rerun flag instead of immediate rerun
def set_rerun_flag():
    st.session_state.needs_rerun = True

# Hide completed tasks toggle - moved from sidebar to main page
show_completed = st.toggle(
    "Show/Hide Completed Tasks",
    key="show_completed"  # This will use the value from session state without setting a default
)

# Initialize categories if needed and load them
initialize_categories()
categories_df = load_categories()

# Initialize selected category in session state if not exists
if 'selected_category' not in st.session_state:
    st.session_state.selected_category = 'all'

# Initialize new_category session state with "work" as default if not exists
if 'new_category' not in st.session_state:
    st.session_state.new_category = 'work'

# Category selection
col1, col2 = st.columns([3, 1])
with col1:
    # Convert categories to a dictionary for the selectbox
    category_options = {'all': 'All Categories'}
    for _, row in categories_df.iterrows():
        category_options[row['id']] = row['name']

    selected_category = st.selectbox(
        "Select Category",
        options=list(category_options.keys()),
        format_func=lambda x: category_options[x],
        key='selected_category'
    )

with col2:
    if st.button("⚙️ Manage Categories", use_container_width=True):
        st.session_state.show_category_manager = True
        set_rerun_flag()

# Category Management UI
if st.session_state.get('show_category_manager', False):
    with st.expander("Category Management", expanded=True):
        st.markdown("""
        <style>
        .category-item {
            display: flex;
            align-items: center;
            padding: 8px;
            margin: 4px 0;
            background: rgba(255,255,255,0.05);
            border-radius: 4px;
        }
        .category-color {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            margin-right: 10px;
        }
        .category-name {
            flex-grow: 1;
        }
        .category-actions {
            display: flex;
            gap: 8px;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Add new category form
        with st.form("add_category_form", clear_on_submit=True):
            st.subheader("Add New Category")
            new_cat_name = st.text_input("Category Name")
            new_cat_color = st.color_picker("Category Color", "#4ECDC4")
            
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.form_submit_button("Add Category", use_container_width=True):
                    if new_cat_name:
                        add_category(new_cat_name, new_cat_color)
                        st.success(f"Category '{new_cat_name}' added!")
                        set_rerun_flag()
            with col2:
                if st.form_submit_button("Close Manager", use_container_width=True):
                    st.session_state.show_category_manager = False
                    set_rerun_flag()
        
        # List existing categories
        st.subheader("Existing Categories")
        for _, category in categories_df.iterrows():
            st.markdown(f"""
            <div class="category-item">
                <div class="category-color" style="background-color: {category['color']};"></div>
                <div class="category-name">{category['name']}</div>
            </div>
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("✎ Edit", key=f"edit_{category['id']}", use_container_width=True):
                    st.session_state.editing_category = category
            
            with col2:
                if st.button("🗑 Delete", key=f"delete_{category['id']}", help="Delete category", use_container_width=True):
                    if st.session_state.get('confirm_delete') == category['id']:
                        delete_category(category['id'])
                        st.success(f"Category '{category['name']}' deleted!")
                        st.session_state.confirm_delete = None
                        set_rerun_flag()
                    else:
                        st.session_state.confirm_delete = category['id']
                        st.warning(f"Click again to confirm deleting '{category['name']}'")
            
            if st.session_state.get('confirm_delete') == category['id']:
                st.markdown("""
                <div style="text-align: center; padding: 8px; color: #ff4444; font-size: 0.9em;">
                    ⚠️ Click delete again to confirm. Associated tasks will be moved to Work category.
                </div>
                """, unsafe_allow_html=True)
        
        # Edit category form
        if 'editing_category' in st.session_state:
            st.markdown("---")
            with st.form("edit_category_form"):
                st.subheader(f"Edit Category: {st.session_state.editing_category['name']}")
                edit_cat_name = st.text_input("Category Name", value=st.session_state.editing_category['name'])
                edit_cat_color = st.color_picker("Category Color", st.session_state.editing_category['color'])
                
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.form_submit_button("Update", use_container_width=True):
                        update_category(
                            st.session_state.editing_category['id'],
                            edit_cat_name,
                            edit_cat_color
                        )
                        del st.session_state.editing_category
                        st.success("Category updated!")
                        set_rerun_flag()
                with col2:
                    if st.form_submit_button("Cancel", use_container_width=True):
                        del st.session_state.editing_category
                        set_rerun_flag()

# Add a horizontal line for visual separation
st.markdown("---")

# Load todos
try:
    df = load_data()
except Exception as e:
    st.error(f"An error occurred: {str(e)}")
    st.info("Please try refreshing the page in a few moments...")
    df = pd.DataFrame({'task': [], 'status': [], 'score': [], 'id': [], 'position': [], 'category_id': [], 'parent_id': [], 'level': []})

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
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            new_todo = st.text_input("Task Description", placeholder="Enter your task here...")
        with col2:
            new_score = st.selectbox(
                "Priority",
                options=list(SCORE_OPTIONS.keys()),
                format_func=lambda x: SCORE_OPTIONS[x],
                key="new_score"
            )
        with col3:
            # Get list of category IDs
            category_ids = [cat['id'] for _, cat in categories_df.iterrows()]
            # Find index of 'work' category if it exists, otherwise use 0
            default_index = category_ids.index('work') if 'work' in category_ids else 0
            
            new_category = st.selectbox(
                "Category",
                options=category_ids,
                format_func=lambda x: category_options[x],
                key="new_category",
                index=default_index
            )
        
        col1, col2, col3 = st.columns([3, 1, 1])
        with col3:
            st.markdown('<div class="add-task-btn">', unsafe_allow_html=True)
            submitted = st.form_submit_button("Add Task", use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        if submitted and new_todo:
            try:
                add_todo(new_todo, new_score, new_category)
                st.success("Task added successfully!")
                set_rerun_flag()
            except Exception as e:
                st.error(f"Failed to add task: {str(e)}")
    st.markdown('</div>', unsafe_allow_html=True)

# Display tasks
if not df.empty:
    # Sort by score (highest to lowest) and filter based on show_completed setting
    df = df.sort_values('score', ascending=False)
    if not show_completed:  # Use the toggle value directly
        df = df[df['status'] != 'completed']
    
    # Filter by selected category
    if selected_category != 'all':
        df = df[df['category_id'] == selected_category]
    
    # Store task edit states
    if 'edit_states' not in st.session_state:
        st.session_state.edit_states = {}
        
    # Store the task being edited
    if 'editing_task' not in st.session_state:
        st.session_state.editing_task = None
        
    # Function to toggle task completion status
    def toggle_status(task_id, current_status, task_text, score, category_id):
        new_status = "pending" if current_status == "completed" else "completed"
        update_todo(task_id, task_text, new_status, score, category_id)
        
        # If task is being marked as completed, ask if subtasks should also be completed
        if new_status == "completed":
            # Find all subtasks
            subtasks = df[df['parent_id'] == task_id]
            if not subtasks.empty:
                # Create a session state flag to show the confirmation dialog
                st.session_state.confirm_complete_subtasks = {
                    'parent_id': task_id,
                    'subtasks': subtasks
                }
        
        set_rerun_flag()
        
    # Batch operations for better performance
    @retry_with_backoff(retries=2, backoff_in_seconds=0.5)
    def complete_all_subtasks(parent_id):
        """
        Input: parent_id
        Process: Completes all subtasks of a parent task in a batch
        Output: None
        """
        try:
            db = get_firestore_db()
            batch = db.batch()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Find all subtasks
            subtasks_ref = db.collection('todos').where('parent_id', '==', parent_id)
            subtasks = subtasks_ref.stream()
            
            # Update all in a batch
            for subtask in subtasks:
                subtask_ref = db.collection('todos').document(subtask.id)
                batch.update(subtask_ref, {
                    'status': 'completed',
                    'updated_at': now
                })
            
            # Commit the batch
            batch.commit()
            
            # Clear cache
            st.cache_data.clear()
            
            st.success("All subtasks marked as completed!")
            st.session_state.confirm_complete_subtasks = None
            set_rerun_flag()
            
        except Exception as e:
            st.error(f"Error completing subtasks: {str(e)}")
            raise

    # Function to complete all subtasks - replace with call to batch function
    def complete_all_subtasks_handler(parent_id):
        complete_all_subtasks(parent_id)
        
    # Function to delete a task
    def delete_task(task_id):
        delete_todo(task_id)
        st.success("Task deleted!")
        set_rerun_flag()
    
    # Display all tasks in a clean list
    # First, sort by position and then organize by parent-child relationship
    df = df.sort_values('position')
    
    # Create a dictionary to track processed tasks to avoid duplicates
    processed_tasks = set()

    # Function to display a task and its subtasks recursively
    def display_task_with_subtasks(task_row, is_subtask=False):
        task_id = task_row['id']
        
        # Skip if already processed
        if task_id in processed_tasks:
            return
            
        processed_tasks.add(task_id)
        
        priority_int = int(task_row['score'])
        position = task_row['position']
        category_id = task_row.get('category_id', 'work')  # Default to work if no category
        dot_color = SCORE_COLORS.get(priority_int, "#e0e0e0")  # Default to light gray if score not found
        task_status = "completed" if task_row['status'] == 'completed' else "pending"
        task_class = "completed-task" if task_status == "completed" else ""
        
        # Get category color
        category_color = "#e0e0e0"  # Default color
        category_name = "Work"  # Default name
        if not categories_df.empty:
            category_row = categories_df[categories_df['id'] == category_id]
            if not category_row.empty:
                category_color = category_row.iloc[0]['color']
                category_name = category_row.iloc[0]['name']
        
        # Create a container for each task
        task_container = st.container()
        
        # Create columns for task display and actions
        with task_container:
            # Create columns for the task and action buttons
            col1, col2, col3, col4, col5, col6, col7 = st.columns([20, 1, 1, 1, 1, 1, 1])
            
            with col1:
                # Task item with category indicator
                subtask_class = "subtask" if is_subtask else ""
                st.markdown(f"""
                <div class="task-item {subtask_class}" id="task-{task_id}">
                    <div class="priority-dot" style="background-color: {dot_color};"></div>
                    <div style="display: flex; flex-direction: column; flex-grow: 1;">
                        <p class="task-text {task_class}" style="margin-bottom: 2px;">{task_row['task']}</p>
                        <div style="display: flex; align-items: center;">
                            <div style="width: 8px; height: 8px; border-radius: 50%; background-color: {category_color}; margin-right: 5px;"></div>
                            <span style="font-size: 0.8em; color: rgba(255,255,255,0.6);">{category_name}</span>
                        </div>
                    </div>
                    <span class="priority-emoji">{SCORE_OPTIONS.get(priority_int, "⚪ Unknown").split()[0]}</span>
                </div>
                """, unsafe_allow_html=True)
            
            # Action buttons as actual Streamlit buttons
            with col2:
                if st.button("✓", key=f"complete_{task_id}", help=f"Mark as {'pending' if task_status == 'completed' else 'completed'}"):
                    toggle_status(task_id, task_status, task_row['task'], priority_int, category_id)
            
            with col3:
                # Set the editing task and show edit form
                if st.button("✎", key=f"edit_{task_id}", help="Edit task"):
                    # Store current values in session state for editing
                    st.session_state.editing_task = {
                        'id': task_id,
                        'task': task_row['task'],
                        'status': task_status,
                        'score': priority_int,
                        'category_id': category_id,
                        'parent_id': task_row.get('parent_id'),
                        'level': task_row.get('level', 0)
                    }
                    st.rerun()
            
            with col4:
                if st.button("🗑", key=f"delete_{task_id}", help="Delete task"):
                    delete_task(task_id)
            
            # Add move up button
            with col5:
                if st.button("↑", key=f"up_{task_id}", help="Move task up"):
                    move_todo_up(task_id, int(position), df)
                    set_rerun_flag()
            
            # Add move down button
            with col6:
                if st.button("↓", key=f"down_{task_id}", help="Move task down"):
                    move_todo_down(task_id, int(position), df)
                    set_rerun_flag()
                    
            # Add subtask button (only for main tasks)
            with col7:
                if not is_subtask and st.button("+", key=f"subtask_{task_id}", help="Add subtask"):
                    st.session_state.adding_subtask = task_id
                    set_rerun_flag()
        
        # Display subtasks if any
        if not is_subtask:  # Only look for subtasks of main tasks
            subtasks = df[df['parent_id'] == task_id]
            for _, subtask_row in subtasks.iterrows():
                display_task_with_subtasks(subtask_row, is_subtask=True)
    
    # Display main tasks and their subtasks
    main_tasks = df[df['parent_id'].isnull()]
    for _, task_row in main_tasks.iterrows():
        display_task_with_subtasks(task_row)
    
    # Show confirmation dialog for completing subtasks
    if 'confirm_complete_subtasks' in st.session_state and st.session_state.confirm_complete_subtasks:
        parent_id = st.session_state.confirm_complete_subtasks['parent_id']
        subtasks = st.session_state.confirm_complete_subtasks['subtasks']
        
        st.markdown("---")
        st.warning(f"Do you want to mark all {len(subtasks)} subtasks as completed?")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes, complete all subtasks"):
                complete_all_subtasks_handler(parent_id)
        with col2:
            if st.button("No, keep subtasks as is"):
                st.session_state.confirm_complete_subtasks = None
                set_rerun_flag()
        
    # Show edit form if a task is being edited
    if st.session_state.editing_task:
        with st.form(key="edit_task_form"):
            st.subheader("Edit Task")
            
            edit_task = st.text_input("Task", value=st.session_state.editing_task['task'])
            
            col1, col2, col3 = st.columns(3)
            
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
            
            with col3:
                edit_category = st.selectbox(
                    "Category",
                    options=[cat['id'] for _, cat in categories_df.iterrows()],
                    format_func=lambda x: category_options[x],
                    index=list(categories_df['id']).index(st.session_state.editing_task['category_id'])
                        if st.session_state.editing_task['category_id'] in list(categories_df['id']) else 0
                )
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.form_submit_button("Update"):
                    update_todo(
                        st.session_state.editing_task['id'], 
                        edit_task, 
                        edit_status_value, 
                        edit_score,
                        edit_category,
                        st.session_state.editing_task.get('parent_id'),
                        st.session_state.editing_task.get('level')
                    )
                    st.session_state.editing_task = None
                    st.success("Task updated!")
                    set_rerun_flag()
            
            with col2:
                if st.form_submit_button("Cancel"):
                    st.session_state.editing_task = None
                    set_rerun_flag()
        
    # Show subtask form if adding a subtask
    if 'adding_subtask' in st.session_state and st.session_state.adding_subtask:
        parent_id = st.session_state.adding_subtask
        parent_task = df[df['id'] == parent_id].iloc[0] if not df[df['id'] == parent_id].empty else None
        
        if parent_task is not None:
            with st.form(key="add_subtask_form"):
                st.subheader(f"Add Subtask to: {parent_task['task']}")
                
                subtask_text = st.text_input("Subtask Description")
                subtask_score = st.selectbox(
                    "Priority",
                    options=list(SCORE_OPTIONS.keys()),
                    format_func=lambda x: SCORE_OPTIONS[x],
                    key="subtask_score"
                )
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.form_submit_button("Add Subtask"):
                        if subtask_text:
                            add_subtask(parent_id, subtask_text, subtask_score)
                            st.session_state.adding_subtask = None
                            st.success("Subtask added!")
                            set_rerun_flag()
                
                with col2:
                    if st.form_submit_button("Cancel"):
                        st.session_state.adding_subtask = None
                        set_rerun_flag()
else:
    st.info("No tasks yet! Add your first task above.")

# Perform a single rerun at the end if needed
if st.session_state.needs_rerun:
    st.session_state.needs_rerun = False
    st.rerun()

# Add a footer with cache info
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #888; font-size: 0.8em; padding: 10px;">
    ℹ️ Data is cached for 5 minutes for better performance
</div>
""", unsafe_allow_html=True) 