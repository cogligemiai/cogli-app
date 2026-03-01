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
st.set_page_config(page_title="COGLI Vocab", page_icon="🚗", layout="centered")

# --- CUSTOM "CAR-SPEC" CSS ---
st.markdown("""
    <style>
    /* Main Start Button */
    div.stButton > button:first-child {
        height: 4em !important;
        width: 100% !important;
        font-size: 28px !important;
        font-weight: bold !important;
        background-color: #FF4B4B !important;
        color: white !important;
        border-radius: 15px !important;
    }
    /* Tier Toggle Buttons */
    .stButton > button {
        border-radius: 10px;
        height: 3em;
        font-weight: bold;
    }
    /* Label Styling */
    .stMarkdown h3 { font-size: 22px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- ENGINES ---
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
    except: return None, None

client, drive_service = init_engines()

@st.cache_data(ttl=10)
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
    except: return None

def get_audio_html(text):
    if not client: return ""
    try:
        response = client.audio.speech.create(model="tts-1", voice="alloy", input=text)
        b64 = base64.b64encode(response.content).decode()
        rnd_id = random.randint(1000, 99999)
        return f'<audio id="audio-{rnd_id}" autoplay="true"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>'
    except: return ""

def generate_word_bundle(df, is_first=False):
    row = df.iloc[random.randint(0, len(df)-1)]
    word, correct_def = row['Word'], row['Definition']
    raw_nuance = str(row.get('Nuance', '')).strip()
    nuance_text = "" if raw_nuance.lower() in ['', 'nan', 'none', 'no nuance provided.'] else f" {raw_nuance}"
    
    others = df[df['Definition'] != correct_def]['Definition'].sample(min(2, len(df)-1)).tolist()
    opts = [correct_def] + others
    random.shuffle(opts)
    correct_letter = chr(65 + opts.index(correct_def))

    prefix = "First word" if is_first else "Next word"
    challenge_text = f"{prefix}. {word}. Option A: {opts[0]}. Option B: {opts[1]}. Option C: {opts[2]}."
    answer_text = f"The correct answer is {correct_letter}. {correct_def}.{nuance_text}"

    return {
        'word': word, 'opts': opts, 'correct_letter': correct_letter,
        'challenge_text': challenge_text, 'answer_text': answer_text,
        'challenge_audio': get_audio_html(challenge_text),
        'answer_audio': get_audio_html(answer_text)
    }

# --- APP UI ---
if not client or not drive_service:
    st.error("Credentials Error: Check Secrets.")
    st.stop()

df_master = load_data()

if df_master is not None:
    st.title("🚗 COGLI Vocab")
    
    # Initialize Session States
    if 'loop_running' not in st.session_state:
        st.session_state.loop_running = False
        st.session_state.welcome_played = False
    if 'selected_tiers' not in st.session_state:
        st.session_state.selected_tiers = [2] # Default to Tier 2

    # --- START SCREEN ---
    if not st.session_state.loop_running:
        st.subheader("Select Training Tiers")
        
        # Horizontal Toggle Buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            m_label = "✅ Tier 1" if 1 in st.session_state.selected_tiers else "Tier 1"
            if st.button(m_label, key="t1"):
                if 1 in st.session_state.selected_tiers:
                    st.session_state.selected_tiers.remove(1)
                else:
                    st.session_state.selected_tiers.append(1)
                st.rerun()
        
        with col2:
            a_label = "✅ Tier 2" if 2 in st.session_state.selected_tiers else "Tier 2"
            if st.button(a_label, key="t2"):
                if 2 in st.session_state.selected_tiers:
                    st.session_state.selected_tiers.remove(2)
                else:
                    st.session_state.selected_tiers.append(2)
                st.rerun()
                
        with col3:
            s_label = "✅ Tier 3" if 3 in st.session_state.selected_tiers else "Tier 3"
            if st.button(s_label, key="t3"):
                if 3 in st.session_state.selected_tiers:
                    st.session_state.selected_tiers.remove(3)
                else:
                    st.session_state.selected_tiers.append(3)
                st.rerun()

        st.caption("1: Maintenance | 2: Advanced | 3: Specialized")

        # Filter Logic
        if 'Level' in df_master.columns:
            df_filtered = df_master[df_master['Level'].astype(float).isin(st.session_state.selected_tiers)]
        else:
            st.error("⚠️ Column 'Level' not found in your Google Sheet.")
            df_filtered = df_master

        st.divider()
        if st.button("▶️ START VOCAB QUIZ"):
            if not st.session_state.selected_tiers:
                st.error("Please select at least one tier!")
            else:
                st.session_state.df = df_filtered
                st.session_state.current_bundle = generate_word_bundle(df_filtered, is_first=True)
                st.session_state.loop_running = True
                st.rerun()

    # --- THE ACTIVE LOOP ---
    if st.session_state.loop_running:
        header_spot = st.empty()
        content_spot = st.empty()
        status_spot = st.empty()
        audio_spot = st.empty()
        
        if not st.session_state.welcome_played:
            audio_spot.markdown(get_audio_html("Welcome to the COGLI Vocab Quiz."), unsafe_allow_html=True)
            time.sleep(3.0) 
            st.session_state.welcome_played = True
            
        bundle = st.session_state.current_bundle
        header_spot.markdown(f"### **Word:** {bundle['word'].upper()}")
        content_spot.markdown(f"**A:**   {bundle['opts'][0]}\n\n**B:**   {bundle['opts'][1]}\n\n**C:**   {bundle['opts'][2]}")
        audio_spot.markdown(bundle['challenge_audio'], unsafe_allow_html=True)
        
        start_time = time.time()
        st.session_state.next_bundle = generate_word_bundle(st.session_state.df, is_first=False)
        
        speech_wait = (len(bundle['challenge_text'].split()) / 2.3)
        time.sleep(max(0, speech_wait - (time.time() - start_time)) + 2.0)

        status_spot.success(f"Answer: {bundle['correct_letter']}")
        audio_spot.empty()
        time.sleep(0.1)
        audio_spot.markdown(bundle['answer_audio'], unsafe_allow_html=True)
        
        res_wait = (len(bundle['answer_text'].split()) / 2.3)
        time.sleep(res_wait + 2.0)
        
        st.session_state.current_bundle = st.session_state.next_bundle
        st.rerun()
else:
    st.warning("Connecting to COGLI Data...")
