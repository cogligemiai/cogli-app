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
    if not client: return ""
    try:
        response = client.audio.speech.create(model="tts-1", voice="alloy", input=text)
        b64 = base64.b64encode(response.content).decode()
        rnd_id = random.randint(1000, 99999)
        return f'<audio id="audio-{rnd_id}" autoplay="true"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>'
    except:
        return ""

def generate_word_bundle(df):
    """Creates a complete package of text and pre-downloaded audio for a single word."""
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

    return {
        'word': word,
        'opts': opts,
        'correct_letter': correct_letter,
        'challenge_text': challenge_text,
        'answer_text': answer_text,
        'challenge_audio': get_audio_html(challenge_text),
        'answer_audio': get_audio_html(answer_text)
    }

# --- APP UI ---
if not client or not drive_service:
    st.error("Credentials Error: Check Secrets.")
    st.stop()

df = load_data()

if df is not None:
    st.title("🚘 COGLI Car Vocab Quiz")
    
    # 1. INITIALIZATION & PRE-LOADING
    if 'loop_running' not in st.session_state:
        st.session_state.loop_running = False
        st.session_state.welcome_played = False
        
    if 'current_bundle' not in st.session_state:
        # This spinner shows while it downloads the first audio files
        with st.spinner("Pre-loading Audio Engine (Takes ~5 seconds)..."):
            st.session_state.welcome_audio = get_audio_html("Welcome to the COGLI Car Vocab Quiz.")
            st.session_state.current_bundle = generate_word_bundle(df)

    # 2. START SCREEN
    if not st.session_state.loop_running:
        st.success("Engine Ready! Zero-Latency mode engaged.")
        if st.button("▶️ START VOCAB QUIZ", type="primary"):
            st.session_state.loop_running = True
            st.rerun()

    # 3. THE ACTIVE LOOP
    if st.session_state.loop_running:
        header_spot = st.empty()
        content_spot = st.empty()
        status_spot = st.empty()
        audio_spot = st.empty()
        
        # --- THE WELCOME MESSAGE ---
        if not st.session_state.welcome_played:
            audio_spot.markdown(st.session_state.welcome_audio, unsafe_allow_html=True)
            time.sleep(2.5) 
            st.session_state.welcome_played = True
            audio_spot.empty()
            
        bundle = st.session_state.current_bundle

        # --- PHASE A: INSTANT CHALLENGE ---
        header_spot.markdown(f"### **Word:** {bundle['word'].upper()}")
        content_spot.markdown(f"**A:** {bundle['opts'][0]}\n\n**B:** {bundle['opts'][1]}\n\n**C:** {bundle['opts'][2]}")
        
        # Play pre-fetched challenge audio immediately
        time.sleep(0.05) 
        audio_spot.markdown(bundle['challenge_audio'], unsafe_allow_html=True)
        status_spot.info("Speaking Challenge...")
        
        # Start a stopwatch
        start_time = time.time()
        est_speech_time = (len(bundle['challenge_text'].split()) / 2.7) 
        
        # --- THE MAGIC TRICK: FETCH NEXT WORD WHILE SPEAKING CURRENT WORD ---
        st.session_state.next_bundle = generate_word_bundle(df)
        
        # Check stopwatch. If fetching the next word took less time than the speech, 
        # wait out the remainder of the speech time.
        elapsed_time = time.time() - start_time
        remaining_speech_time = est_speech_time - elapsed_time
        if remaining_speech_time > 0:
            time.sleep(remaining_speech_time)
        
        # --- 2-SECOND PAUSE ---
        for i in range(2, 0, -1):
            status_spot.warning(f"YOUR TURN ({i}s)")
            time.sleep(1)

        # --- PHASE B: INSTANT RESOLUTION ---
        status_spot.success(f"Answer: {bundle['correct_letter']}")
        audio_spot.empty()
        time.sleep(0.05)
        
        # Play pre-fetched answer audio immediately
        audio_spot.markdown(bundle['answer_audio'], unsafe_allow_html=True)
        
        est_res_time = (len(bundle['answer_text'].split()) / 3.0) 
        time.sleep(est_res_time)
        
        # --- SWAP THE BARREL & RESTART ---
        # The 'next_bundle' we fetched in the background becomes the new 'current_bundle'
        st.session_state.current_bundle = st.session_state.next_bundle
        st.rerun()

else:
    st.warning("Connecting to COGLI Data...")
