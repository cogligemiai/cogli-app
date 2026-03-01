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
st.set_page_config(page_title="COGLI Car Vocab", page_icon="🚘", layout="centered")

# --- ENGINES (Cached) ---
@st.cache_resource
def init_engines():
    try:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        creds_info = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
        if "private_key" in creds_info:
            creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n").strip()
        creds = service_account.Credentials.from_service_account_info(creds_info)
        drive_service = build('drive', 'v3', credentials=creds)
        return client, drive_service
    except:
        return None, None

client, drive_service = init_engines()

@st.cache_data(ttl=300)
def load_data():
    if not drive_service: return None
    try:
        results = drive_service.files().list(q="name contains 'VOCAB_COGLI_MASTER_CLEAN'", fields="files(id, name, mimeType)").execute()
        items = results.get('files', [])
        if not items: return None
        target = items[0]
        request = drive_service.files().get_media(fileId=target['id']) if target['mimeType'] != 'application/vnd.google-apps.spreadsheet' else drive_service.files().export_media(fileId=target['id'], mimeType='text/csv')
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done: status, done = downloader.next_chunk()
        fh.seek(0)
        return pd.read_csv(fh)
    except:
        return None

def get_audio_html(text):
    """Generates the HTML for the audio player without displaying it yet."""
    if not client: return ""
    try:
        response = client.audio.speech.create(model="tts-1", voice="alloy", input=text)
        b64 = base64.b64encode(response.content).decode()
        return f'<audio autoplay="true"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>'
    except:
        return ""

# --- APP UI ---
if not client or not drive_service:
    st.error("Credentials Error: Check Secrets.")
    st.stop()

df = load_data()

if df is not None:
    st.title("🚘 COGLI Car Vocab")

    # Containers for dynamic updates
    header_spot = st.empty()
    content_spot = st.empty()
    timer_spot = st.empty()
    audio_spot = st.empty() # The invisible audio player
    
    # START BUTTON
    if 'loop_running' not in st.session_state:
        st.session_state.loop_running = False

    if not st.session_state.loop_running:
        if st.button("▶️ START CONTINUOUS LOOP", type="primary"):
            st.session_state.loop_running = True
            st.rerun()

    # THE CONTINUOUS LOOP
    if st.session_state.loop_running:
        while True:
            # 1. SETUP WORD
            row = df.iloc[random.randint(0, len(df)-1)]
            word, correct_def, nuance = row['Word'], row['Definition'], row.get('Nuance', 'No nuance provided.')
            
            others = df[df['Definition'] != correct_def]['Definition'].sample(2).tolist()
            opts = [correct_def] + others
            random.shuffle(opts)
            correct_letter = chr(65 + opts.index(correct_def))

            # 2. DISPLAY CHALLENGE
            header_spot.markdown(f"### **Word:** {word.upper()}")
            content_spot.markdown(f"**A:** {opts[0]}\n\n**B:** {opts[1]}\n\n**C:** {opts[2]}")
            
            # 3. SPEAK CHALLENGE
            challenge_text = f"The word is {word}. Option A: {opts[0]}. Option B: {opts[1]}. Option C: {opts[2]}."
            audio_html = get_audio_html(challenge_text)
            audio_spot.markdown(audio_html, unsafe_allow_html=True)
            
            # 4. THINKING TIMER (Reduced to 8s)
            est_speech_time = int(len(challenge_text.split()) / 2.3)
            # Wait for speech to finish + 8 seconds thinking time
            for i in range(est_speech_time + 8, 0, -1):
                if i > 8:
                    timer_spot.info(f"Speaking... ({i}s)")
                else:
                    timer_spot.warning(f"YOUR TURN: Answer Now! ({i}s)")
                time.sleep(1)
            
            # 5. RESOLUTION
            answer_text = f"The correct answer is {correct_letter}: {correct_def}. Nuance: {nuance}."
            audio_html = get_audio_html(answer_text)
            audio_spot.markdown(audio_html, unsafe_allow_html=True) # Replaces the old audio player
            
            content_spot.success(f"Answer: {correct_letter}")
            timer_spot.empty()
            
            # 6. TRANSITION PAUSE
            est_res_time = int(len(answer_text.split()) / 2.3) + 3
            time.sleep(est_res_time)
            
            # Loop restarts automatically (while True)

else:
    st.warning("Connecting to COGLI Data...")
