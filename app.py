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

st.set_page_config(page_title="COGLI Driving Dashboard", layout="centered")

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

@st.cache_data(ttl=300)
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
    try:
        response = client.audio.speech.create(model="tts-1", voice="alloy", input=text)
        b64 = base64.b64encode(response.content).decode()
        md = f'<audio autoplay="true"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>'
        st.markdown(md, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Voice Error: {e}")

# --- APP UI ---
df = load_data()

if df is not None:
    st.title("🚗 COGLI Driving Dashboard")
    
    # Initialize session state for word and options
    if 'current_index' not in st.session_state:
        st.session_state.current_index = random.randint(0, len(df)-1)
        st.session_state.options = []

    row = df.iloc[st.session_state.current_index]
    word = row['Word']
    correct_def = row['Definition']

    # Generate A, B, C options if not already set
    if not st.session_state.options:
        others = df[df['Definition'] != correct_def]['Definition'].sample(2).tolist()
        opts = [correct_def] + others
        random.shuffle(opts)
        st.session_state.options = opts

    # --- HIGH VISIBILITY DISPLAY ---
    st.markdown(f"<h1 style='text-align: center; color: #1E90FF;'>{word.upper()}</h1>", unsafe_allow_html=True)
    
    st.write(f"**A:** {st.session_state.options[0]}")
    st.write(f"**B:** {st.session_state.options[1]}")
    st.write(f"**C:** {st.session_state.options[2]}")

    st.divider()
    
    # --- DRIVING LOOP ---
    auto_mode = st.toggle("🚀 START AUTO-LOOP (Hands-Free)")

    if auto_mode:
        st.warning("Auto-Loop Active. Moving to next word in 15 seconds...")
        
        # Construct the A, B, C script
        script = f"The word is {word}. "
        script += f"Option A: {st.session_state.options[0]}. "
        script += f"Option B: {st.session_state.options[1]}. "
        script += f"Option C: {st.session_state.options[2]}."
        
        speak(script)
        
        time.sleep(15)
        
        # Reset for next word
        st.session_state.current_index = random.randint(0, len(df)-1)
        st.session_state.options = []
        st.rerun()
    else:
        if st.button("🔊 Read Options"):
            script = f"The word is {word}. Option A: {st.session_state.options[0]}. Option B: {st.session_state.options[1]}. Option C: {st.session_state.options[2]}."
            speak(script)
        
        if st.button("Next Word ➡️"):
            st.session_state.current_index = random.randint(0, len(df)-1)
            st.session_state.options = []
            st.rerun()

else:
    st.warning("Connecting to COGLI Data...")
