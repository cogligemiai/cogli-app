import streamlit as st
import pandas as pd
import json
import random
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# --- CONFIGURATION ---
# This looks for your specific Master file. 
# It will prioritize the CSV but can handle the Sheet if needed.
TARGET_FILENAME = "VOCAB_COGLI_MASTER_CLEAN_v1.2.csv"

st.set_page_config(page_title="COGLI Vocabulary Quiz", layout="centered")

# --- GOOGLE DRIVE CONNECTION ---
@st.cache_resource
def get_drive_service():
    try:
        creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = service_account.Credentials.from_service_account_info(creds_dict)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Authentication Error: {e}")
        return None

@st.cache_data(ttl=600) # Cache data for 10 minutes to save bandwidth
def load_data():
    service = get_drive_service()
    if not service: return None

    # Search for the exact filename
    results = service.files().list(
        q=f"name = '{TARGET_FILENAME}'",
        fields="files(id, name, mimeType)"
    ).execute()
    items = results.get('files', [])

    if not items:
        # Fallback: Search for the BU version if the exact one isn't found
        results = service.files().list(
            q="name contains 'VOCAB_COGLI_MASTER_CLEAN'",
            fields="files(id, name, mimeType)"
        ).execute()
        items = results.get('files', [])

    if not items:
        st.error("Could not find the Vocabulary file in Google Drive.")
        return None

    target = items[0]
    
    try:
        if target['mimeType'] == 'application/vnd.google-apps.spreadsheet':
            request = service.files().export_media(fileId=target['id'], mimeType='text/csv')
        else:
            request = service.files().get_media(fileId=target['id'])
        
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.seek(0)
        return pd.read_csv(fh)
    except Exception as e:
        st.error(f"Error downloading file: {e}")
        return None

# --- QUIZ LOGIC ---
df = load_data()

if df is not None:
    st.title("🎯 COGLI Vocabulary Quiz")
    
    # Initialize session state
    if 'current_index' not in st.session_state:
        st.session_state.current_index = random.randint(0, len(df)-1)
    if 'options' not in st.session_state:
        st.session_state.options = []
    if 'answered' not in st.session_state:
        st.session_state.answered = False

    # Get current word data
    row = df.iloc[st.session_state.current_index]
    word = row['Word']
    correct_def = row['Definition']
    nuance = row.get('Nuance', 'No nuance provided.')

    # Generate options only once per word
    if not st.session_state.options:
        others = df[df['Definition'] != correct_def]['Definition'].sample(2).tolist()
        opts = [correct_def] + others
        random.shuffle(opts)
        st.session_state.options = opts

    st.divider()
    st.subheader(f"Word: :blue[{word}]")

    # Quiz Form
    with st.form("quiz_form"):
        choice = st.radio("Select the correct definition:", st.session_state.options)
        submitted = st.form_submit_button("Submit Answer")

        if submitted:
            st.session_state.answered = True
            if choice == correct_def:
                st.success(f"✅ **CORRECT!**")
                st.info(f"**NUANCE:** {nuance}")
            else:
                st.error(f"❌ **INCORRECT.**")
                st.write(f"The correct definition is: **{correct_def}**")

    # Navigation
    if st.session_state.answered:
        if st.button("Next Word ➡️"):
            st.session_state.current_index = random.randint(0, len(df)-1)
            st.session_state.options = []
            st.session_state.answered = False
            st.rerun()
else:
    st.warning("Waiting for data connection...")
