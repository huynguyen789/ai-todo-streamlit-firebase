"""
Logic:
- Provides CRUD operations for categories
- Manages category data in Firestore
- Includes caching for better performance
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from utils.helpers import retry_with_backoff
from database.firebase_init import get_firestore_db

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