import streamlit as st
import pandas as pd
import json
import random
import io
import base64
import time
from openai import OpenAI
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# --- CONFIGURATION ---
TARGET_FILENAME = "VOCAB_COGLI_MASTER_CLEAN_v1.2.csv"

st.set_page_config(page_title="COGLI Driving Mode", layout="centered")

# --- ENGINES ---
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

@st.cache_resource
def get_drive_service():
    try:
        creds_info = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
        if "private_key" in creds_info:
            creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n").strip()
        creds = service_account.Credentials.from_service_account_info(creds_info)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Auth Error: {e}")
        return None

@st.cache_data(ttl=600)
def load_data():
    service = get_drive_service()
    if not service: return None
    results = service.files().list(q="name contains 'VOCAB_COGLI_MASTER_CLEAN'", fields="files(id, name, mimeType)").execute()
    items = results.get('files', [])
    if not items: return None
    target = items[0]
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

def speak(text):
    response = client.audio.speech.create(model="tts-1", voice="alloy", input=text)
    b64 = base64.b64encode(response.content).decode()
    md = f'<audio autoplay="true"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>'
    st.markdown(md, unsafe_allow_html=True)

# --- APP UI ---
df = load_data()

if df is not None:
    st.title("🚗 COGLI Driving Mode")
    
    if 'current_index' not in st.session_state:
        st.session_state.current_index = random.randint(0, len(df)-1)
    
    row = df.iloc[st.session_state.current_index]
    word = row['Word']
    definition = row['Definition']
    nuance = row.get('Nuance', 'No nuance provided.')

    st.subheader(f"Word: :blue[{word}]")
    
    # --- AUTO-ADVANCE LOGIC ---
    auto_mode = st.toggle("🚀 ENABLE AUTO-ADVANCE (Driving Mode)")

    if auto_mode:
        st.warning("Auto-Advance Active. App will speak and move to next word every 15 seconds.")
        speak(f"The word is {word}. Definition: {definition}. Nuance: {nuance}.")
        time.sleep(15) # Wait 15 seconds for the user to process
        st.session_state.current_index = random.randint(0, len(df)-1)
        st.rerun()
    else:
        if st.button("🔊 Speak Current Word"):
            speak(f"The word is {word}. Definition: {definition}. Nuance: {nuance}.")
        
        if st.button("Next Word ➡️"):
            st.session_state.current_index = random.randint(0, len(df)-1)
            st.rerun()

else:
    st.warning("Connecting to COGLI Data...")
