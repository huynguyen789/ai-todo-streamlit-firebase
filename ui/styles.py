"""
Logic:
- Provides CSS styling for the Todo app
- Includes styles for task items, forms, buttons, and other UI components
"""

import streamlit as st

def apply_custom_css():
    """
    Input: None
    Process: Applies custom CSS styling to the Streamlit app
    Output: None
    """
    st.markdown("""
    <style>
        /* Main container styling */
        .main .block-container {
            padding-top: 1rem;
            padding-bottom: 1rem;
        }
        
        /* Clean task list styling */
        .task-item {
            display: flex;
            align-items: center;
            padding: 0.5rem;
            margin-bottom: 0.25rem;
            background-color: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
            transition: all 0.2s ease;
            position: relative;
        }
        .task-item:hover {
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
            background-color: rgba(255, 255, 255, 0.15);
        }
        
        /* Priority dot */
        .priority-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 8px;
            flex-shrink: 0;
        }
        
        /* Task text */
        .task-text {
            flex-grow: 1;
            margin-right: 8px;
            font-size: 0.95rem;
            word-break: break-word;
        }
        
        /* Category badge */
        .task-category {
            padding: 2px 6px;
            border-radius: 10px;
            font-size: 0.7rem;
            color: white;
            margin-left: 4px;
            white-space: nowrap;
            text-align: center;
        }
        
        /* Completed task styling */
        .completed-task {
            text-decoration: line-through;
            color: #888;
        }
        
        /* Add form styling */
        .add-form {
            background-color: rgba(255, 255, 255, 0.05);
            padding: 1rem;
            border-radius: 6px;
            margin-bottom: 1rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }
        
        /* Subtask styling with indentation and connecting lines */
        .subtask {
            margin-left: 20px;
            position: relative;
        }
        .subtask:before {
            content: "";
            position: absolute;
            left: -15px;
            top: 0;
            height: 100%;
            width: 2px;
            background-color: #555;
        }
        .subtask:after {
            content: "";
            position: absolute;
            left: -15px;
            top: 50%;
            width: 15px;
            height: 2px;
            background-color: #555;
        }
        
        /* Button styling */
        .stButton button {
            border-radius: 4px;
            padding: 0px 4px;
            font-size: 0.75rem;
            transition: all 0.2s ease;
            min-height: 30px;
            line-height: 1;
        }
        .stButton button:hover {
            transform: translateY(-1px);
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
        }
        
        /* Sidebar styling */
        .css-1d391kg, .css-163ttbj, .css-1r6slb0 {
            background-color: rgba(255, 255, 255, 0.05);
        }
        
        /* Statistics cards */
        .stat-card {
            background-color: rgba(255, 255, 255, 0.05);
            padding: 0.75rem;
            border-radius: 6px;
            margin-bottom: 0.75rem;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
        }
        .stat-card h3 {
            margin-top: 0;
            margin-bottom: 0.4rem;
            font-size: 1rem;
            color: #fff;
        }
        .stat-card p {
            margin: 0.2rem 0;
            font-size: 0.85rem;
        }
        
        /* Progress bar */
        .progress-bg {
            background-color: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
            overflow: hidden;
            margin: 0.4rem 0;
        }
        .progress-fill {
            background-color: #4CAF50;
            border-radius: 4px;
        }
        
        /* Category selector */
        .category-selector {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-bottom: 0.75rem;
        }
        .category-selector button {
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.75rem;
            border: none;
            color: white;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .category-selector button:hover {
            opacity: 0.9;
            transform: translateY(-1px);
        }
        
        /* Category management */
        .category-manager {
            background-color: rgba(255, 255, 255, 0.05);
            padding: 0.75rem;
            border-radius: 6px;
            margin-bottom: 1rem;
        }
        .category-item {
            display: flex;
            align-items: center;
            padding: 0.4rem;
            margin-bottom: 0.4rem;
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 4px;
        }
        .category-color-preview {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 6px;
        }
        
        /* Color picker styling */
        .color-picker {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin: 0.4rem 0;
        }
        .color-option {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            cursor: pointer;
            transition: transform 0.2s ease;
        }
        .color-option:hover {
            transform: scale(1.2);
        }
        .color-option.selected {
            border: 2px solid white;
        }
        
        /* Inline edit form */
        .inline-edit-form, .inline-subtask-form {
            background-color: rgba(255, 255, 255, 0.1);
            padding: 0.75rem;
            border-radius: 4px;
            margin: 0.4rem 0;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }
        
        /* Streamlit form styling */
        div[data-testid="stForm"] {
            background-color: rgba(255, 255, 255, 0.05);
            padding: 0.75rem;
            border-radius: 6px;
            margin-bottom: 0.75rem;
        }
        
        /* Input field styling */
        div[data-baseweb="input"] input, div[data-baseweb="textarea"] textarea {
            background-color: rgba(255, 255, 255, 0.1);
            border-color: rgba(255, 255, 255, 0.2);
        }
        
        /* Select box styling */
        div[data-baseweb="select"] {
            background-color: rgba(255, 255, 255, 0.1);
        }
        
        /* Checkbox styling */
        label[data-baseweb="checkbox"] {
            gap: 8px;
        }
        
        /* Toggle styling */
        div[data-testid="stToggle"] {
            margin-bottom: 0.75rem;
        }
        
        /* Expander styling */
        details[data-testid="stExpander"] {
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 6px;
            overflow: hidden;
        }
        details[data-testid="stExpander"] summary {
            padding: 0.5rem;
            font-weight: 600;
        }
        
        /* Horizontal rule styling */
        hr {
            margin: 1.5rem 0;
            border-color: rgba(255, 255, 255, 0.1);
        }
        
        /* Subtask connector lines */
        .subtask-connector {
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 2px;
            background-color: #555;
        }
        .subtask-connector:before {
            content: "";
            position: absolute;
            left: 0;
            top: 50%;
            width: 8px;
            height: 2px;
            background-color: #555;
        }
        
        /* Task action buttons */
        .task-actions {
            display: flex;
            gap: 4px;
        }
        .task-actions button {
            padding: 0px 4px;
            font-size: 0.7rem;
            min-width: 24px;
        }
        
        /* Compact forms */
        .compact-form {
            padding: 0.5rem;
            margin-bottom: 0.5rem;
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 4px;
        }
        
        /* Subtask styling */
        .subtask-item {
            position: relative;
            padding-left: 20px;
        }
        
        /* Subtask connector styling */
        .subtask-line {
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 2px;
            background-color: #555;
        }
        
        .subtask-branch {
            position: absolute;
            left: 0;
            top: 50%;
            width: 15px;
            height: 2px;
            background-color: #555;
        }
        
        /* Responsive adjustments */
        @media (max-width: 768px) {
            .task-item {
                flex-direction: column;
                align-items: flex-start;
            }
            .task-text {
                margin-bottom: 0.4rem;
            }
            .task-actions {
                width: 100%;
                justify-content: space-between;
            }
        }
        
        /* Tooltip styling */
        div[data-baseweb="tooltip"] {
            background-color: #333;
            color: white;
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 0.75rem;
        }
        
        /* Scrollbar styling */
        ::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        ::-webkit-scrollbar-track {
            background: rgba(255, 255, 255, 0.05);
        }
        ::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.2);
            border-radius: 3px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(255, 255, 255, 0.3);
        }
        
        /* Focus styling */
        *:focus {
            outline: 1px solid rgba(255, 255, 255, 0.3);
            outline-offset: 1px;
        }
        
        /* Animation for new tasks */
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(5px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .new-task {
            animation: fadeIn 0.2s ease-out;
        }
        
        /* Compact form labels */
        label {
            font-size: 0.85rem;
            margin-bottom: 0.2rem;
        }
        
        /* Compact headings */
        h1 {
            font-size: 1.8rem;
            margin-bottom: 1rem;
        }
        h2 {
            font-size: 1.5rem;
            margin-bottom: 0.75rem;
        }
        h3 {
            font-size: 1.2rem;
            margin-bottom: 0.5rem;
        }
        h4 {
            font-size: 1rem;
            margin-bottom: 0.4rem;
        }
    </style>
    """, unsafe_allow_html=True) 