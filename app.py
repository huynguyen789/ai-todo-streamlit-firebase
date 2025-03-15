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
from database.firebase_init import get_firestore_db, initialize_collection
from database.category_ops import initialize_categories, load_categories
from database.todo_operations import load_data
from ui.styles import apply_custom_css
from ui.sidebar import render_sidebar
from ui.category_ui import render_category_selector, display_category_management
from ui.todo_components import display_add_todo_form, display_todo_list

# Page config
st.set_page_config(
    page_title="Todo List App", 
    page_icon="✅",
    layout="wide"
)

# Apply custom CSS
apply_custom_css()

try:
    # Initialize Firebase and collections
    initialize_collection()
    initialize_categories()
    
    # Main content
    st.title("✅ Todo List")
    
    # Initialize session state variables
    if 'show_completed' not in st.session_state:
        st.session_state.show_completed = True
    if 'needs_rerun' not in st.session_state:
        st.session_state.needs_rerun = False
    if 'selected_category' not in st.session_state:
        st.session_state.selected_category = 'all'
    if 'new_category' not in st.session_state:
        st.session_state.new_category = 'work'
    
    # Top controls in a single row
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        # Category selection
        categories_df = load_categories()
        selected_category = render_category_selector(categories_df)
    
    with col2:
        # Show/hide completed tasks toggle
        show_completed = st.toggle(
            "Show Completed Tasks",
            key="show_completed",
            value=True
        )
    
    with col3:
        # Category management toggle
        if st.button("Manage Categories", key="toggle_category_manager"):
            st.session_state.show_category_manager = not st.session_state.get('show_category_manager', False)
            st.session_state.needs_rerun = True
    
    # Category Management UI (conditionally displayed)
    if st.session_state.get('show_category_manager', False):
        display_category_management(categories_df)
    
    # Load todos
    try:
        df = load_data()
    except Exception as e:
        st.error(f"An error occurred while loading data: {str(e)}")
        st.info("Please try refreshing the page in a few moments...")
        df = pd.DataFrame({'task': [], 'status': [], 'score': [], 'id': [], 'position': [], 'category_id': [], 'parent_id': [], 'level': []})
    
    # Render sidebar
    render_sidebar(df)
    
    # Add new todo section
    display_add_todo_form(categories_df)
    
    # Display tasks
    display_todo_list(df, categories_df, show_completed)
    
    # Perform a single rerun at the end if needed
    if st.session_state.needs_rerun:
        st.session_state.needs_rerun = False
        st.rerun()
    
    # Add a footer with cache info
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #888; font-size: 0.8em; padding: 5px;">
        ℹ️ Data is cached for 5 minutes for better performance
    </div>
    """, unsafe_allow_html=True)

except Exception as e:
    st.error(f"An unexpected error occurred: {str(e)}")
    st.info("Please try refreshing the page. If the problem persists, contact support.") 