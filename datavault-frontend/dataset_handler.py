import streamlit as st
import pandas as pd
import os
from io import BytesIO, StringIO
import requests

def check_supabase_storage(supabase, user_id, dataset_name, file_name):
    """Check if file exists in Supabase storage"""
    try:
        bucket_path = f"user_{user_id}/{dataset_name.replace('/', '_')}/{file_name}"
        # List files in the bucket to check if our file exists
        files = supabase.storage.from_('datasets').list(f"user_{user_id}/{dataset_name.replace('/', '_')}")
        for file in files:
            if file['name'] == file_name:
                return bucket_path
        return None
    except Exception as e:
        print(f"Error checking Supabase storage: {str(e)}")
        return None

def upload_to_supabase(supabase, user_id, file_path, dataset_name):
    """Upload a file to Supabase Storage"""
    try:
        file_name = os.path.basename(file_path)
        bucket_path = f"user_{user_id}/{dataset_name}/{file_name}"
        
        # Create user directory if it doesn't exist
        try:
            supabase.storage.from_('datasets').list(f"user_{user_id}")
        except:
            # Directory doesn't exist, it will be created on upload
            pass
        
        # Check if file exists and remove it
        try:
            supabase.storage.from_('datasets').remove([bucket_path])
        except:
            # File doesn't exist, which is fine
            pass
        
        # Read file content
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # Upload to Supabase storage
        response = supabase.storage.from_('datasets').upload(
            path=bucket_path,
            file=file_content,
            file_options={"contentType": "text/csv"}
        )
        return bucket_path
    except Exception as e:
        st.error(f"Error uploading to Supabase: {str(e)}")
        return None

def get_from_supabase(supabase_client, bucket_path):
    """Get dataset from Supabase storage"""
    try:
        # Get file from Supabase storage
        response = supabase_client.storage.from_('datasets').download(bucket_path)
        
        # Try to detect encoding first using chardet
        try:
            import chardet
            detected = chardet.detect(response)
            detected_encoding = detected['encoding']
            if detected_encoding:
                try:
                    df = pd.read_csv(
                        BytesIO(response), 
                        encoding=detected_encoding,
                        on_bad_lines='skip'
                    )
                    st.success(f"Successfully loaded dataset using detected encoding: {detected_encoding}")
                    return df
                except Exception as e:
                    st.warning(f"Detected encoding {detected_encoding} failed, trying fallback encodings...")
        except ImportError:
            pass

        # Fallback encodings to try
        encodings = ['utf-8', 'latin1', 'iso-8859-1', 'cp1252', 'utf-16', 'ascii']
        errors = []
        
        for encoding in encodings:
            try:
                df = pd.read_csv(
                    BytesIO(response), 
                    encoding=encoding,
                    on_bad_lines='skip'
                )
                st.success(f"Successfully loaded dataset using encoding: {encoding}")
                return df
            except UnicodeDecodeError as e:
                errors.append(f"{encoding}: {str(e)}")
                continue
            except Exception as e:
                errors.append(f"{encoding}: Unexpected error: {str(e)}")
                continue
        
        # If CSV reading fails, try Excel as last resort
        try:
            df = pd.read_excel(BytesIO(response))
            st.success("Successfully loaded dataset as Excel file")
            return df
        except Exception as excel_error:
            errors.append(f"Excel: {str(excel_error)}")
        
        # If we get here, all attempts failed
        error_msg = "Failed to load dataset. Attempted the following:\n\n"
        for error in errors:
            error_msg += f"- {error}\n"
        st.error(error_msg)
        return None
                
    except Exception as e:
        st.error(f"Error accessing dataset from storage: {str(e)}")
        return None

def display_dataset_info(df, bucket_path):
    """Display dataset information and store in session state"""
    st.success(f"Dataset loaded successfully from Supabase!")
    
    # Store in session state
    st.session_state.df = df
    st.session_state.current_dataset = bucket_path
    
    # Display basic information
    with st.container():
        st.markdown('<div class=""><hr /></div>', unsafe_allow_html=True)
        st.subheader("Dataset Information")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Rows", len(df))
        with col2:
            st.metric("Total Columns", len(df.columns))
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Display the first 5 rows in a table
    with st.container():
        st.markdown('<div class=""><hr /></div>', unsafe_allow_html=True)
        st.subheader("First 5 Rows of the Dataset")
        st.dataframe(df.head(), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Display column names
    with st.container():
        st.markdown('<div class=""><hr /></div>', unsafe_allow_html=True)
        st.subheader("Available Columns")
        st.write(", ".join(df.columns.tolist()))
        st.markdown('</div>', unsafe_allow_html=True)

def make_api_call(endpoint, params=None, headers=None):
    """Make API call to Flask backend"""
    base_url = os.getenv('API_BASE_URL', 'http://localhost:5000/api')
    try:
        # Add current dataset path to params if it exists
        if st.session_state.current_dataset:
            if params is None:
                params = {}
            params['bucket_path'] = st.session_state.current_dataset
        
        # Initialize headers if None
        if headers is None:
            headers = {}
        
        response = requests.get(f"{base_url}{endpoint}", params=params, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            error_msg = response.json().get('error', f"API call failed with status code {response.status_code}")
            return {"error": error_msg}
    except requests.exceptions.ConnectionError:
        return {"error": "Could not connect to API. Make sure the API server is running and accessible."}

def get_user_datasets(supabase, user_id):
    """Get list of datasets uploaded by the user"""
    try:
        # List all folders in the user's directory
        user_path = f"user_{user_id}"
        try:
            folders = supabase.storage.from_('datasets').list(user_path)
        except:
            # User directory doesn't exist yet
            return []
            
        datasets = []
        for folder in folders:
            if folder['name'].endswith('.csv'):  # Handle files in root
                datasets.append({
                    'name': folder['name'],
                    'path': f"{user_path}/{folder['name']}"
                })
            else:  # Handle files in folders
                try:
                    files = supabase.storage.from_('datasets').list(f"{user_path}/{folder['name']}")
                    for file in files:
                        if file['name'].endswith('.csv'):
                            datasets.append({
                                'name': f"{folder['name']}/{file['name']}",
                                'path': f"{user_path}/{folder['name']}/{file['name']}"
                            })
                except:
                    continue
        return datasets
    except Exception as e:
        st.error(f"Error fetching datasets: {str(e)}")
        return [] 