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

st.set_page_config(page_title="COGLI Diagnostic", layout="centered")
st.title("🎯 COGLI Quiz Diagnostic")

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
        st.error(f"Auth Error: {e}")
        return None

def load_data():
    service = get_drive_service()
    if not service: return None

    # DEBUG: List ALL files the robot can see to find the discrepancy
    st.write("🔍 **Robot is searching...**")
    results = service.files().list(pageSize=10, fields="files(id, name, mimeType)").execute()
    items = results.get('files', [])
    
    if not items:
        st.warning("⚠️ The Robot sees **ZERO** files. Check folder sharing permissions.")
        return None

    st.write("📂 **Files the Robot can see:**")
    for item in items:
        st.write(f"- `{item['name']}` (Type: `{item['mimeType']}`)")

    # Aggressive Search: Look for the name only, ignore type for a moment
    search = service.files().list(
        q=f"name contains 'VOCAB_COGLI_MASTER_CLEAN'",
        fields="files(id, name, mimeType)"
    ).execute()
    found_files = search.get('files', [])

    if not found_files:
        st.error(f"❌ Could not find any file containing '{FILENAME}'")
        return None

    target = found_files[0]
    st.success(f"✅ Found: `{target['name']}`")

    # Download Logic
    request = service.files().get_media(fileId=target['id'])
    if target['mimeType'] == 'application/vnd.google-apps.spreadsheet':
        # If it's a Google Sheet, we must export it as CSV
        request = service.files().export_media(fileId=target['id'], mimeType='text/csv')
    
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    
    fh.seek(0)
    return pd.read_csv(fh)

# --- RUN APP ---
df = load_data()

if df is not None:
    st.divider()
    st.write("📊 **Data Loaded Successfully!**")
    st.dataframe(df.head()) # Show the first few rows to confirm
    
    if st.button("Start Quiz Mode"):
        st.info("Diagnostic complete. We will revert to the clean Quiz UI next.")
