import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv
import sys
import json
from dataset_handler import (
    check_supabase_storage,
    upload_to_supabase,
    get_from_supabase,
    display_dataset_info,
    get_user_datasets
)

# Initialize session state if not already done
if 'authenticated' not in st.session_state:
    st.warning("Please login to access this page.")
    st.stop()

if not st.session_state.get('authenticated', False):
    st.warning("Please login to access this page.")
    st.stop()

if 'supabase' not in st.session_state:
    st.error("Error: Application not properly initialized. Please return to the home page.")
    st.stop()

# Page config
st.set_page_config(page_title="Dataset Explorer", page_icon="📊")

def get_kaggle_credentials():
    """Get Kaggle credentials from Supabase"""
    try:
        kaggle_config = st.session_state.supabase.table('user_settings').select("*").eq('user_id', st.session_state.user.id).eq('setting_type', 'kaggle').execute()
        if not kaggle_config.data:
            return None, None
        
        settings = kaggle_config.data[0].get('settings', {})
        username = settings.get('username', '')
        key = settings.get('key', '')
        
        if not username or not key:
            return None, None
            
        return username, key
    except Exception as e:
        st.error(f"Error fetching Kaggle credentials: {str(e)}")
        return None, None

def setup_kaggle_credentials():
    """Setup Kaggle credentials from Supabase settings"""
    username, key = get_kaggle_credentials()
    
    if not username or not key:
        st.error("Kaggle credentials not found. Please configure them in the Settings page first.")
        return False
        
    try:
        # Create .kaggle directory if it doesn't exist
        kaggle_dir = os.path.expanduser('~/.kaggle')
        if not os.path.exists(kaggle_dir):
            os.makedirs(kaggle_dir)
        
        # Save credentials to kaggle.json
        kaggle_file = os.path.join(kaggle_dir, 'kaggle.json')
        with open(kaggle_file, 'w') as f:
            json.dump({
                "username": username,
                "key": key
            }, f)
        
        # Set proper permissions
        os.chmod(kaggle_file, 0o600)
        
        # Set environment variables
        os.environ['KAGGLE_USERNAME'] = username
        os.environ['KAGGLE_KEY'] = key
        
        return True
    except Exception as e:
        st.error(f"Error setting up Kaggle credentials: {str(e)}")
        return False

def download_kaggle_dataset(dataset_name):
    """Download dataset from Kaggle"""
    try:
        # Setup Kaggle credentials first
        if not setup_kaggle_credentials():
            return None
            
        # Import kaggle here to avoid early authentication
        import kaggle.api
        from kaggle.api.kaggle_api_extended import KaggleApi
        
        # Initialize the Kaggle API
        api = KaggleApi()
        api.authenticate()
        
        # Download the dataset
        api.dataset_download_files(dataset_name, path='.', unzip=True)
        
        # Find CSV files
        csv_files = [f for f in os.listdir('.') if f.endswith('.csv')]
        return csv_files
    except Exception as e:
        st.error(f"Error downloading from Kaggle: {str(e)}")
        return None

st.title("Dataset Explorer")

# Create tabs for different dataset operations
tab1, tab2 = st.tabs(["Download New Dataset", "Your Datasets"])

with tab1:
    st.header("Download from Kaggle")
    
    # Check if Kaggle credentials are configured
    username, _ = get_kaggle_credentials()
    if not username:
        st.warning("⚠️ Please configure your Kaggle credentials in the Settings page first.")
        if st.button("Go to Settings"):
            st.switch_page("pages/4_Settings.py")  # Updated page reference
        st.stop()
    
    dataset_name = st.text_input(
        "Enter Dataset Name (format: username/dataset-name)",
        help="Example: NUFORC/ufo-sightings or sonalanand/spotify-dataset-for-self-practise"
    )
    
    if st.button("Download Dataset"):
        if dataset_name:
            # First, check if the dataset exists in any form in the user's storage
            try:
                user_datasets = get_user_datasets(st.session_state.supabase, st.session_state.user.id)
                dataset_slug = dataset_name.replace('/', '_')
                existing_dataset = next(
                    (d for d in user_datasets if dataset_slug in d['name']),
                    None
                )
                
                if existing_dataset:
                    st.info("Dataset already exists in your storage. Loading existing version...")
                    df = get_from_supabase(st.session_state.supabase, existing_dataset['path'])
                    if df is not None:
                        display_dataset_info(df, existing_dataset['path'])
                        st.success("Dataset loaded successfully!")
                else:
                    # Dataset doesn't exist, proceed with download
                    with st.spinner("Downloading from Kaggle..."):
                        csv_files = download_kaggle_dataset(dataset_name)
                        if csv_files:
                            csv_file = 'scrubbed.csv' if 'scrubbed.csv' in csv_files else csv_files[0]
                            bucket_path = upload_to_supabase(
                                st.session_state.supabase,
                                st.session_state.user.id,
                                csv_file,
                                dataset_name.replace('/', '_')
                            )
                            if bucket_path:
                                st.success(f"Dataset uploaded successfully!")
                                df = get_from_supabase(st.session_state.supabase, bucket_path)
                                if df is not None:
                                    display_dataset_info(df, bucket_path)
                            
                            # Clean up
                            for file in csv_files:
                                try:
                                    os.remove(file)
                                except Exception as e:
                                    st.warning(f"Could not remove temporary file {file}: {str(e)}")
            except Exception as e:
                st.error(f"Error checking for existing dataset: {str(e)}")
        else:
            st.warning("Please enter a dataset name")

with tab2:
    st.header("Your Datasets")
    datasets = get_user_datasets(st.session_state.supabase, st.session_state.user.id)
    
    if datasets:
        selected_dataset = st.selectbox(
            "Select a dataset",
            options=[d['name'] for d in datasets],
            format_func=lambda x: x.split('/')[-1]
        )
        
        if st.button("Load Dataset"):
            selected_path = next(d['path'] for d in datasets if d['name'] == selected_dataset)
            df = get_from_supabase(st.session_state.supabase, selected_path)
            if df is not None:
                display_dataset_info(df, selected_path)
    else:
        st.info("No datasets uploaded yet. Use the Download New Dataset tab to get started!") 