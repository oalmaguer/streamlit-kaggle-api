import streamlit as st
import os
import json
import sys
import pandas as pd
import requests
from datetime import datetime

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

def ensure_user_settings_table():
    """Create user_settings table if it doesn't exist"""
    try:
        # Check if table exists
        result = st.session_state.supabase.table('user_settings').select("count").limit(1).execute()
        return True
    except Exception as e:
        if "'42P01'" in str(e):  # Table doesn't exist error
            try:
                # Create the table using SQL
                sql = """
                create table if not exists public.user_settings (
                    id uuid default uuid_generate_v4() primary key,
                    user_id uuid references auth.users(id) not null,
                    setting_type text not null,
                    settings jsonb not null default '{}'::jsonb,
                    created_at timestamp with time zone default timezone('utc'::text, now()) not null,
                    updated_at timestamp with time zone default timezone('utc'::text, now()) not null,
                    constraint user_settings_user_type_unique unique (user_id, setting_type)
                );

                -- Set up RLS (Row Level Security)
                alter table public.user_settings enable row level security;

                -- Create policy to allow users to read their own settings
                create policy "Users can read their own settings"
                    on public.user_settings for select
                    using (auth.uid() = user_id);

                -- Create policy to allow users to insert their own settings
                create policy "Users can insert their own settings"
                    on public.user_settings for insert
                    with check (auth.uid() = user_id);

                -- Create policy to allow users to update their own settings
                create policy "Users can update their own settings"
                    on public.user_settings for update
                    using (auth.uid() = user_id);
                """
                
                # Execute the SQL through REST API since Supabase Python client doesn't support raw SQL
                url = f"{st.secrets.get('SUPABASE_URL')}/rest/v1/rpc/create_user_settings_table"
                headers = {
                    'apikey': st.secrets.get('SUPABASE_KEY'),
                    'Authorization': f"Bearer {st.secrets.get('SUPABASE_KEY')}",
                    'Content-Type': 'application/json',
                    'Prefer': 'return=minimal'
                }
                response = requests.post(url, headers=headers)
                
                if response.status_code in [200, 201]:
                    st.success("✅ User settings table created successfully!")
                    return True
                else:
                    st.error(f"Failed to create table: {response.text}")
                    return False
            except Exception as create_error:
                st.error(f"Error creating table: {str(create_error)}")
                return False
        else:
            st.error(f"Error checking table: {str(e)}")
            return False

# Page config
st.set_page_config(page_title="Settings", page_icon="⚙️")

st.title("Settings")

# Ensure the user_settings table exists
if not ensure_user_settings_table():
    st.error("Could not initialize settings storage. Please contact support.")
    st.stop()

# Create tabs for different settings
tab1, tab2, tab3 = st.tabs(["Kaggle Settings", "API Settings", "Debug Information"])

with tab1:
    st.header("Kaggle Configuration")
    
    # Show current Kaggle settings
    st.subheader("Current Configuration")
    
    # Try to get existing Kaggle credentials from Supabase
    try:
        kaggle_config = st.session_state.supabase.table('user_settings').select("*").eq('user_id', st.session_state.user.id).eq('setting_type', 'kaggle').execute()
        if not kaggle_config.data:
            current_username = ""
            current_key = ""
            has_config = False
        else:
            settings = kaggle_config.data[0].get('settings', {})
            current_username = settings.get('username', '')
            current_key = settings.get('key', '')
            has_config = bool(current_username and current_key)
    except Exception as e:
        st.error(f"Error fetching Kaggle configuration: {str(e)}")
        current_username = ""
        current_key = ""
        has_config = False
    
    if has_config:
        st.success("✅ Kaggle credentials are configured")
        st.info(f"Current username: {current_username}")
        
        # Add delete credentials button
        if st.button("🗑️ Delete Kaggle Credentials", type="secondary", help="Remove your stored Kaggle credentials"):
            try:
                # Delete from Supabase
                result = st.session_state.supabase.table('user_settings').delete().eq('user_id', st.session_state.user.id).eq('setting_type', 'kaggle').execute()
                
                # Remove local kaggle.json if it exists
                kaggle_file = os.path.expanduser('~/.kaggle/kaggle.json')
                if os.path.exists(kaggle_file):
                    os.remove(kaggle_file)
                
                # Clear environment variables
                if 'KAGGLE_USERNAME' in os.environ:
                    del os.environ['KAGGLE_USERNAME']
                if 'KAGGLE_KEY' in os.environ:
                    del os.environ['KAGGLE_KEY']
                
                st.success("✅ Kaggle credentials deleted successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Error deleting credentials: {str(e)}")
    else:
        st.warning("❌ Kaggle credentials are not configured")
    
    st.markdown("""
    ### How to Get Kaggle Credentials
    
    1. Go to [Kaggle.com](https://www.kaggle.com)
    2. Log in to your account
    3. Click on your profile picture → Account
    4. Scroll down to the API section
    5. Click "Create New API Token"
    6. A `kaggle.json` file will be downloaded
    """)
    
    # Input fields for Kaggle credentials
    st.subheader("Update Kaggle Credentials")
    
    with st.form("kaggle_credentials_form"):
        kaggle_username = st.text_input(
            "Kaggle Username",
            value=current_username,
            help="Enter your Kaggle username from the kaggle.json file"
        )
        
        kaggle_key = st.text_input(
            "Kaggle API Key",
            value=current_key,
            type="password",
            help="Enter your Kaggle API key from the kaggle.json file"
        )
        
        col1, col2 = st.columns([1, 2])
        with col1:
            submit_button = st.form_submit_button("Save Credentials")
        with col2:
            if submit_button:
                if not kaggle_username or not kaggle_key:
                    st.error("Please enter both username and API key")
                else:
                    try:
                        # Prepare settings data
                        settings_data = {
                            'user_id': st.session_state.user.id,
                            'setting_type': 'kaggle',
                            'settings': {
                                'username': kaggle_username,
                                'key': kaggle_key,
                                'updated_at': datetime.utcnow().isoformat()
                            }
                        }
                        
                        # First test if the credentials work
                        try:
                            # Create .kaggle directory if it doesn't exist
                            kaggle_dir = os.path.expanduser('~/.kaggle')
                            if not os.path.exists(kaggle_dir):
                                os.makedirs(kaggle_dir)
                            
                            # Save credentials to kaggle.json
                            kaggle_file = os.path.join(kaggle_dir, 'kaggle.json')
                            with open(kaggle_file, 'w') as f:
                                json.dump({
                                    "username": kaggle_username,
                                    "key": kaggle_key
                                }, f)
                            
                            # Set proper permissions
                            os.chmod(kaggle_file, 0o600)
                            
                            # Test authentication
                            import kaggle
                            kaggle.api.authenticate()
                            
                            # If we get here, authentication worked, now save to Supabase
                            if has_config:
                                # Update existing record
                                result = st.session_state.supabase.table('user_settings').update(settings_data).eq('user_id', st.session_state.user.id).eq('setting_type', 'kaggle').execute()
                                if not result.data:
                                    raise Exception("No rows were updated in Supabase")
                            else:
                                # Insert new record
                                result = st.session_state.supabase.table('user_settings').insert(settings_data).execute()
                                if not result.data:
                                    raise Exception("No rows were inserted into Supabase")
                            
                            st.success("✅ Kaggle credentials saved and verified successfully!")
                            
                            # Set environment variables
                            os.environ['KAGGLE_USERNAME'] = kaggle_username
                            os.environ['KAGGLE_KEY'] = kaggle_key
                            
                            # Force a rerun to update the UI
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"❌ Kaggle authentication failed: {str(e)}")
                            # Clean up the kaggle.json file if it exists
                            try:
                                if os.path.exists(kaggle_file):
                                    os.remove(kaggle_file)
                            except:
                                pass
                        
                    except Exception as e:
                        st.error(f"Error saving to Supabase: {str(e)}")
    
    # Show current environment variables
    with st.expander("Environment Variables"):
        st.code(f"""
KAGGLE_USERNAME={os.getenv('KAGGLE_USERNAME', 'Not set')}
KAGGLE_KEY={'*' * 8 if os.getenv('KAGGLE_KEY') else 'Not set'}
        """)

with tab2:
    st.header("API Configuration")
    
    # Show current API settings
    st.subheader("Current Configuration")
    api_base_url = st.secrets.get("API_BASE_URL", os.getenv('API_BASE_URL', 'http://localhost:5000'))
    
    # Get user's subdomain configuration
    try:
        subdomain_config = st.session_state.supabase.table('user_settings').select("*").eq('user_id', st.session_state.user.id).eq('setting_type', 'api_config').execute()
        current_subdomain = subdomain_config.data[0].get('settings', {}).get('subdomain', '') if subdomain_config.data else ''
        has_subdomain = bool(current_subdomain)
    except Exception as e:
        st.error(f"Error fetching subdomain configuration: {str(e)}")
        current_subdomain = ''
        has_subdomain = False
    
    # Show current subdomain status
    if has_subdomain:
        st.success("✅ Custom subdomain configured")
        user_api_url = f"https://{current_subdomain}.{api_base_url.replace('https://', '')}"
        st.info(f"Your API URL: {user_api_url}")
    else:
        st.warning("⚠️ No custom subdomain configured")
    
    # Subdomain management form
    st.subheader("Configure Custom Subdomain")
    with st.form("subdomain_form"):
        new_subdomain = st.text_input(
            "Custom Subdomain",
            value=current_subdomain,
            help="Enter your desired subdomain (e.g., 'myapi' will give you 'myapi.your-api.domain.com')",
            placeholder="myapi"
        )
        
        # Add validation hints
        st.caption("""
        Subdomain requirements:
        - Only lowercase letters, numbers, and hyphens
        - Must start with a letter
        - Between 3-20 characters
        - No special characters or spaces
        """)
        
        col1, col2 = st.columns([1, 2])
        with col1:
            submit_button = st.form_submit_button("Save Subdomain")
        
        if submit_button:
            if new_subdomain:
                # Validate subdomain format
                import re
                if not re.match(r'^[a-z][a-z0-9-]{2,19}$', new_subdomain):
                    st.error("Invalid subdomain format. Please follow the requirements above.")
                else:
                    try:
                        # Check if subdomain is available
                        existing = st.session_state.supabase.table('user_settings').select("*").eq('settings->>subdomain', new_subdomain).neq('user_id', st.session_state.user.id).execute()
                        
                        if existing.data:
                            st.error("This subdomain is already taken. Please choose another one.")
                        else:
                            # Prepare settings data
                            settings_data = {
                                'user_id': st.session_state.user.id,
                                'setting_type': 'api_config',
                                'settings': {
                                    'subdomain': new_subdomain,
                                    'updated_at': datetime.utcnow().isoformat()
                                }
                            }
                            
                            if has_subdomain:
                                # Update existing record
                                result = st.session_state.supabase.table('user_settings').update(settings_data).eq('user_id', st.session_state.user.id).eq('setting_type', 'api_config').execute()
                            else:
                                # Insert new record
                                result = st.session_state.supabase.table('user_settings').insert(settings_data).execute()
                            
                            st.success("✅ Subdomain saved successfully!")
                            st.info("Note: It may take a few minutes for your new subdomain to become active.")
                            st.rerun()
                            
                    except Exception as e:
                        st.error(f"Error saving subdomain: {str(e)}")
            else:
                st.error("Please enter a subdomain")
    
    if has_subdomain:
        if st.button("🗑️ Delete Custom Subdomain", type="secondary", help="Remove your custom subdomain configuration"):
            try:
                # Delete from Supabase
                result = st.session_state.supabase.table('user_settings').delete().eq('user_id', st.session_state.user.id).eq('setting_type', 'api_config').execute()
                st.success("✅ Custom subdomain deleted successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Error deleting subdomain: {str(e)}")
    
    st.markdown("---")
    
    st.markdown("""
    ### API Configuration Guide
    
    The API base URL should be set in your Streamlit secrets:
    ```toml
    API_BASE_URL = "your-api-url"
    ```
    
    For local development, use:
    ```toml
    API_BASE_URL = "http://localhost:5000"
    ```
    
    For production, use your deployed API URL:
    ```toml
    API_BASE_URL = "https://your-api.domain.com"
    ```
    """)

with tab3:
    st.header("Debug Information")
    
    # System Information
    st.subheader("System Information")
    st.json({
        "Python Version": sys.version,
        "Working Directory": os.getcwd(),
        "Platform": sys.platform
    })
    
    # Environment Variables
    st.subheader("Environment Variables")
    env_vars = {
        "API_BASE_URL": os.getenv("API_BASE_URL"),
        "SUPABASE_URL": "***" if os.getenv("SUPABASE_URL") else None,
        "KAGGLE_USERNAME": os.getenv("KAGGLE_USERNAME"),
        "PATH": os.getenv("PATH")
    }
    st.json(env_vars)
    
    # Session State
    st.subheader("Session State")
    # Filter out sensitive information
    safe_session_state = {
        k: v for k, v in st.session_state.items()
        if not isinstance(v, (pd.DataFrame, dict)) and "key" not in k.lower()
    }
    st.json(safe_session_state)
    
    # Streamlit Configuration
    st.subheader("Streamlit Configuration")
    if os.path.exists(".streamlit/config.toml"):
        with open(".streamlit/config.toml", "r") as f:
            st.code(f.read(), language="toml")
    else:
        st.info("No Streamlit configuration file found")
    
    # Test Connections
    st.subheader("Connection Tests")
    if st.button("Test Connections"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            try:
                st.session_state.supabase.auth.get_session()
                st.success("✅ Supabase")
            except Exception as e:
                st.error(f"❌ Supabase\n{str(e)}")
        
        with col2:
            try:
                response = requests.get(f"{api_base_url}/api/hello")
                if response.status_code == 200:
                    st.success("✅ API")
                else:
                    st.error("❌ API")
            except Exception as e:
                st.error(f"❌ API\n{str(e)}")
        
        with col3:
            try:
                if hasattr(st.secrets, 'kaggle'):
                    import kaggle
                    kaggle.api.authenticate()
                    st.success("✅ Kaggle")
                else:
                    st.warning("⚠️ Kaggle not configured")
            except Exception as e:
                st.error(f"❌ Kaggle\n{str(e)}") 