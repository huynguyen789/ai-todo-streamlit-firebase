"""
Logic:
- Provides UI components for todo items
- Renders todo list with add/edit/delete functionality
- Supports subtasks with parent-child relationships
"""

import streamlit as st
import pandas as pd
from database.category_ops import SCORE_OPTIONS, SCORE_COLORS
from database.todo_operations import add_todo, update_todo, delete_todo, move_todo_up, move_todo_down, add_subtask

def display_add_todo_form(categories_df):
    """
    Input: DataFrame with categories
    Process: Renders compact form for adding new todo items
    Output: None
    """
    st.subheader("Add New Task")
    
    # Initialize task input in session state if not exists
    if 'new_task_input' not in st.session_state:
        st.session_state.new_task_input = ""
    
    with st.form(key="add_form", clear_on_submit=True):
        cols = st.columns([3, 1, 1, 1])
        
        # Task input
        with cols[0]:
            task = st.text_input("Task", value=st.session_state.new_task_input, key="task_input_field", placeholder="Enter task description")
        
        # Score selection
        with cols[1]:
            score = st.selectbox(
                "Priority",
                options=[10, 7, 5, 2],
                format_func=lambda x: SCORE_OPTIONS[x].split(" ")[0],  # Just show the emoji and importance
                key="new_score"
            )
        
        # Category selection
        with cols[2]:
            if not categories_df.empty:
                category_options = {row['id']: row['name'] for _, row in categories_df.iterrows()}
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

def display_todo_list(df, categories_df, show_completed=True):
    """
    Input: DataFrame with todos, DataFrame with categories, boolean for showing completed tasks
    Process: Renders todo list with tasks and subtasks
    Output: None
    """
    if df.empty:
        st.info("No tasks yet. Add a task to get started!")
        return
    
    # Create a lookup dictionary for categories
    category_lookup = {}
    if not categories_df.empty:
        category_lookup = {row['id']: {'name': row['name'], 'color': row['color']} 
                          for _, row in categories_df.iterrows()}
    
    # Filter by selected category if not 'all'
    if st.session_state.selected_category != 'all':
        df = df[df['category_id'] == st.session_state.selected_category]
    
    # Filter out completed tasks if show_completed is False
    if not show_completed:
        df = df[df['status'] != 'completed']
    
    if df.empty:
        st.info("No tasks match your current filters.")
        return
    
    # Get main tasks (level 0)
    main_tasks = df[df['level'] == 0].sort_values('position')
    
    # Display each main task with its subtasks
    for _, task in main_tasks.iterrows():
        display_task(task, df, category_lookup, categories_df)

def display_task(task, df, category_lookup, categories_df, level=0):
    """
    Input: Task row, DataFrame with todos, category lookup dict, categories DataFrame, nesting level
    Process: Renders a task with its subtasks in a compact single-line format
    Output: None
    """
    task_id = task['id']
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
                        edited_task = st.text_input("Edit Task", value=task_text, key=f"edit_task_{task_id}")
                    
                    with cols[1]:
                        edited_score = st.selectbox(
                            "Priority",
                            options=[10, 7, 5, 2],
                            format_func=lambda x: SCORE_OPTIONS[x].split(" ")[0],
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
                        subtask_text = st.text_input("Subtask", key=f"subtask_text_{task_id}", placeholder="Enter subtask")
                    
                    with cols[1]:
                        subtask_score = st.selectbox(
                            "Priority",
                            options=[10, 7, 5, 2],
                            format_func=lambda x: SCORE_OPTIONS[x].split(" ")[0],
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
            cols = st.columns([0.05, 2.5, 0.4, 0.15, 0.15, 0.15, 0.15, 0.15, 0.15])
            
            # Priority dot
            with cols[0]:
                st.markdown(f'<div class="priority-dot" style="background-color: {SCORE_COLORS[score]};"></div>', unsafe_allow_html=True)
            
            # Task text
            with cols[1]:
                text_style = "text-decoration: line-through;" if status == "completed" else ""
                st.markdown(f'<div style="{text_style}">{task_text}</div>', unsafe_allow_html=True)
            
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
                if st.button("+", key=f"add_subtask_{task_id}", help="Add subtask"):
                    st.session_state[f"add_subtask_mode_{task_id}"] = True
                    st.session_state.needs_rerun = True
            
            # Delete button
            with cols[6]:
                if st.button("🗑", key=f"delete_{task_id}", help="Delete task"):
                    delete_todo(task_id)
                    st.session_state.needs_rerun = True
            
            # Move up button
            with cols[7]:
                if st.button("↑", key=f"up_{task_id}", help="Move up"):
                    move_todo_up(task_id, position, df)
                    st.session_state.needs_rerun = True
            
            # Move down button
            with cols[8]:
                if st.button("↓", key=f"down_{task_id}", help="Move down"):
                    move_todo_down(task_id, position, df)
                    st.session_state.needs_rerun = True
    
    # Display subtasks
    subtasks = df[(df['parent_id'] == task_id) & (df['level'] > 0)].sort_values('position')
    for _, subtask in subtasks.iterrows():
        display_task(subtask, df, category_lookup, categories_df, level=level+1) 