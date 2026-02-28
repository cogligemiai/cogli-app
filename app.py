import streamlit as st
import pandas as pd
import json
import random
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# --- CONFIGURATION ---
FILENAME_PART = "VOCAB_COGLI_MASTER_CLEAN"

st.set_page_config(page_title="COGLI Super-Search", layout="centered")
st.title("🎯 COGLI Super-Search Diagnostic")

@st.cache_resource
def get_drive_service():
    try:
        creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = service_account.Credentials.from_service_account_info(creds_dict)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Auth Error: {e}")
        return None

def load_data():
    service = get_drive_service()
    if not service: return None

    st.write("🔍 **Scanning all shared files (Limit: 100)...**")
    # Increased pageSize to 100 to see past the folders
    results = service.files().list(pageSize=100, fields="files(id, name, mimeType)").execute()
    items = results.get('files', [])
    
    if not items:
        st.warning("⚠️ The Robot sees ZERO files.")
        return None

    # Display everything found to help us identify the exact filename
    with st.expander("See all 100 files the Robot found"):
        for item in items:
            st.write(f"- `{item['name']}` (Type: `{item['mimeType']}`)")

    # Search for the file using just the main part of the name
    search = service.files().list(
        q=f"name contains '{FILENAME_PART}'",
        fields="files(id, name, mimeType)"
    ).execute()
    found_files = search.get('files', [])

    if not found_files:
        st.error(f"❌ Still cannot find a file containing '{FILENAME_PART}'")
        st.info("Check if the file is actually inside the 'COGLI VOCABULARY' folder.")
        return None

    # Pick the first match
    target = found_files[0]
    st.success(f"✅ Found Match: `{target['name']}`")

    # Download Logic
    try:
        if target['mimeType'] == 'application/vnd.google-apps.spreadsheet':
            st.info("Converting Google Sheet to CSV on the fly...")
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
        st.error(f"Download Error: {e}")
        return None

# --- RUN APP ---
df = load_data()

if df is not None:
    st.divider()
    st.balloons()
    st.success("📊 **DATA CONNECTED!**")
    st.write("### Preview of your Master Vocabulary:")
    st.dataframe(df.head(10)) 
    
    st.info("Once you confirm this data is correct, I will provide the final Quiz UI code.")
