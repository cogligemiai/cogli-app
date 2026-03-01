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
st.set_page_config(page_title="COGLI Driving Mode", layout="centered")

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

def speak(text):
    if not client: return
    try:
        response = client.audio.speech.create(model="tts-1", voice="alloy", input=text)
        b64 = base64.b64encode(response.content).decode()
        md = f'<audio autoplay="true"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>'
        st.markdown(md, unsafe_allow_html=True)
    except:
        pass

# --- APP UI ---
if not client or not drive_service:
    st.error("Credentials Error: Please check Streamlit Secrets.")
    st.stop()

df = load_data()

if df is not None:
    st.title("🚗 COGLI Smart-Loop")

    if 'drive_loop_active' not in st.session_state:
        st.session_state.drive_loop_active = False

    row = df.iloc[random.randint(0, len(df)-1)]
    word, correct_def, nuance = row['Word'], row['Definition'], row.get('Nuance', 'No nuance provided.')
    
    others = df[df['Definition'] != correct_def]['Definition'].sample(2).tolist()
    opts = [correct_def] + others
    random.shuffle(opts)
    correct_letter = chr(65 + opts.index(correct_def))

    st.markdown(f"### **Word:** {word.upper()}")
    
    # --- DRIVING LOOP ---
    if not st.session_state.drive_loop_active:
        st.info("Tap start to begin the Smart-Loop.")
        if st.button("▶️ START DRIVING LOOP", type="primary"):
            st.session_state.drive_loop_active = True
            st.rerun()
    
    if st.session_state.drive_loop_active:
        st.success("Loop Active...")
        st.write(f"**A:** {opts[0]}\n\n**B:** {opts[1]}\n\n**C:** {opts[2]}")
        
        # 1. GENERATE SCRIPT
        challenge_text = f"The word is {word}. Option A: {opts[0]}. Option B: {opts[1]}. Option C: {opts[2]}."
        
        # 2. CALCULATE TIMING (Word count / 2.5 words per second + 15s buffer)
        word_count = len(challenge_text.split())
        speech_duration = int(word_count / 2.3) # Estimated time to speak
        thinking_buffer = 15 # Time for YOU to answer
        total_wait = speech_duration + thinking_buffer

        # 3. SPEAK & WAIT
        speak(challenge_text)
        
        # Visual countdown that accounts for the speech time
        placeholder = st.empty()
        for i in range(total_wait, 0, -1):
            if i > thinking_buffer:
                placeholder.info(f"Speaking... ({i}s)")
            else:
                placeholder.warning(f"YOUR TURN: Answer Now! ({i}s)")
            time.sleep(1)
        placeholder.empty()
        
        # 4. RESOLUTION
        answer_text = f"The correct answer is {correct_letter}: {correct_def}. Nuance: {nuance}."
        speak(answer_text)
        st.success(f"Answer: {correct_letter}")
        
        # Wait for resolution speech to finish before reloading
        res_duration = int(len(answer_text.split()) / 2.3) + 4
        time.sleep(res_duration) 
        
        st.rerun()

else:
    st.warning("Connecting to COGLI Data...")
