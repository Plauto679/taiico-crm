import pandas as pd
from config import USERS_DB
import os

def verify_credentials(username, password):
    """
    Verify username and password against the Excel file.
    """
    if not os.path.exists(USERS_DB):
        print(f"Users DB not found at: {USERS_DB}")
        return False

    try:
        df = pd.read_excel(USERS_DB)
        
        # Ensure columns exist (case insensitive search if needed, but assuming exact match based on request)
        # Request said 'Usuario' and 'Password' columns
        
        # Simple exact match
        user_match = df[df['Usuario'] == username]
        
        if user_match.empty:
            return False
            
        # Check password
        # Assuming plain text passwords as per the simple requirement, 
        # but in production this should be hashed.
        stored_password = user_match.iloc[0]['Password']
        
        # Handle potential type mismatch (e.g. if password is a number)
        return str(stored_password) == str(password)
        
    except Exception as e:
        print(f"Error verifying credentials: {e}")
        return False
