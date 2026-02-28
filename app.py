import streamlit as st
import pandas as pd
import json
import random
import io
import base64
from openai import OpenAI
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# --- CONFIGURATION ---
TARGET_FILENAME = "VOCAB_COGLI_MASTER_CLEAN_v1.2.csv"

st.set_page_config(page_title="COGLI Voice-Link", layout="centered")

# --- ENGINES ---
# This pulls the key you put in Streamlit Secrets
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

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
    results = service.files().list(q=f"name = '{TARGET_FILENAME}'", fields="files(id, name, mimeType)").execute()
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
    """Converts text to speech and injects an auto-playing audio tag."""
    response = client.audio.speech.create(
        model="tts-1",
        voice="alloy", # Options: alloy, echo, fable, onyx, nova, shimmer
        input=text
    )
    b64 = base64.b64encode(response.content).decode()
    md = f"""
        <audio autoplay="true">
        <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
        """
    st.markdown(md, unsafe_allow_html=True)

# --- APP UI ---
df = load_data()

if df is not None:
    st.title("🎯 COGLI Voice-Link")
    
    if 'current_index' not in st.session_state:
        st.session_state.current_index = random.randint(0, len(df)-1)
    
    row = df.iloc[st.session_state.current_index]
    word = row['Word']
    definition = row['Definition']
    nuance = row.get('Nuance', 'No nuance provided.')

    st.subheader(f"Current Word: :blue[{word}]")
    st.write(f"**Definition:** {definition}")

    # --- DRIVING MODE CONTROLS ---
    st.divider()
    
    if st.button("🔊 START AUDIO STREAM", type="primary"):
        text_to_say = f"Next word. {word}. Definition: {definition}. Nuance: {nuance}."
        speak(text_to_say)

    if st.button("Next Word ➡️"):
        st.session_state.current_index = random.randint(0, len(df)-1)
        st.rerun()

    st.divider()
    st.caption("COGLI Protocol: Use 'Start Audio Stream' for hands-free reinforcement.")

else:
    st.warning("Connecting to COGLI Data...")
