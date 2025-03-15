"""
Logic:
- Renders the sidebar with statistics and debug information
"""

import streamlit as st
import pandas as pd

def render_sidebar(df):
    """
    Input: DataFrame with todos
    Process: Renders sidebar with statistics and debug information
    Output: None
    """
    with st.sidebar:
        st.title("📊 Statistics")
        
        # Calculate statistics
        if not df.empty:
            total_tasks = len(df)
            completed_tasks = len(df[df['status'] == 'completed'])
            pending_tasks = total_tasks - completed_tasks
            
            # Calculate completion percentage
            completion_percentage = 0
            if total_tasks > 0:
                completion_percentage = int((completed_tasks / total_tasks) * 100)
            
            # Display statistics in cards
            st.markdown(f"""
            <div class="stat-card">
                <h3>Tasks</h3>
                <p>Total: {total_tasks} | Completed: {completed_tasks} | Pending: {pending_tasks}</p>
                <div class="progress-bg" style="height: 8px; width: 100%;">
                    <div class="progress-fill" style="height: 8px; width: {completion_percentage}%;"></div>
                </div>
                <p style="text-align: right; margin-top: 4px;">{completion_percentage}% complete</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Priority distribution
            if 'score' in df.columns:
                priority_counts = df['score'].value_counts().to_dict()
                
                # Ensure all priorities have a count
                for priority in [10, 7, 5, 2]:
                    if priority not in priority_counts:
                        priority_counts[priority] = 0
                
                # Display priority distribution
                st.markdown(f"""
                <div class="stat-card">
                    <h3>Priority Distribution</h3>
                    <p>🔴 Important-Urgent: {priority_counts.get(10, 0)}</p>
                    <p>🟡 Important-Not Urgent: {priority_counts.get(7, 0)}</p>
                    <p>🟢 Not Important-Urgent: {priority_counts.get(5, 0)}</p>
                    <p>⚪ Not Important-Not Urgent: {priority_counts.get(2, 0)}</p>
                </div>
                """, unsafe_allow_html=True)
            
            # Category distribution if available
            if 'category_id' in df.columns and df['category_id'].nunique() > 0:
                category_counts = df['category_id'].value_counts().to_dict()
                
                # Display category distribution
                st.markdown("""
                <div class="stat-card">
                    <h3>Category Distribution</h3>
                """, unsafe_allow_html=True)
                
                for category, count in category_counts.items():
                    st.markdown(f"<p>{category}: {count}</p>", unsafe_allow_html=True)
                
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("No tasks yet. Add some tasks to see statistics.")
        
        # Debug information in an expander
        with st.expander("Debug Info"):
            st.write("Session State:")
            st.write(st.session_state)
            
            st.write("DataFrame Info:")
            if not df.empty:
                st.write(f"Shape: {df.shape}")
                st.write(f"Columns: {df.columns.tolist()}")
            else:
                st.write("DataFrame is empty") 