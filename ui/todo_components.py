"""
Logic:
- Provides UI components for todo items
- Renders todo list with add/edit/delete functionality
- Supports subtasks with parent-child relationships
"""

import streamlit as st
import pandas as pd
from database.category_ops import SCORE_OPTIONS, SCORE_COLORS
from database.todo_operations import (
    add_todo, update_todo, delete_todo, move_todo_up, 
    move_todo_down, add_subtask, filter_tasks_by_timeframe
)
from database.firebase_init import get_firestore_db

def display_add_todo_form(categories_df):
    """
    Input: DataFrame with categories
    Process: Renders compact form for adding new todo items
    Output: None
    """
    # Initialize task input in session state if not exists
    if 'new_task_input' not in st.session_state:
        st.session_state.new_task_input = ""
    
    with st.form(key="add_form", clear_on_submit=True):
        # st.markdown("### Add New Task")
        cols = st.columns([3, 1, 1, 1])
        
        # Task input
        with cols[0]:
            task = st.text_input("Task", value=st.session_state.new_task_input, key="task_input_field", placeholder="Enter task description")
        
        # Score selection
        with cols[1]:
            score = st.selectbox(
                "Priority",
                options=[10, 7, 5, 2],
                format_func=lambda x: SCORE_OPTIONS[x],  # Show the full priority description
                key="new_score"
            )
        
        # Category selection
        with cols[2]:
            if not categories_df.empty:
                category_options = {row['id']: row['name'] for _, row in categories_df.iterrows()}
                
                # Set the default value based on the filtered category
                default_index = 0
                # If a specific category is selected for filtering and it exists in options,
                # make it the default selection for new tasks
                if st.session_state.selected_category != 'all' and st.session_state.selected_category in category_options:
                    # If session state already has a value for new_category, we shouldn't override it
                    # unless we're first loading this form with a filtered category
                    if st.session_state.get('new_category') != st.session_state.selected_category:
                        st.session_state.new_category = st.session_state.selected_category
                
                category_id = st.selectbox(
                    "Category",
                    options=list(category_options.keys()),
                    format_func=lambda x: category_options[x],
                    key="new_category"
                )
            else:
                category_id = "work"  # Default if no categories
        
        # Submit button
        with cols[3]:
            submitted = st.form_submit_button("Add Task")
        
        if submitted and task:  # Only add if task is not empty
            # Add the task to the database
            add_todo(task, score, category_id)
            
            # Clear the input field by updating session state
            st.session_state.new_task_input = ""
            
            # Set rerun flag to refresh the page
            st.session_state.needs_rerun = True

def display_todo_list(df, categories_df, show_completed=True, completion_timeframe='all'):
    """
    Input: DataFrame with todos, DataFrame with categories, boolean for showing completed tasks,
           string for completion timeframe (all, today, week, month, year)
    Process: Renders todo list with tasks and subtasks
    Output: None
    """
    # Show success message for task deletion if applicable
    if st.session_state.get('last_deleted_task'):
        # st.success(f"Task '{st.session_state.last_deleted_task}' deleted successfully!")
        # Clear the deletion message after showing it
        del st.session_state.last_deleted_task
    
    # Clean up any task_deleted flags that might be lingering
    for key in list(st.session_state.keys()):
        if key.startswith('task_deleted_'):
            del st.session_state[key]
    
    if df.empty:
        st.info("No tasks yet. Add a task to get started!")
        return
    
    # Create a lookup dictionary for categories
    category_lookup = {}
    if not categories_df.empty:
        category_lookup = {row['id']: {'name': row['name'], 'color': row['color']} 
                          for _, row in categories_df.iterrows()}
    
    # Create a copy of the original dataframe for filtering
    filtered_df = df.copy()
    
    # Filter by selected category if not 'all'
    if st.session_state.selected_category != 'all':
        filtered_df = filtered_df[filtered_df['category_id'] == st.session_state.selected_category]
    
    # Apply timeframe filtering to completed tasks
    filtered_df = filter_tasks_by_timeframe(filtered_df, completion_timeframe)
    
    # Filter out completed tasks if show_completed is False
    if not show_completed:
        filtered_df = filtered_df[filtered_df['status'] != 'completed']
    
    if filtered_df.empty:
        message = "No tasks match your current filters."
        if completion_timeframe != 'all':
            timeframe_text = {
                'today': 'today',
                'week': 'this week',
                'month': 'this month',
                'year': 'this year'
            }.get(completion_timeframe, '')
            
            if timeframe_text:
                message = f"No completed tasks {timeframe_text}."
                
        st.info(message)
        return
    
    # Get main tasks (level 0) and sort them: pending first, then completed
    main_tasks = filtered_df[filtered_df['level'] == 0].copy()
    
    # Add a sorting column: 0 for pending tasks, 1 for completed tasks
    main_tasks['sort_order'] = main_tasks['status'].apply(lambda x: 1 if x == 'completed' else 0)
    
    # Sort by sort_order first (pending before completed), then by position
    main_tasks = main_tasks.sort_values(['sort_order', 'position'])
    
    # Display each main task with its subtasks - pass the original df for operations
    for _, task in main_tasks.iterrows():
        display_task(task, df, category_lookup, categories_df)

def display_task(task, df, category_lookup, categories_df, level=0):
    """
    Input: Task row, DataFrame with todos, category lookup dict, categories DataFrame, nesting level
    Process: Renders a task with its subtasks in a compact single-line format
    Output: None
    """
    # Ensure we're working with the original task ID as a string
    task_id = str(task['id'])
    task_text = task['task']
    status = task['status']
    score = task['score']
    category_id = task.get('category_id', 'work')
    position = task.get('position', 0)
    
    # Get category info
    category_name = "Unknown"
    category_color = "#888888"
    if category_id in category_lookup:
        category_name = category_lookup[category_id]['name']
        category_color = category_lookup[category_id]['color']
    
    # Create a container for the task
    with st.container():
        # For edit and subtask forms
        if st.session_state.get(f"edit_mode_{task_id}", False) or st.session_state.get(f"add_subtask_mode_{task_id}", False):
            # Display the forms
            if st.session_state.get(f"edit_mode_{task_id}", False):
                with st.form(key=f"edit_form_{task_id}"):
                    cols = st.columns([3, 1, 1, 1, 1])
                    
                    with cols[0]:
                        edited_task = st.text_input("Edit task", value=task_text, key=f"edit_task_{task_id}")
                    
                    with cols[1]:
                        edited_score = st.selectbox(
                            "Priority",
                            options=[10, 7, 5, 2],
                            format_func=lambda x: SCORE_OPTIONS[x],  # Show the full priority description
                            index=[10, 7, 5, 2].index(score),
                            key=f"edit_score_{task_id}"
                        )
                    
                    with cols[2]:
                        if not categories_df.empty:
                            category_options = {row['id']: row['name'] for _, row in categories_df.iterrows()}
                            edited_category_id = st.selectbox(
                                "Category",
                                options=list(category_options.keys()),
                                format_func=lambda x: category_options[x],
                                index=list(category_options.keys()).index(category_id) if category_id in category_options else 0,
                                key=f"edit_category_{task_id}"
                            )
                        else:
                            edited_category_id = category_id
                    
                    with cols[3]:
                        save = st.form_submit_button("Save")
                    
                    with cols[4]:
                        cancel = st.form_submit_button("Cancel")
                    
                    if save:
                        update_todo(task_id, edited_task, status, edited_score, edited_category_id)
                        st.session_state[f"edit_mode_{task_id}"] = False
                        st.session_state.needs_rerun = True
                    
                    if cancel:
                        st.session_state[f"edit_mode_{task_id}"] = False
                        st.session_state.needs_rerun = True
            
            # Add subtask form
            if st.session_state.get(f"add_subtask_mode_{task_id}", False):
                with st.form(key=f"subtask_form_{task_id}"):
                    cols = st.columns([3, 1, 1, 1])
                    
                    with cols[0]:
                        subtask_text = st.text_input("Enter subtask", key=f"subtask_text_{task_id}", placeholder=f"Subtask for: {task_text[:30]}{'...' if len(task_text) > 30 else ''}")
                    
                    with cols[1]:
                        subtask_score = st.selectbox(
                            "Priority",
                            options=[10, 7, 5, 2],
                            format_func=lambda x: SCORE_OPTIONS[x],  # Show the full priority description
                            index=[10, 7, 5, 2].index(score),  # Default to parent's score
                            key=f"subtask_score_{task_id}"
                        )
                    
                    with cols[2]:
                        add = st.form_submit_button("Add")
                    
                    with cols[3]:
                        cancel = st.form_submit_button("Cancel")
                    
                    if add and subtask_text:
                        add_subtask(task_id, subtask_text, subtask_score, category_id)
                        st.session_state[f"add_subtask_mode_{task_id}"] = False
                        st.session_state.needs_rerun = True
                    
                    if cancel:
                        st.session_state[f"add_subtask_mode_{task_id}"] = False
                        st.session_state.needs_rerun = True
        else:
            # Regular task display
            # Add indentation for subtasks
            indent_margin = level * 20
            
            cols = st.columns([0.05, 2.5, 0.4, 0.15, 0.15, 0.15, 0.15, 0.15, 0.15])
            
            # Priority dot
            with cols[0]:
                if level > 0:
                    # Add connector line for subtasks
                    st.markdown(f"""
                    <div style="position: relative; height: 100%;">
                        <div style="position: absolute; left: {indent_margin-15}px; top: 0; bottom: 0; border-left: 2px solid #555; height: 100%;"></div>
                        <div style="position: absolute; left: {indent_margin-15}px; top: 50%; width: 15px; border-top: 2px solid #555;"></div>
                        <div class="priority-dot" style="background-color: {SCORE_COLORS[score]}; margin-left: {indent_margin}px;"></div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="priority-dot" style="background-color: {SCORE_COLORS[score]};"></div>', unsafe_allow_html=True)
            
            # Task text
            with cols[1]:
                text_style = "text-decoration: line-through;" if status == "completed" else ""
                margin_style = f"margin-left: {indent_margin}px;" if level > 0 else ""
                st.markdown(f'<div style="{text_style} {margin_style}">{task_text}</div>', unsafe_allow_html=True)
            
            # Category badge
            with cols[2]:
                st.markdown(f'<div class="task-category" style="background-color: {category_color};">{category_name}</div>', unsafe_allow_html=True)
            
            # Toggle status button
            with cols[3]:
                if st.button("✓", key=f"toggle_{task_id}", help="Toggle completion status"):
                    new_status = "pending" if status == "completed" else "completed"
                    update_todo(task_id, task_text, new_status, score, category_id)
                    st.session_state.needs_rerun = True
            
            # Edit button
            with cols[4]:
                if st.button("✎", key=f"edit_{task_id}", help="Edit task"):
                    st.session_state[f"edit_mode_{task_id}"] = True
                    st.session_state.needs_rerun = True
            
            # Add subtask button
            with cols[5]:
                if st.button("↳+", key=f"add_subtask_{task_id}", help="Add subtask"):
                    st.session_state[f"add_subtask_mode_{task_id}"] = True
                    st.session_state.needs_rerun = True
            
            # Delete button
            with cols[6]:
                # Check if this task was just deleted and prevent showing the button 
                # if we're in the middle of a rerun from a deletion
                if not st.session_state.get(f"task_deleted_{task_id}", False):
                    if st.button("🗑", key=f"delete_{task_id}", help="Delete task"):
                        # Use the delete_todo function to handle deletion
                        success = delete_todo(task_id)
                        
                        if success:
                            # Mark as deleted
                            st.session_state[f"task_deleted_{task_id}"] = True
                            # Force cache clearing to refresh data
                            st.cache_data.clear()
                            # Set the rerun flag to refresh UI once
                            st.session_state.needs_rerun = True
                            # Add a success message that will be shown after rerun
                            st.session_state.last_deleted_task = task_text[:20] + "..." if len(task_text) > 20 else task_text
                        else:
                            st.error(f"Failed to delete task. Please try again.")
                else:
                    # Show a placeholder where the button would be
                    st.markdown("", unsafe_allow_html=True)
            
            # Move up button
            with cols[7]:
                if st.button("↑", key=f"up_{task_id}", help="Move up"):
                    # Ensure position is an integer
                    try:
                        position_int = int(position)
                        move_todo_up(task_id, position_int, df)
                        st.session_state.needs_rerun = True
                    except Exception as e:
                        st.error(f"Error moving task: {str(e)}")
            
            # Move down button
            with cols[8]:
                if st.button("↓", key=f"down_{task_id}", help="Move down"):
                    # Ensure position is an integer
                    try:
                        position_int = int(position)
                        move_todo_down(task_id, position_int, df)
                        st.session_state.needs_rerun = True
                    except Exception as e:
                        st.error(f"Error moving task: {str(e)}")
    
    # Display subtasks
    # Filter subtasks from the original df to ensure IDs are preserved
    subtasks_df = df[(df['parent_id'] == task_id) & (df['level'] > 0)].copy()
    
    if not subtasks_df.empty:
        # Add a sorting column: 0 for pending tasks, 1 for completed tasks
        subtasks_df['sort_order'] = subtasks_df['status'].apply(lambda x: 1 if x == 'completed' else 0)
        
        # Sort by sort_order first (pending before completed), then by position
        subtasks_df = subtasks_df.sort_values(['sort_order', 'position'])
        
        for _, subtask in subtasks_df.iterrows():
            display_task(subtask, df, category_lookup, categories_df, level=level+1) 