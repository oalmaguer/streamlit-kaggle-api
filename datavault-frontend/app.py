import streamlit as st
import pandas as pd
import os
from dotenv import load_dotenv
import requests
import json
from supabase import create_client
from io import StringIO, BytesIO
import tempfile
import extra_streamlit_components as stx
import logging
from dataset_handler import (
    check_supabase_storage,
    upload_to_supabase,
    get_from_supabase,
    display_dataset_info,
    make_api_call,
    get_user_datasets
)
import sys
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
logger.info("Environment variables loaded")

# Log available secrets (without sensitive values)
logger.info("Available Streamlit secrets keys: %s", list(st.secrets.keys()))

# Get API base URL from environment
API_BASE_URL = st.secrets.get("API_BASE_URL", os.getenv('API_BASE_URL', 'http://localhost:5000'))
logger.info("API_BASE_URL configured as: %s", API_BASE_URL)

def init_supabase():
    """Initialize Supabase client"""
    try:
        SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.getenv('SUPABASE_URL'))
        SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.getenv('SUPABASE_KEY'))
        logger.info("Supabase configuration loaded")
        
        if not SUPABASE_URL or not SUPABASE_KEY:
            logger.error("Missing Supabase credentials")
            st.error("Missing Supabase credentials. Please check your configuration.")
            return None
        
        # Initialize Supabase client
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase client initialized successfully")
        return supabase
    except Exception as e:
        logger.error("Error initializing Supabase: %s", str(e))
        st.error(f"Error initializing Supabase: {str(e)}")
        return None

def check_session():
    """Check for existing session and refresh if needed"""
    try:
        if not st.session_state.get('supabase'):
            st.session_state.supabase = init_supabase()
        
        # Try to get existing session
        session = st.session_state.supabase.auth.get_session()
        
        if session:
            # Check if session needs refresh (if less than 60 mins remaining)
            expires_at = datetime.fromtimestamp(session.expires_at)
            if expires_at - datetime.now() < timedelta(minutes=60):
                # Refresh the session
                st.session_state.supabase.auth.refresh_session()
            
            # Update session state with user info
            st.session_state.authenticated = True
            st.session_state.user = session.user
            return True
    except Exception as e:
        print(f"Session check error: {str(e)}")
        st.session_state.authenticated = False
        st.session_state.user = None
    return False

def init_session_state():
    """Initialize session state variables"""
    try:
        # Initialize Supabase first
        if 'supabase' not in st.session_state:
            st.session_state.supabase = init_supabase()
        
        # Try to recover existing session
        if not st.session_state.get('authenticated', False):
            check_session()
        
        # Initialize other state variables only if needed
        if 'current_page' not in st.session_state:
            st.session_state.current_page = 'welcome'
        if 'current_dataset' not in st.session_state:
            st.session_state.current_dataset = None
        if 'df' not in st.session_state:
            st.session_state.df = None
            
    except Exception as e:
        print(f"Session state initialization error: {str(e)}")
        st.error("Error initializing application. Please try refreshing the page.")

# Page configuration
st.set_page_config(
    page_title="DataVault Explorer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern look
st.markdown("""
<style>
    /* Modern color scheme */
    :root {
        --primary-color: #4A90E2;
        --background-color: #F8F9FA;
        --text-color: #2C3E50;
        --success-color: #2ECC71;
        --warning-color: #F1C40F;
        --error-color: #E74C3C;
    }
    
    /* Main container */
    .main {
        background-color: var(--background-color);
        color: var(--text-color);
        padding: 20px;
    }
    
    /* Headers */
    h1, h2, h3 {
        color: var(--text-color);
        font-weight: 600;
    }
    
    /* Buttons */
    .stButton button {
        background-color: var(--primary-color);
        color: white;
        border-radius: 8px;
        padding: 8px 16px;
        border: none;
        transition: all 0.3s ease;
    }
    
    .stButton button:hover {
        background-color: #357ABD;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* Cards */
    .card {
        background-color: white;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    
    /* Success/Info messages */
    .success-msg {
        background-color: var(--success-color);
        color: white;
        padding: 10px;
        border-radius: 8px;
    }
    
    .info-msg {
        background-color: var(--primary-color);
        color: white;
        padding: 10px;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

def login_with_email(email, password):
    """Login with email and password"""
    try:
        auth = st.session_state.supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        if auth.user:
            st.session_state.authenticated = True
            st.session_state.user = auth.user
            # Store session data
            st.session_state.session = auth.session
            return True
    except Exception as e:
        st.error(f"Login failed: {str(e)}")
    return False

def login_with_google():
    """Login with Google"""
    try:
        response = st.session_state.supabase.auth.sign_in_with_oauth({
            "provider": "google"
        })
        # Get the authorization URL
        auth_url = response.url
        # Open in new tab
        st.markdown(f'<a href="{auth_url}" target="_blank">Click here to login with Google</a>', unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Google login failed: {str(e)}")

def register(email, password):
    """Register new user"""
    try:
        response = st.session_state.supabase.auth.sign_up({
            "email": email,
            "password": password
        })
        st.success("Registration successful! Please check your email to verify your account.")
        return True
    except Exception as e:
        st.error(f"Registration failed: {str(e)}")
        return False

def logout():
    """Logout the current user"""
    try:
        st.session_state.supabase.auth.sign_out()
    except:
        pass
    finally:
        # Clear all session state
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        # Reinitialize clean session state
        init_session_state()
        st.rerun()

def show_welcome_page():
    """Display welcome page"""
    # Redirect if user is already logged in
    if st.session_state.authenticated:
        st.session_state.current_page = 'main'
        st.rerun()
        return
    
    # st.markdown('<div class="card">', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("Welcome to DataVault Explorer 📊")
        st.markdown("""
        Your one-stop solution for exploring and analyzing Kaggle datasets.
        
        - 📈 Easy dataset visualization
        - 🔄 Seamless Kaggle integration
        - 🔒 Secure data storage
        - 🤝 API ready
        """)
        
        st.markdown("---")
        
        col4, col5, col6 = st.columns([1,1,1])
        with col4:
            if st.button("Login", use_container_width=True):
                st.session_state.current_page = 'login'
                st.rerun()
        with col5:
            if st.button("Register", use_container_width=True):
                st.session_state.current_page = 'register'
                st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

def show_login_page():
    """Display login page"""
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("Login to DataVault Explorer")
        
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        
        col4, col5 = st.columns(2)
        with col4:
            if st.button("Login", use_container_width=True):
                if login_with_email(email, password):
                    st.session_state.current_page = 'main'
                    st.rerun()
        with col5:
            if st.button("Login with Google", use_container_width=True):
                login_with_google()
        
        st.markdown("---")
        st.markdown("Don't have an account? [Register here](#)", help="Click the Register button below")
        if st.button("Go to Register", use_container_width=True):
            st.session_state.current_page = 'register'
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

def show_register_page():
    """Display register page"""
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("Register for DataVault Explorer")
        
        reg_email = st.text_input("Email", key="reg_email")
        reg_password = st.text_input("Password", type="password", key="reg_password")
        reg_password_confirm = st.text_input("Confirm Password", type="password", key="reg_password_confirm")
        
        if st.button("Register", use_container_width=True):
            if reg_password != reg_password_confirm:
                st.error("Passwords do not match!")
            else:
                if register(reg_email, reg_password):
                    st.session_state.current_page = 'login'
                    st.rerun()
        
        st.markdown("---")
        st.markdown("Already have an account? [Login here](#)", help="Click the Login button below")
        if st.button("Go to Login", use_container_width=True):
            st.session_state.current_page = 'login'
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

def download_kaggle_dataset(dataset_name):
    """Download dataset from Kaggle"""
    try:
        logger.info("Starting Kaggle dataset download for: %s", dataset_name)
        
        # Setup Kaggle credentials first
        if not setup_kaggle_credentials():
            logger.error("Failed to setup Kaggle credentials")
            st.error("Failed to setup Kaggle credentials")
            return None
            
        logger.info("Importing Kaggle API modules...")
        # Import kaggle here to avoid early authentication
        import kaggle.api
        from kaggle.api.kaggle_api_extended import KaggleApi
        
        # Initialize the Kaggle API
        logger.info("Initializing Kaggle API...")
        api = KaggleApi()
        api.authenticate()
        logger.info("Kaggle API authenticated successfully")
        
        # Download the dataset
        logger.info("Downloading dataset files...")
        api.dataset_download_files(dataset_name, path='.', unzip=True)
        logger.info("Dataset downloaded successfully")
        
        # Find CSV files
        csv_files = [f for f in os.listdir('.') if f.endswith('.csv')]
        logger.info("Found CSV files: %s", csv_files)
        return csv_files
    except Exception as e:
        logger.error("Error downloading from Kaggle: %s", str(e))
        st.error(f"Error downloading from Kaggle: {str(e)}")
        return None

def show_main_app():
    """Display main application"""
    # Initialize session state
    init_session_state()
    
    # Sidebar
    with st.sidebar:
        st.title("DataVault Explorer")
        st.markdown("---")
        st.markdown(f"👤 **{st.session_state.user.email}**")
        
        # Show user's datasets
        st.markdown("### Your Datasets")
        datasets = get_user_datasets(st.session_state.supabase, st.session_state.user.id)
        if datasets:
            selected_dataset = st.selectbox(
                "Select a dataset to load",
                options=[d['name'] for d in datasets],
                format_func=lambda x: x.split('/')[-1],  # Show only filename
                key="dataset_selector"
            )
            if st.button("Load Selected Dataset") or st.session_state.get('reload_dataset', False):
                selected_path = next(d['path'] for d in datasets if d['name'] == selected_dataset)
                df = get_from_supabase(st.session_state.supabase, selected_path)
                if df is not None:
                    display_dataset_info(df, selected_path)
                    # Reset the reload flag
                    st.session_state.reload_dataset = False
        else:
            st.info("No datasets uploaded yet")
        
        st.markdown("---")
        if st.button("Logout", use_container_width=True):
            logout()
            st.rerun()
    
    # Main content
    if st.session_state.current_page == 'main':
        st.title("Dataset Explorer")
        
        # Add API Management section
        with st.expander("🔑 API Access Management"):
            st.markdown("""
            ### Manage Your API Access
            Generate and manage API keys to access your datasets programmatically.
            """)
            
            # Show existing API keys
            try:
                api_keys = st.session_state.supabase.table('api_keys').select("*").eq('user_id', st.session_state.user.id).execute()
                if api_keys.data:
                    st.markdown("### Your API Keys")
                    for key in api_keys.data:
                        st.code(key['key'], language=None)
                        created_at = pd.to_datetime(key['created_at']).strftime("%Y-%m-%d %H:%M:%S")
                        st.caption(f"Created: {created_at}")
            except Exception as e:
                st.error(f"Error fetching API keys: {str(e)}")
            
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
                        
                        # Show example usage with the current dataset if available
                        st.markdown("### Example API Usage")
                        example_dataset = st.session_state.current_dataset if st.session_state.current_dataset else "your_dataset_path"
                        
                        st.code(f"""
# Python example
import requests

headers = {{
    'X-API-Key': '{data['api_key']}'
}}

# Get dataset summary
response = requests.get(
    '{API_BASE_URL}/api/data/summary',
    headers=headers,
    params={{'bucket_path': '{example_dataset}'}}
)

# Get first 5 rows
response = requests.get(
    '{API_BASE_URL}/api/data/head',
    headers=headers,
    params={{'bucket_path': '{example_dataset}', 'n': 5}}
)
                        """, language='python')
                        
                        # Force a rerun to show the new key in the list
                        st.rerun()
                    else:
                        st.error(f"Failed to generate API key: {response.json().get('error', 'Unknown error')}")
                except Exception as e:
                    st.error(f"Error: {str(e)}")
            
            # Show API Documentation
            if st.session_state.user:
                if st.button("View API Documentation"):
                    try:
                        response = requests.get(f"{API_BASE_URL}/api/docs/{st.session_state.user.id}")
                        if response.status_code == 200:
                            docs = response.json()
                            st.markdown("### Your API Documentation")
                            st.markdown(f"""
                            **Base URL:** `{docs['base_url']}`
                            
                            **Authentication:**
                            - Type: {docs['authentication']['type']}
                            - Header: `{docs['authentication']['header']}`
                            
                            **Available Endpoints:**
                            """)
                            
                            for endpoint, details in docs['endpoints'].items():
                                st.markdown(f"""
                                #### `{endpoint}`
                                {details['description']}
                                
                                Parameters: {', '.join(details['parameters'])}
                                
                                Example:
                                ```
                                {details['example']}
                                ```
                                """)
                            
                            if docs['available_datasets']:
                                st.markdown("### Your Available Datasets")
                                for dataset in docs['available_datasets']:
                                    st.code(dataset, language=None)
                            else:
                                st.info("No datasets uploaded yet. Upload a dataset to see it here.")
                    except Exception as e:
                        st.error(f"Error fetching API documentation: {str(e)}")
        
        # Input field for dataset name
        dataset_name = st.text_input(
            "Enter Dataset Name (format: username/dataset-name)",
            help="Example: NUFORC/ufo-sightings or sonalanand/spotify-dataset-for-self-practise"
        )
        
        # Download/Load button
        if st.button("Download new Dataset"):
            try:
                # First, check if the dataset already exists in Supabase
                existing_path = check_supabase_storage(st.session_state.supabase, st.session_state.user.id, dataset_name.replace('/', '_'), 'scrubbed.csv')
                
                if existing_path:
                    st.info("Dataset found in storage, loading from Supabase...")
                    df = get_from_supabase(st.session_state.supabase, existing_path)
                    if df is not None:
                        display_dataset_info(df, existing_path)
                        # Set flag to reload sidebar
                        st.session_state.reload_dataset = True
                        st.rerun()
                
                # If we get here, the dataset doesn't exist, so download from Kaggle
                with st.spinner("Dataset not found in storage. Downloading from Kaggle..."):
                    csv_files = download_kaggle_dataset(dataset_name)
                    
                    if csv_files:
                        # If there are multiple CSV files, prefer 'scrubbed.csv' or take the first one
                        csv_file = 'scrubbed.csv' if 'scrubbed.csv' in csv_files else csv_files[0]
                        
                        # Upload to Supabase
                        bucket_path = upload_to_supabase(st.session_state.supabase, st.session_state.user.id, csv_file, dataset_name.replace('/', '_'))
                        if bucket_path:
                            st.success(f"Dataset uploaded to Supabase storage: {bucket_path}")
                            
                            # Read the dataset from Supabase
                            df = get_from_supabase(st.session_state.supabase, bucket_path)
                            if df is not None:
                                display_dataset_info(df, bucket_path)
                                # Set flag to reload sidebar
                                st.session_state.reload_dataset = True
                                st.rerun()
                        
                        # Clean up local files
                        for file in csv_files:
                            os.remove(file)
                    else:
                        st.error("No CSV files found in the downloaded dataset.")
                
            except Exception as e:
                st.error(f"Error: {str(e)}")
                st.error("Please make sure you have entered a valid dataset name and have proper Kaggle credentials configured.")
        
        # Only show API Examples section if we have a dataset loaded
        if st.session_state.df is not None and st.session_state.current_dataset is not None:
            st.subheader("API Examples")
            st.info(f"Current dataset path: {st.session_state.current_dataset}")
            
            # Create columns for buttons
            col1, col2 = st.columns(2)
            
            # Get the user's API key
            try:
                api_key_result = st.session_state.supabase.table('api_keys').select("key").eq('user_id', st.session_state.user.id).limit(1).execute()
                api_key = api_key_result.data[0]['key'] if api_key_result.data else None
                
                if not api_key:
                    st.warning("Please generate an API key first using the API Access Management section above")
                else:
                    # Add buttons for different API endpoints
                    with col1:
                        st.subheader("Basic Information")
                        if st.button("Get Data Summary"):
                            st.session_state.summary_response = make_api_call(
                                "/data/summary",
                                headers={"X-API-Key": api_key}
                            )
                        
                        if st.session_state.summary_response:
                            st.write("Data Summary Response:")
                            st.json(st.session_state.summary_response)
                        
                        if st.button("Get Statistics"):
                            st.session_state.stats_response = make_api_call(
                                "/data/stats",
                                headers={"X-API-Key": api_key}
                            )
                        
                        if st.session_state.stats_response:
                            st.write("Statistics Response:")
                            st.json(st.session_state.stats_response)
                    
                    with col2:
                        st.subheader("Row Preview")
                        n_rows = st.number_input("Number of rows", min_value=1, max_value=100, value=5)
                        if st.button("Get First N Rows"):
                            st.session_state.head_response = make_api_call(
                                "/data/head",
                                params={"n": n_rows},
                                headers={"X-API-Key": api_key}
                            )
                        
                        if st.session_state.head_response:
                            st.write(f"First {n_rows} Rows Response:")
                            st.json(st.session_state.head_response)
                    
                    # Show Python example code with current API key and dataset
                    st.markdown("### Python Code Example")
                    st.code(f"""
import requests

headers = {{
    'X-API-Key': '{api_key}'  # Your API key
}}

# Get dataset summary
response = requests.get(
    '{API_BASE_URL}/api/data/summary',
    headers=headers,
    params={{'bucket_path': '{st.session_state.current_dataset}'}}
)
print(response.json())

# Get first 5 rows
response = requests.get(
    '{API_BASE_URL}/api/data/head',
    headers=headers,
    params={{
        'bucket_path': '{st.session_state.current_dataset}',
        'n': 5
    }}
)
print(response.json())
                    """, language='python')
            except Exception as e:
                st.error(f"Error fetching API key: {str(e)}")

def show_debug_page():
    """Display debug information"""
    st.title("Debug Information")
    
    # Show environment information
    st.subheader("Environment")
    st.json({
        "API_BASE_URL": API_BASE_URL,
        "SUPABASE_URL": SUPABASE_URL,
        "Has SUPABASE_KEY": bool(SUPABASE_KEY),
        "Working Directory": os.getcwd(),
        "Python Version": sys.version,
    })
    
    # Show Streamlit secrets
    st.subheader("Streamlit Secrets")
    st.json({
        "Available Keys": list(st.secrets.keys()),
        "Has Kaggle Config": hasattr(st.secrets, 'kaggle'),
    })
    
    # Show session state
    st.subheader("Session State")
    st.json(dict(st.session_state))
    
    # Show recent logs
    st.subheader("Recent Logs")
    log_stream = StringIO()
    logging_handler = logging.StreamHandler(log_stream)
    logging_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(logging_handler)
    st.code(log_stream.getvalue())
    
    # Test connections
    st.subheader("Connection Tests")
    
    # Test Supabase
    try:
        st.session_state.supabase.auth.get_session()
        st.success("✅ Supabase connection successful")
    except Exception as e:
        st.error(f"❌ Supabase connection failed: {str(e)}")
    
    # Test API
    try:
        response = requests.get(f"{API_BASE_URL}/api/hello")
        st.success(f"✅ API connection successful: {response.json()}")
    except Exception as e:
        st.error(f"❌ API connection failed: {str(e)}")
    
    # Test Kaggle
    if st.button("Test Kaggle Connection"):
        try:
            setup_kaggle_credentials()
            import kaggle
            kaggle.api.authenticate()
            st.success("✅ Kaggle authentication successful")
        except Exception as e:
            st.error(f"❌ Kaggle authentication failed: {str(e)}")

# Main app flow
def main():
    try:
        logger.info("Starting main application")
        
        # Initialize session state first
        init_session_state()
        
        logger.info("Current session state: %s", dict(st.session_state))
        
        # Add debug page access
        if 'debug' in st.query_params:
            show_debug_page()
            return
        
        # Check authentication after initialization
        if st.session_state.authenticated:
            logger.info("User is authenticated, showing main app")
            show_main_app()
        else:
            logger.info("User is not authenticated, showing auth pages")
            if st.session_state.current_page == 'welcome':
                show_welcome_page()
            elif st.session_state.current_page == 'login':
                show_login_page()
            elif st.session_state.current_page == 'register':
                show_register_page()
            else:
                show_welcome_page()
    except Exception as e:
        logger.error("Error in main application: %s", str(e))
        st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    logger.info("Application starting")
    main()