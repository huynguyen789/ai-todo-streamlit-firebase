"""
Logic:
- Provides CRUD operations for todo items
- Manages todo data in Firestore
- Includes caching for better performance
- Supports subtasks with parent-child relationships
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import uuid
from utils.helpers import retry_with_backoff
from database.firebase_init import get_firestore_db

@st.cache_data(ttl=300)  # Cache data for 5 minutes
def load_data():
    """
    Input: None
    Process: Loads todo data from Firestore, ensures position field exists
    Output: Returns DataFrame with todos sorted by position
    """
    try:
        db = get_firestore_db()
        
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
        
        # Add completed_at timestamp when task is marked as complete
        if status == 'completed':
            # If task is being completed now, add completed_at timestamp
            todo_doc = db.collection('todos').document(doc_id).get()
            if todo_doc.exists:
                todo_data = todo_doc.to_dict()
                if todo_data.get('status') != 'completed':
                    update_data['completed_at'] = now
        elif status == 'pending':
            # If task is being marked as pending, remove completed_at timestamp
            update_data['completed_at'] = None
        
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
    Output: Boolean indicating success or failure
    """
    try:
        # Ensure doc_id is a string
        doc_id = str(doc_id).strip()
        
        # Get Firestore database instance
        db = get_firestore_db()
        
        # Find and delete subtasks first
        todos_collection = db.collection('todos')
        
        # Query for subtasks
        subtasks_query = todos_collection.where('parent_id', '==', doc_id).stream()
        subtask_ids = [subtask.id for subtask in subtasks_query]
        
        # Delete each subtask
        for subtask_id in subtask_ids:
            todos_collection.document(subtask_id).delete()
            
        # Now delete the main task
        todos_collection.document(doc_id).delete()
        
        # Force cache clearing to refresh data
        st.cache_data.clear()
        
        return True
        
    except Exception as e:
        st.error(f"Error deleting task: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return False

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
            todo_ref = db.collection('todos').document(doc_id)
            todo_ref.update({'position': target_position})
            
            target_ref = db.collection('todos').document(target_id)
            target_ref.update({'position': current_position})
            
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
            todo_ref = db.collection('todos').document(doc_id)
            todo_ref.update({'position': target_position})
            
            target_ref = db.collection('todos').document(target_id)
            target_ref.update({'position': current_position})
            
            # Clear cache to refresh data
            st.cache_data.clear()
    except Exception as e:
        st.error(f"Error moving todo down: {str(e)}")
        raise

@retry_with_backoff(retries=3)
def add_subtask(parent_id, task, score, category_id='work'):
    """
    Input: parent task ID, subtask text, score, and category_id
    Process: Adds new subtask to Firestore with parent-child relationship
    Output: None
    """
    try:
        db = get_firestore_db()
        
        # Get parent task to determine level
        parent_ref = db.collection('todos').document(parent_id)
        parent_doc = parent_ref.get()
        
        if parent_doc.exists:
            parent_data = parent_doc.to_dict()
            parent_level = parent_data.get('level', 0)
            
            # Subtask level is parent level + 1
            subtask_level = parent_level + 1
            
            # Add the subtask
            add_todo(
                task=task,
                score=score,
                category_id=category_id,
                parent_id=parent_id,
                level=subtask_level
            )
        else:
            st.error("Parent task not found")
            raise ValueError("Parent task not found")
    except Exception as e:
        st.error(f"Error adding subtask: {str(e)}")
        raise

def filter_tasks_by_timeframe(df, timeframe='all'):
    """
    Input: DataFrame with todos, timeframe option ('all', 'today', 'week', 'month', 'year')
    Process: Filters tasks based on selected completion timeframe
    Output: Filtered DataFrame
    """
    if timeframe == 'all' or df.empty:
        return df
    
    # Create copy to avoid modifying original
    filtered_df = df.copy()
    
    # Convert string timestamps to datetime objects where they exist
    if 'completed_at' in filtered_df.columns:
        filtered_df['completed_at'] = pd.to_datetime(filtered_df['completed_at'], errors='coerce')
    else:
        # If no completed_at column, return original DataFrame
        return df
    
    # Get current datetime for comparison
    now = pd.Timestamp.now()
    
    # Filter based on selected timeframe
    if timeframe == 'today':
        # Tasks completed today (same date)
        return filtered_df[
            (filtered_df['status'] == 'completed') & 
            (filtered_df['completed_at'].dt.date == now.date()) | 
            (filtered_df['status'] == 'pending')
        ]
    
    elif timeframe == 'week':
        # Tasks completed this week
        # Get start of current week (Monday)
        start_of_week = now - pd.Timedelta(days=now.dayofweek)
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0)
        
        return filtered_df[
            (filtered_df['status'] == 'completed') & 
            (filtered_df['completed_at'] >= start_of_week) | 
            (filtered_df['status'] == 'pending')
        ]
    
    elif timeframe == 'month':
        # Tasks completed this month
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0)
        
        return filtered_df[
            (filtered_df['status'] == 'completed') & 
            (filtered_df['completed_at'] >= start_of_month) | 
            (filtered_df['status'] == 'pending')
        ]
    
    elif timeframe == 'year':
        # Tasks completed this year
        start_of_year = now.replace(month=1, day=1, hour=0, minute=0, second=0)
        
        return filtered_df[
            (filtered_df['status'] == 'completed') & 
            (filtered_df['completed_at'] >= start_of_year) | 
            (filtered_df['status'] == 'pending')
        ]
    
    # Default case, return original DataFrame
    return df 