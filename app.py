import streamlit as st
import pandas as pd
import json
import random
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# --- CONFIGURATION ---
FILENAME = "VOCAB_COGLI_MASTER_CLEAN_v1.2.csv"

# --- PAGE SETUP ---
st.set_page_config(page_title="COGLI Quiz", layout="centered")
st.title("🎯 COGLI Vocabulary Quiz")

# --- GOOGLE DRIVE CONNECTION ---
@st.cache_resource
def get_drive_service():
    try:
        # Load credentials from Streamlit Secrets
        info = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
        creds = service_account.Credentials.from_service_account_info(info)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Authentication Error: Check your Streamlit Secrets. {e}")
        return None

def load_data_from_drive():
    service = get_drive_service()
    if not service: return None

    # Search for the specific CSV file in the shared folder
    results = service.files().list(
        q=f"name = '{FILENAME}'",
        fields="files(id, name)"
    ).execute()
    items = results.get('files', [])

    if not items:
        st.error(f"File '{FILENAME}' not found. Ensure the folder is shared with the robot email.")
        return None

    file_id = items[0]['id']
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()

    fh.seek(0)
    return pd.read_csv(fh)

# --- APP LOGIC ---
df = load_data_from_drive()

if df is not None:
    # Initialize session state for tracking progress
    if 'current_index' not in st.session_state:
        st.session_state.current_index = 0

    # Get current word data
    row = df.iloc[st.session_state.current_index]
    word = row['Word']
    correct_def = row['Definition']
    nuance = row.get('Nuance', 'No nuance provided.')

    # Generate 2 random wrong answers from the rest of the list
    other_defs = df[df['Definition'] != correct_def]['Definition'].sample(2).tolist()
    options = [correct_def] + other_defs
    random.shuffle(options)

    st.divider()
    st.subheader(f"Word: :blue[{word}]")

    # Quiz Form
    with st.form("quiz_form"):
        choice = st.radio("Select the correct definition:", options)
        submitted = st.form_submit_button("Submit Answer")

        if submitted:
            if choice == correct_def:
                st.success(f"**CORRECT!** \n\n **NUANCE:** {nuance}")
            else:
                st.error(f"**INCORRECT.** \n\n The correct definition is: {correct_def}")

    # Navigation
    if st.button("Next Word ➡️"):
        st.session_state.current_index = (st.session_state.current_index + 1) % len(df)
        st.rerun()
