"""
Logic:
- Provides UI components for category selection and management
- Renders category selector and category management forms
"""

import streamlit as st
import pandas as pd
from database.category_ops import add_category, update_category, delete_category

# Predefined colors for categories
CATEGORY_COLORS = [
    "#FF6B6B",  # Coral Red
    "#4ECDC4",  # Turquoise
    "#45B7D1",  # Sky Blue
    "#FFA62B",  # Orange
    "#A78BFA",  # Purple
    "#16A34A",  # Green
    "#F472B6",  # Pink
    "#FB923C",  # Light Orange
    "#38BDF8",  # Light Blue
    "#4ADE80",  # Light Green
]

def render_category_selector(categories_df):
    """
    Input: DataFrame with categories
    Process: Renders category selector as a dropdown
    Output: Selected category ID
    """
    # Create category options for dropdown
    category_options = {"all": "All Categories"}
    
    # Add categories from DataFrame
    if not categories_df.empty:
        for _, row in categories_df.iterrows():
            category_options[row['id']] = row['name']
    
    # Create the dropdown
    selected_category = st.selectbox(
        "Filter by Category",
        options=list(category_options.keys()),
        format_func=lambda x: category_options[x],
        key="category_selector"
    )
    
    # Update session state if changed
    if selected_category != st.session_state.selected_category:
        st.session_state.selected_category = selected_category
        st.session_state.needs_rerun = True
    
    return st.session_state.selected_category

def display_category_management(categories_df):
    """
    Input: DataFrame with categories
    Process: Renders category management UI
    Output: None
    """
    st.markdown('<div class="category-manager">', unsafe_allow_html=True)
    st.subheader("Category Management")
    
    # Add new category form
    with st.form(key="add_category_form"):
        st.markdown("#### Add New Category")
        new_category_name = st.text_input("Category Name", key="new_category_name")
        
        # Color selection
        st.markdown("Select Color:")
        color_cols = st.columns(5)
        
        # Initialize selected color in session state if not exists
        if 'selected_color' not in st.session_state:
            st.session_state.selected_color = CATEGORY_COLORS[0]
        
        # Display color options
        for i, color in enumerate(CATEGORY_COLORS):
            col_idx = i % 5
            with color_cols[col_idx]:
                # Check if this color is selected
                is_selected = st.session_state.selected_color == color
                selected_class = "selected" if is_selected else ""
                
                # Create a clickable color option
                st.markdown(
                    f"""
                    <div 
                        class="color-option {selected_class}" 
                        style="background-color: {color};"
                        onclick="
                            document.querySelectorAll('.color-option').forEach(el => el.classList.remove('selected'));
                            this.classList.add('selected');
                            window.parent.postMessage({{
                                type: 'streamlit:setComponentValue',
                                value: '{color}',
                                dataType: 'string',
                                key: 'selected_color'
                            }}, '*');
                        "
                    ></div>
                    """,
                    unsafe_allow_html=True
                )
        
        # Submit button
        submitted = st.form_submit_button("Add Category")
        
        if submitted and new_category_name:
            # Add the category
            add_category(new_category_name, st.session_state.selected_color)
            
            # Clear the input
            st.session_state.new_category_name = ""
            
            # Set rerun flag
            st.session_state.needs_rerun = True
    
    # Display existing categories with edit/delete options
    if not categories_df.empty:
        st.markdown("#### Existing Categories")
        
        for _, row in categories_df.iterrows():
            category_id = row['id']
            category_name = row['name']
            category_color = row['color']
            
            # Create a container for each category
            with st.container():
                cols = st.columns([0.1, 0.6, 0.15, 0.15])
                
                # Color preview
                with cols[0]:
                    st.markdown(
                        f'<div class="category-color-preview" style="background-color: {category_color};"></div>',
                        unsafe_allow_html=True
                    )
                
                # Category name
                with cols[1]:
                    st.markdown(f"**{category_name}**")
                
                # Edit button
                with cols[2]:
                    if st.button("Edit", key=f"edit_cat_{category_id}"):
                        st.session_state[f"edit_category_{category_id}"] = True
                        st.session_state[f"edit_category_name_{category_id}"] = category_name
                        st.session_state[f"edit_category_color_{category_id}"] = category_color
                        st.session_state.needs_rerun = True
                
                # Delete button
                with cols[3]:
                    if st.button("Delete", key=f"delete_cat_{category_id}"):
                        delete_category(category_id)
                        st.session_state.needs_rerun = True
            
            # Edit form (conditionally displayed)
            if st.session_state.get(f"edit_category_{category_id}", False):
                with st.form(key=f"edit_category_form_{category_id}"):
                    # Name input
                    edit_name = st.text_input(
                        "Category Name", 
                        value=st.session_state[f"edit_category_name_{category_id}"],
                        key=f"edit_name_{category_id}"
                    )
                    
                    # Color selection
                    st.markdown("Select Color:")
                    edit_color_cols = st.columns(5)
                    
                    # Initialize edit color in session state if not exists
                    if f'edit_category_color_{category_id}' not in st.session_state:
                        st.session_state[f'edit_category_color_{category_id}'] = category_color
                    
                    # Display color options
                    for i, color in enumerate(CATEGORY_COLORS):
                        col_idx = i % 5
                        with edit_color_cols[col_idx]:
                            # Check if this color is selected
                            is_selected = st.session_state[f'edit_category_color_{category_id}'] == color
                            selected_class = "selected" if is_selected else ""
                            
                            # Create a clickable color option
                            st.markdown(
                                f"""
                                <div 
                                    class="color-option {selected_class}" 
                                    style="background-color: {color};"
                                    onclick="
                                        document.querySelectorAll('.color-option').forEach(el => el.classList.remove('selected'));
                                        this.classList.add('selected');
                                        window.parent.postMessage({{
                                            type: 'streamlit:setComponentValue',
                                            value: '{color}',
                                            dataType: 'string',
                                            key: 'edit_category_color_{category_id}'
                                        }}, '*');
                                    "
                                ></div>
                                """,
                                unsafe_allow_html=True
                            )
                    
                    # Submit and cancel buttons
                    col1, col2 = st.columns(2)
                    with col1:
                        save = st.form_submit_button("Save")
                    with col2:
                        cancel = st.form_submit_button("Cancel")
                    
                    if save:
                        # Update the category
                        update_category(
                            category_id, 
                            edit_name, 
                            st.session_state[f'edit_category_color_{category_id}']
                        )
                        
                        # Clear edit state
                        st.session_state[f"edit_category_{category_id}"] = False
                        
                        # Set rerun flag
                        st.session_state.needs_rerun = True
                    
                    if cancel:
                        # Clear edit state
                        st.session_state[f"edit_category_{category_id}"] = False
                        
                        # Set rerun flag
                        st.session_state.needs_rerun = True
    
    st.markdown('</div>', unsafe_allow_html=True) 