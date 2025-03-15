"""
Logic:
- Connect to Firestore and authenticate with service account from Streamlit secrets
- Initialize Firebase app and Firestore client
- Cache connections for better performance
"""

import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
from utils.helpers import retry_with_backoff

# Initialize Firebase
@st.cache_resource
def get_firebase_app():
    """
    Input: None
    Process: Initializes Firebase app with credentials from Streamlit secrets
    Output: Firebase app instance
    """
    if not firebase_admin._apps:
        try:
            # Get credentials from Streamlit secrets
            firebase_config = st.secrets["firebase"]
            
            # Convert the AttrDict to a regular dictionary
            firebase_config_dict = dict(firebase_config)
            
            # Create a credentials object from the dictionary
            cred = credentials.Certificate(firebase_config_dict)
            
            # Initialize the app
            return firebase_admin.initialize_app(cred)
        except Exception as e:
            # If there's an error with the secrets format, try an alternative approach
            st.error(f"Error initializing Firebase: {str(e)}")
            
            try:
                # Create a temporary JSON file with the credentials
                firebase_config = st.secrets["firebase"]
                temp_cred_path = "/tmp/firebase_credentials.json"
                
                with open(temp_cred_path, "w") as f:
                    json.dump(dict(firebase_config), f)
                
                # Use the file path for credentials
                cred = credentials.Certificate(temp_cred_path)
                
                # Initialize the app
                return firebase_admin.initialize_app(cred)
            except Exception as e2:
                st.error(f"Failed to initialize Firebase with alternative method: {str(e2)}")
                raise
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

@retry_with_backoff(retries=2, backoff_in_seconds=0.5)
def initialize_collection():
    """
    Input: None
    Process: Ensures the todos collection exists
    Output: None
    """
    try:
        # This is a no-op for Firestore as collections are created implicitly
        # But we can use this to check connectivity
        db = get_firestore_db()
        todos_ref = db.collection('todos')
        # Just check if we can access the collection
        todos_ref.limit(1).get()
    except Exception as e:
        st.error(f"Error initializing todos collection: {str(e)}")
        raise 