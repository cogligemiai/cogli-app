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
st.set_page_config(page_title="COGLI Car Vocab Quiz", page_icon="🚘", layout="centered")

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
        items = results.get('files',[])
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
    """Generates the HTML for the audio player."""
    if not client: return ""
    try:
        response = client.audio.speech.create(model="tts-1", voice="alloy", input=text)
        b64 = base64.b64encode(response.content).decode()
        rnd_id = random.randint(1000, 99999)
        return f'<audio id="audio-{rnd_id}" autoplay="true"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>'
    except:
        return ""

# --- APP UI ---
if not client or not drive_service:
    st.error("Credentials Error: Check Secrets.")
    st.stop()

df = load_data()

if df is not None:
    st.title("🚘 COGLI Car Vocab Quiz")
    
    # 1. LOOP STATE MANAGER
    if 'loop_running' not in st.session_state:
        st.session_state.loop_running = False
    
    if 'welcome_played' not in st.session_state:
        st.session_state.welcome_played = False

    # Pre-fetch the Welcome Audio while the user is looking at the start screen
    if 'welcome_audio_html' not in st.session_state:
        with st.spinner("Pre-loading Audio Engine..."):
            st.session_state.welcome_audio_html = get_audio_html("Welcome to the COGLI Car Vocab Quiz.")

    # 2. THE START SCREEN
    if not st.session_state.loop_running:
        st.info("Engine Ready. Tap start to begin continuous loop.")
        if st.button("▶️ START VOCAB QUIZ", type="primary"):
            st.session_state.loop_running = True
            st.rerun()

    # 3. THE ACTIVE LOOP
    if st.session_state.loop_running:
        # Layout Containers
        header_spot = st.empty()
        content_spot = st.empty()
        status_spot = st.empty()
        audio_spot = st.empty()
        
        # --- THE WELCOME SEQUENCE (Plays only once) ---
        if not st.session_state.welcome_played:
            status_spot.info("System Active...")
            audio_spot.markdown(st.session_state.welcome_audio_html, unsafe_allow_html=True)
            time.sleep(2.5) # Wait for welcome message to finish
            st.session_state.welcome_played = True
            audio_spot.empty() # Clear player
        
        # --- SETUP WORD & NUANCE FILTER ---
        row = df.iloc[random.randint(0, len(df)-1)]
        word = row['Word']
        correct_def = row['Definition']
        
        raw_nuance = str(row.get('Nuance', '')).strip()
        if raw_nuance.lower() in['', 'nan', 'none', 'no nuance provided', 'no nuance provided.']:
            nuance_text = ""
        else:
            nuance_text = f" Nuance: {raw_nuance}"
            
        others = df[df['Definition'] != correct_def]['Definition'].sample(2).tolist()
        opts = [correct_def] + others
        random.shuffle(opts)
        
        correct_letter = chr(65 + opts.index(correct_def))

        challenge_text = f"The word is {word}. Option A: {opts[0]}. Option B: {opts[1]}. Option C: {opts[2]}."
        answer_text = f"The correct answer is {correct_letter}. {correct_def}.{nuance_text}"

        # --- INSTANT VISUAL RENDER ---
        header_spot.markdown(f"### **Word:** {word.upper()}")
        content_spot.markdown(f"**A:** {opts[0]}\n\n**B:** {opts[1]}\n\n**C:** {opts[2]}")
        
        # --- PHASE A: INSTANT CHALLENGE AUDIO ---
        challenge_audio = get_audio_html(challenge_text)
        
        # Play Challenge Audio immediately
        audio_spot.empty()
        time.sleep(0.05) 
        audio_spot.markdown(challenge_audio, unsafe_allow_html=True)
        status_spot.info("Speaking Challenge...")
        
        # Start stopwatch
        start_time = time.time()
        est_speech_time = (len(challenge_text.split()) / 2.7) 
        
        # --- BACKGROUND FETCH: GET THE ANSWER AUDIO WHILE SPEAKING ---
        answer_audio = get_audio_html(answer_text)
        
        # Wait only the REMAINING time of the speech
        elapsed_time = time.time() - start_time
        remaining_speech_time = est_speech_time - elapsed_time
        if remaining_speech_time > 0:
            time.sleep(remaining_speech_time)
        
        # EXACT 2-SECOND PAUSE
        for i in range(2, 0, -1):
            status_spot.warning(f"YOUR TURN ({i}s)")
            time.sleep(1)

        # --- PHASE B: THE RESOLUTION ---
        status_spot.success(f"Answer: {correct_letter}")
        audio_spot.empty()
        time.sleep(0.05)
        audio_spot.markdown(answer_audio, unsafe_allow_html=True)
        
        # Aggressive cutoff timer
        est_res_time = (len(answer_text.split()) / 3.0) 
        time.sleep(est_res_time)
        
        # INSTANTLY RESTART THE PAGE
        st.rerun()

else:
    st.warning("Connecting to COGLI Data...")
