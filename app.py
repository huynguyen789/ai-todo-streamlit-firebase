"""
Logic:
- Connect to Firestore and authenticate with service account
- Provide CRUD operations for todo items with scoring (10, 7, 5, 1)
- Display todo list with add/edit/delete functionality and colored score selection
- Cache data for performance
- Handle API operations with simple retries
- Enhanced UI with card-based layout and visual indicators
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
    10: "🔴 High Priority (10)",
    7: "🟡 Medium-High (7)",
    5: "🟢 Medium (5)",
    1: "⚪ Low (1)"
}

# Score to color mapping
SCORE_COLORS = {
    10: "#ff5252",  # Red
    7: "#ffd740",   # Yellow
    5: "#4caf50",   # Green
    1: "#e0e0e0"    # Light Gray
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
    Process: Initializes Firebase app with credentials
    Output: Firebase app instance
    """
    if not firebase_admin._apps:
        # Path to the Firebase credentials file
        cred_path = os.path.join(os.path.dirname(__file__), "data", "firebase.json")
        
        # Load credentials from file
        cred = credentials.Certificate(cred_path)
        
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
    Process: Loads todo data from Firestore
    Output: Returns DataFrame with todos
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
            
            # Convert score to numeric, replacing invalid values with 1
            df['score'] = pd.to_numeric(df['score'], errors='coerce').fillna(1)
            
            # Debug info
            st.sidebar.expander("🔍 Debug Info").write({
                'columns': list(df.columns),
                'row_count': len(df),
                'sample_row': df.iloc[0].to_dict() if not df.empty else None
            })
            
            return df
        else:
            return pd.DataFrame({'task': [], 'status': [], 'score': [], 'id': []})
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        # Return empty DataFrame with required columns
        return pd.DataFrame({'task': [], 'status': [], 'score': [], 'id': []})

@retry_with_backoff(retries=3)
def add_todo(task, score):
    """
    Input: task text and score
    Process: Adds new todo to Firestore with score
    Output: None
    """
    try:
        db = get_firestore_db()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Create new todo document
        new_todo = {
            'task': task,
            'status': 'pending',
            'score': score,
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
            'score': score,
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
    
    /* Card styling */
    .todo-card {
        border-radius: 10px;
        padding: 1.2rem;
        margin-bottom: 1rem;
        background-color: white;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
    }
    .todo-card:hover {
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        transform: translateY(-2px);
    }
    
    /* Priority indicators */
    .priority-indicator {
        width: 8px;
        height: 100%;
        border-radius: 4px;
        position: absolute;
        left: 0;
        top: 0;
    }
    
    /* Form styling */
    .add-form {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    
    /* Button styling */
    .stButton>button {
        border-radius: 5px;
        font-weight: 500;
    }
    
    /* Update button */
    .update-btn>button {
        background-color: #4CAF50;
        color: white;
    }
    
    /* Delete button */
    .delete-btn>button {
        background-color: #f44336;
        color: white;
    }
    
    /* Status toggle */
    .status-complete {
        text-decoration: line-through;
        color: #9e9e9e;
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        padding: 2rem 1rem;
    }
    
    /* Stats cards */
    .stat-card {
        background-color: white;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    
    /* Priority labels */
    .priority-label {
        display: inline-block;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-weight: 500;
        color: white;
        margin-right: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Main content
st.title("✅ Todo List")

# Add new todo section
st.markdown('<div class="add-form">', unsafe_allow_html=True)
with st.form("add_todo_form", clear_on_submit=True):
    st.subheader("Add New Task")
    
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
        submitted = st.form_submit_button("Add Task", use_container_width=True)
    
    if submitted and new_todo:
        try:
            add_todo(new_todo, new_score)
            st.success("Task added successfully!")
            time.sleep(1)  # Add delay for UI feedback
            st.rerun()
        except Exception as e:
            st.error(f"Failed to add task: {str(e)}")
st.markdown('</div>', unsafe_allow_html=True)

try:
    # Load todos
    df = load_data()
    
    if not df.empty:
        # Sort by score (highest to lowest) and display todos
        df = df.sort_values('score', ascending=False)
        
        # Group tasks by priority for better organization
        for priority in sorted(df['score'].unique(), reverse=True):
            priority_df = df[df['score'] == priority]
            
            # Only show priority header if there are tasks with this priority
            if not priority_df.empty:
                priority_int = int(priority)
                if priority_int in SCORE_OPTIONS:
                    st.markdown(f"""
                    <div style="display: flex; align-items: center; margin-top: 1.5rem; margin-bottom: 0.5rem;">
                        <div style="background-color: {SCORE_COLORS[priority_int]}; width: 15px; height: 15px; border-radius: 50%; margin-right: 10px;"></div>
                        <h3 style="margin: 0;">{SCORE_OPTIONS[priority_int].split('(')[0]}</h3>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Display tasks for this priority
            for idx, row in priority_df.iterrows():
                try:
                    # Create a card with colored border based on priority
                    priority_int = int(row['score'])
                    border_color = SCORE_COLORS.get(priority_int, "#e0e0e0")
                    
                    st.markdown(f"""
                    <div class="todo-card" style="border-left: 5px solid {border_color}; position: relative;">
                    """, unsafe_allow_html=True)
                    
                    # Task content
                    col1, col2, col3 = st.columns([5, 2, 2])
                    
                    with col1:
                        task_style = "status-complete" if row['status'] == 'completed' else ""
                        st.markdown(f'<p class="{task_style}" style="font-size: 1.1rem; margin-bottom: 0.5rem;">{row["task"]}</p>', unsafe_allow_html=True)
                        task = st.text_input("Edit Task", row['task'], key=f"task_{idx}", label_visibility="collapsed")
                    
                    with col2:
                        status = st.checkbox(
                            "Completed", 
                            value=True if row['status'] == 'completed' else False, 
                            key=f"status_{idx}"
                        )
                        status_value = "completed" if status else "pending"
                    
                    with col3:
                        score = st.selectbox(
                            "Priority",
                            options=list(SCORE_OPTIONS.keys()),
                            format_func=lambda x: SCORE_OPTIONS[x],
                            index=list(SCORE_OPTIONS.keys()).index(priority_int) if priority_int in SCORE_OPTIONS.keys() else 0,
                            key=f"score_{idx}"
                        )
                    
                    # Action buttons
                    col1, col2, col3, col4 = st.columns([3, 3, 3, 3])
                    
                    with col3:
                        st.markdown('<div class="update-btn">', unsafe_allow_html=True)
                        if st.button("Update", key=f"update_{idx}", use_container_width=True):
                            update_todo(row['id'], task, status_value, score)
                            st.success("Task updated!")
                            time.sleep(1)  # Add delay for UI feedback
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    with col4:
                        st.markdown('<div class="delete-btn">', unsafe_allow_html=True)
                        if st.button("Delete", key=f"delete_{idx}", use_container_width=True):
                            delete_todo(row['id'])
                            st.success("Task deleted!")
                            time.sleep(1)  # Add delay for UI feedback
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                except Exception as e:
                    st.error(f"Error displaying task {idx}: {str(e)}")
                    continue
    else:
        st.info("No tasks yet! Add your first task above.")

except Exception as e:
    st.error(f"An error occurred: {str(e)}")
    st.info("Please try refreshing the page in a few moments...")

# Sidebar
with st.sidebar:
    st.title("Todo List Info")
    
    # Refresh button
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.success("Refreshing data...")
        time.sleep(1)  # Add delay for UI feedback
        st.rerun()
    
    # Stats
    if not df.empty:
        st.markdown("## 📊 Statistics")
        
        # Total tasks card
        total = len(df)
        completed = len(df[df['status'] == 'completed'])
        pending = total - completed
        
        # Progress bar
        progress = completed / total if total > 0 else 0
        st.markdown(f"""
        <div class="stat-card">
            <h4>Progress</h4>
            <div style="margin-bottom: 0.5rem;">
                <div style="height: 10px; background-color: #e0e0e0; border-radius: 5px;">
                    <div style="height: 10px; width: {progress * 100}%; background-color: #4CAF50; border-radius: 5px;"></div>
                </div>
            </div>
            <p>Completed: {completed}/{total} ({int(progress * 100)}%)</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Priority distribution
        st.markdown('<div class="stat-card">', unsafe_allow_html=True)
        st.markdown("<h4>Priority Distribution</h4>", unsafe_allow_html=True)
        
        try:
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
                    <div style="flex-grow: 1; height: 15px; background-color: #f0f0f0; border-radius: 3px;">
                        <div style="width: {bar_width}%; height: 15px; background-color: {SCORE_COLORS[score]}; border-radius: 3px;"></div>
                    </div>
                    <div style="width: 30px; text-align: right; margin-left: 5px;">{count}</div>
                </div>
                """, unsafe_allow_html=True)
                
        except Exception as e:
            st.error(f"Error calculating priority distribution: {str(e)}")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Status summary
        st.markdown(f"""
        <div class="stat-card">
            <h4>Status Summary</h4>
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
        </div>
        """, unsafe_allow_html=True)
    
    # Cache info
    st.info("ℹ️ Data is cached for 10 minutes") 