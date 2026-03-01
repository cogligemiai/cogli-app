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
from streamlit_mic_recorder import speech_to_text

# --- CONFIGURATION ---
TARGET_FILENAME = "VOCAB_COGLI_MASTER_CLEAN_v1.2.csv"

st.set_page_config(page_title="COGLI Active Voice", layout="centered")

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
    request = service.files().get_media(fileId=target['id']) if target['mimeType'] != 'application/vnd.google-apps.spreadsheet' else service.files().export_media(fileId=target['id'], mimeType='text/csv')
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
    st.title("🚗 COGLI Active Voice")
    
    if 'current_index' not in st.session_state:
        st.session_state.current_index = random.randint(0, len(df)-1)
        st.session_state.options = []
        st.session_state.last_speech = ""

    row = df.iloc[st.session_state.current_index]
    word = row['Word']
    correct_def = row['Definition']

    if not st.session_state.options:
        others = df[df['Definition'] != correct_def]['Definition'].sample(2).tolist()
        opts = [correct_def] + others
        random.shuffle(opts)
        st.session_state.options = opts

    # Display
    st.markdown(f"<h1 style='text-align: left; color: #1E90FF;'>{word.upper()}</h1>", unsafe_allow_html=True)
    st.write(f"**A:** {st.session_state.options[0]}")
    st.write(f"**B:** {st.session_state.options[1]}")
    st.write(f"**C:** {st.session_state.options[2]}")

    st.divider()

    # --- THE EAR (Speech to Text) ---
    st.write("🎤 **Say 'Option A', 'Option B', or 'Next'**")
    text = speech_to_text(language='en', use_container_width=True, just_once=True, key='STT')

    if text:
        st.write(f"Robot heard: *{text}*")
        
        # Logic to handle your voice command
        if "next" in text.lower():
            st.session_state.current_index = random.randint(0, len(df)-1)
            st.session_state.options = []
            st.rerun()
        
        # Check for A, B, or C
        answer_map = {"a": 0, "b": 1, "c": 2}
        for key, idx in answer_map.items():
            if f"option {key}" in text.lower() or text.lower() == key:
                if st.session_state.options[idx] == correct_def:
                    speak("Correct! Moving to next word.")
                else:
                    speak(f"Incorrect. The answer was {correct_def}. Moving on.")
                
                # Auto-advance after answering
                st.session_state.current_index = random.randint(0, len(df)-1)
                st.session_state.options = []
                st.rerun()

    # Manual Trigger for the first time
    if st.button("🔊 Read Challenge"):
        script = f"The word is {word}. Option A: {st.session_state.options[0]}. Option B: {st.session_state.options[1]}. Option C: {st.session_state.options[2]}."
        speak(script)

else:
    st.warning("Connecting to COGLI Data...")
