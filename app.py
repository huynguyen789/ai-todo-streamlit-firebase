"""
Logic:
- Connect to Firestore and authenticate with service account from Streamlit secrets
- Provide CRUD operations for todo items with scoring (10, 7, 5, 2)
- Display todo list with add/edit/delete functionality and colored score selection
- Support subtasks with parent-child relationships and visual indentation
- Cache data for performance
- Handle API operations with simple retries
- Clean, minimalist UI with inline task editing and organized sidebar
- Option to hide/show completed tasks in the main page for easy access (default: hidden)
- Allow reordering tasks with up/down movement controls
- Time-based filtering for completed tasks (today, week, month, year)
- Completed tasks automatically moved to bottom of list for better focus on active tasks
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

# Initialize session state variables
def initialize_session_state():
    """
    Input: None
    Process: Initialize all session state variables if they don't exist
    Output: None
    """
    if 'show_completed' not in st.session_state:
        st.session_state.show_completed = False
    if 'needs_rerun' not in st.session_state:
        st.session_state.needs_rerun = False
    if 'rerun_in_progress' not in st.session_state:
        st.session_state.rerun_in_progress = False
    if 'selected_category' not in st.session_state:
        st.session_state.selected_category = 'all'
    if 'new_category' not in st.session_state:
        st.session_state.new_category = 'work'
    if 'completion_timeframe' not in st.session_state:
        st.session_state.completion_timeframe = 'today'

try:
    # Initialize Firebase and collections
    initialize_collection()
    initialize_categories()
    
    # Initialize session state
    initialize_session_state()
    
    # Main content
    st.title("✅ Todo List")
    
    # Top controls in a single row
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    
    with col1:
        # Category selection
        categories_df = load_categories()
        selected_category = render_category_selector(categories_df)
    
    with col2:
        # Show/hide completed tasks toggle
        previous_show_completed = st.session_state.show_completed
        show_completed = st.toggle(
            "Show Completed Tasks",
            key="show_completed"
        )
        
        # When toggling from off to on, set timeframe to today
        if show_completed and not previous_show_completed:
            st.session_state.completion_timeframe = 'today'
            st.session_state.needs_rerun = True
    
    with col3:
        # Timeframe selector for completed tasks
        if show_completed:
            timeframe_options = {
                'today': 'Today',
                'week': 'This Week',
                'month': 'This Month',
                'year': 'This Year',
                'all': 'All Time'
            }
            completion_timeframe = st.selectbox(
                "Show Completed From",
                options=list(timeframe_options.keys()),
                format_func=lambda x: timeframe_options[x],
                key="completion_timeframe"
            )
        else:
            completion_timeframe = 'all'
    
    with col4:
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
    display_todo_list(df, categories_df, show_completed, completion_timeframe)
    
    # Add a footer with cache info and refresh button
    st.markdown("---")
    col1, col2 = st.columns([4, 1])
    
    with col1:
        st.markdown("""
        <div style="text-align: center; color: #888; font-size: 0.8em; padding: 5px;">
            ℹ️ Data is cached for 5 minutes for better performance
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        if st.button("🔄 Refresh Data", help="Clear cache and refresh all data"):
            # Hard refresh: clear cache and force rerun
            st.cache_data.clear()
            st.rerun()
    
    # Perform a single rerun at the very end if needed
    # This ensures all UI components are rendered before the rerun
    if st.session_state.needs_rerun:
        # Reset the flag first to prevent infinite loops
        st.session_state.needs_rerun = False
        
        # If deletion is in progress, ensure it completes before rerun
        deletion_in_progress = False
        for key in st.session_state:
            if key.startswith('task_deleted_'):
                deletion_in_progress = True
                break
        
        if deletion_in_progress:
            # For deletion operations, force a cache invalidation before rerun
            st.cache_data.clear()
        
        # Use a separate flag to track that we're in a rerun operation
        st.session_state.rerun_in_progress = True
        st.rerun()

    # Reset the rerun_in_progress flag on subsequent runs
    if st.session_state.get('rerun_in_progress', False):
        st.session_state.rerun_in_progress = False

except Exception as e:
    st.error(f"An unexpected error occurred: {str(e)}")
    st.info("Please try refreshing the page. If the problem persists, contact support.") 