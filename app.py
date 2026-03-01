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

# --- CUSTOM "IUI" CSS (WIDE & SHORT BUTTONS) ---
st.markdown("""
    <style>
    /* Force buttons to be wide and short */
    .stButton > button {
        width: 100% !important;
        height: 2.5em !important; /* Shorter height */
        padding: 0px !important;
        font-size: 18px !important;
        font-weight: bold !important;
        border-radius: 10px !important;
        border: 2px solid #444 !important;
        white-space: nowrap;
        overflow: hidden;
    }
    /* Highlight selected Tiers in Blue */
    .stButton > button:active, .stButton > button:focus {
        border-color: #1E90FF !important;
    }
    /* Start Button - Red and Wide */
    div.stButton > button[kind="primary"] {
        background-color: #FF4B4B !important;
        color: white !important;
        border: none !important;
        height: 3em !important;
        font-size: 22px !important;
    }
    /* Spacing */
    .block-container { padding-top: 1rem !important; }
    </style>
    """, unsafe_allow_html=True)

# --- ENGINES ---
@st.cache_resource
def init_engines():
    try:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        creds_info = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
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
    # RESILIENCE FIX: Use column index instead of name to avoid KeyError
    row = df.iloc[random.randint(0, len(df)-1)]
    word = str(row.iloc[0]) # First column
    correct_def = str(row.iloc[1]) # Second column
    
    # Try to find Nuance by name, otherwise default
    nuance_text = ""
    if 'Nuance' in df.columns:
        raw_n = str(row['Nuance']).strip()
        if raw_n.lower() not in ['', 'nan', 'none', 'no nuance provided.']:
            nuance_text = f" {raw_n}"

    others = df[df.iloc[:, 1] != correct_def].iloc[:, 1].sample(min(2, len(df)-1)).tolist()
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
    
    if 'loop_running' not in st.session_state:
        st.session_state.loop_running = False
        st.session_state.welcome_played = False
    if 'selected_tiers' not in st.session_state:
        st.session_state.selected_tiers = [2] 

    # --- START SCREEN ---
    if not st.session_state.loop_running:
        st.write("### Select Training Tiers")
        
        t_col1, t_col2, t_col3 = st.columns(3)
        
        with t_col1:
            m_btn = "✅ Maint." if 1 in st.session_state.selected_tiers else "Maint."
            if st.button(m_btn, use_container_width=True):
                if 1 in st.session_state.selected_tiers: st.session_state.selected_tiers.remove(1)
                else: st.session_state.selected_tiers.append(1)
                st.rerun()
        
        with t_col2:
            a_btn = "✅ Adv." if 2 in st.session_state.selected_tiers else "Adv."
            if st.button(a_btn, use_container_width=True):
                if 2 in st.session_state.selected_tiers: st.session_state.selected_tiers.remove(2)
                else: st.session_state.selected_tiers.append(2)
                st.rerun()
                
        with t_col3:
            s_btn = "✅ Spec." if 3 in st.session_state.selected_tiers else "Spec."
            if st.button(s_btn, use_container_width=True):
                if 3 in st.session_state.selected_tiers: st.session_state.selected_tiers.remove(3)
                else: st.session_state.selected_tiers.append(3)
                st.rerun()

        # Filter Logic
        if 'Level' in df_master.columns:
            df_filtered = df_master[df_master['Level'].astype(float).isin(st.session_state.selected_tiers)]
        else:
            st.error("⚠️ Column 'Level' not found in Sheet.")
            df_filtered = df_master

        st.write("") 
        if st.button("▶️ START VOCAB QUIZ", type="primary"):
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
