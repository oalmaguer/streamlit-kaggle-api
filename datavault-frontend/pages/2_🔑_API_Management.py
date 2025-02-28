import streamlit as st
import requests
import pandas as pd
import os
from dataset_handler import get_user_datasets

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
st.set_page_config(page_title="API Management", page_icon="🔑")

# Get API base URL
API_BASE_URL = st.secrets.get("API_BASE_URL", os.getenv('API_BASE_URL', 'http://localhost:5000'))

st.title("API Management")

# Create tabs for different API operations
tab1, tab2, tab3 = st.tabs(["API Keys", "Live Example", "Documentation"])

with tab1:
    st.header("Your API Keys")
    
    # Show existing API keys
    try:
        api_keys = st.session_state.supabase.table('api_keys').select("*").eq('user_id', st.session_state.user.id).execute()
        if api_keys.data:
            st.subheader("Active API Keys")
            for key in api_keys.data:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.code(key['key'], language=None)
                    created_at = pd.to_datetime(key['created_at']).strftime("%Y-%m-%d %H:%M:%S")
                    st.caption(f"Created: {created_at}")
        
        if st.button("Generate New API Key"):
            try:
                # Get current session token
                session = st.session_state.supabase.auth.get_session()
                token = session.access_token
                
                # Call API to generate new key
                response = requests.post(
                    f"{API_BASE_URL}/api/generate-key",
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    st.success("New API Key Generated!")
                    st.code(data['api_key'], language=None)
                    st.warning(data['message'])
                    st.rerun()  # Refresh to show new key in list
                else:
                    st.error(f"Failed to generate API key: {response.json().get('error', 'Unknown error')}")
            except Exception as e:
                st.error(f"Error: {str(e)}")
    except Exception as e:
        st.error(f"Error fetching API keys: {str(e)}")

with tab2:
    st.header("Live API Example")
    
    # Get user's datasets using the dataset_handler function
    try:
        datasets = get_user_datasets(st.session_state.supabase, st.session_state.user.id)
        if datasets:
            # Get the first API key
            api_key = api_keys.data[0]['key'] if api_keys.data else None
            
            if api_key:
                st.subheader("Try it now!")
                st.markdown("This example will fetch the first 5 rows of your selected dataset using the API.")
                
                # Dataset selection with better formatting
                selected_dataset = st.selectbox(
                    "Select a dataset",
                    options=[d['name'] for d in datasets],
                    format_func=lambda x: x.split('/')[-1]  # Show only filename
                )
                
                if selected_dataset:
                    # Get the full path for the selected dataset
                    selected_path = next(d['path'] for d in datasets if d['name'] == selected_dataset)
                    
                    # Show the API call with the actual path
                    st.markdown("#### API Call")
                    st.markdown("```python\nimport requests\n\n" + 
                        f"api_url = '{API_BASE_URL}/api/data/head'\n" +
                        f"headers = {{'X-API-Key': '{api_key}'}}\n" +
                        f"params = {{'bucket_path': '{selected_path}', 'n': 5}}\n\n" +
                        "response = requests.get(api_url, headers=headers, params=params)\n" +
                        "data = response.json()\n```")
                    
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        execute_call = st.button("Execute API Call")
                    with col2:
                        st.markdown("👈 Click to test the API with your selected dataset")
                    
                    if execute_call:
                        with st.spinner("Making API call..."):
                            try:
                                response = requests.get(
                                    f"{API_BASE_URL}/api/data/head",
                                    headers={"X-API-Key": api_key},
                                    params={"bucket_path": selected_path, "n": 5}
                                )
                                
                                if response.status_code == 200:
                                    st.success("API call successful!")
                                    st.json(response.json())
                                else:
                                    st.error(f"API call failed: {response.json().get('error', 'Unknown error')}")
                            except Exception as e:
                                st.error(f"Error executing API call: {str(e)}")
            else:
                st.warning("Please generate an API key first in the 'API Keys' tab.")
        else:
            st.info("No datasets found. Please upload a dataset first in the Dataset Explorer.")
    except Exception as e:
        st.error(f"Error loading datasets: {str(e)}")

with tab3:
    st.header("API Documentation")
    
    if st.button("Load API Documentation"):
        try:
            response = requests.get(f"{API_BASE_URL}/api/docs/{st.session_state.user.id}")
            if response.status_code == 200:
                docs = response.json()
                
                st.subheader("Base Information")
                st.markdown(f"**Base URL:** `{docs['base_url']}`")
                
                st.subheader("Authentication")
                st.markdown(f"""
                - Type: {docs['authentication']['type']}
                - Header: `{docs['authentication']['header']}`
                - {docs['authentication']['note']}
                """)
                
                st.subheader("Available Endpoints")
                for endpoint, details in docs['endpoints'].items():
                    with st.expander(f"🔗 {endpoint}"):
                        st.markdown(f"""
                        **Description:** {details['description']}
                        
                        **Parameters:** {', '.join(details['parameters'])}
                        
                        **Example:**
                        ```
                        {details['example']}
                        ```
                        """)
                
                if docs['available_datasets']:
                    st.subheader("Your Available Datasets")
                    for dataset in docs['available_datasets']:
                        st.code(dataset, language=None)
                else:
                    st.info("No datasets uploaded yet. Upload a dataset to see it here.")
                
                # Show Python example
                st.subheader("Python Code Example")
                example_dataset = docs['available_datasets'][0] if docs['available_datasets'] else "your_dataset_path"
                api_key = api_keys.data[0]['key'] if api_keys.data else "YOUR_API_KEY"
                
                st.code(f"""
import requests

headers = {{
    'X-API-Key': '{api_key}'  # Your API key
}}

# Get dataset summary
response = requests.get(
    '{API_BASE_URL}/api/data/summary',
    headers=headers,
    params={{'bucket_path': '{example_dataset}'}}
)
print(response.json())

# Get first 5 rows
response = requests.get(
    '{API_BASE_URL}/api/data/head',
    headers=headers,
    params={{
        'bucket_path': '{example_dataset}',
        'n': 5
    }}
)
print(response.json())
                """, language='python')
                
        except Exception as e:
            st.error(f"Error fetching API documentation: {str(e)}") 