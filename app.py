import streamlit as st
import pandas as pd
import json
import io
import base64
from openai import OpenAI
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# --- CONFIGURATION ---
st.set_page_config(page_title="COGLI Vocab", page_icon="🏎️", layout="centered")

# --- CUSTOM CSS (SYMMETRY & ALIGNMENT) ---
st.markdown("""
<style>
    /* 1. Header Styling */
    .word-label { font-size: 24px; color: white; }
    .blue-word { color: #1E90FF; font-size: 42px; font-weight: bold; text-transform: uppercase; }
    
    /* 2. Symmetrical Input Box & Buttons */
    div[data-testid="stTextInput"] input {
        height: 45px !important;
        font-size: 16px !important;
        text-transform: uppercase !important;
    }
    
    .stButton > button {
        width: 100% !important;
        height: 45px !important;
        font-size: 16px !important;
        font-weight: bold !important;
        border-radius: 8px !important;
    }

    /* 3. Force Row Alignment */
    [data-testid="column"] {
        display: flex;
        align-items: center;
    }
    
    .detected-word { color: #28a745; font-weight: bold; font-family: monospace; font-size: 24px; }
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
    except:
        return None, None

client, drive_service = init_engines()

# --- DATA LOADING ---
@st.cache_data
def load_data():
    file_id = "1R7vB9-mXQO7_Wp8pY3j5k9_T_V7v-Q-p"
    try:
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.seek(0)
        return pd.read_csv(fh)
    except:
        return pd.DataFrame()

df = load_data()

# --- STATE MANAGEMENT ---
if "active_word" not in st.session_state: st.session_state.active_word = ""
if "active_def" not in st.session_state: st.session_state.active_def = None

# --- UI ---
st.title("🏎️ COGLI Vocab")

# Tiers Selection
st.subheader("Select Vocabulary Tiers")
cols = st.columns(3)
with cols[0]: st.checkbox("Maintenance", value=True)
with cols[1]: st.checkbox("Advanced", value=True)
with cols[2]: st.checkbox("Specialized", value=True)
st.button("▶ START VOCAB QUIZ", type="primary")

st.divider()
st.subheader("📥 COGLI Vocab Lookup")

# --- THE UNIFIED INPUT ROW ---
col1, col2 = st.columns([1.5, 1])

with col1:
    # NATIVE VOICE INPUT: Bulletproof reliability
    audio_data = st.audio_input("Record Word", label_visibility="collapsed")
    if audio_data:
        with st.spinner("⏳ TRANSCRIBING..."):
            transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_data)
            new_word = transcript.text.strip().strip('.').upper()
            if new_word != st.session_state.active_word:
                st.session_state.active_word = new_word
                st.session_state.active_def = None

with col2:
    # MANUAL TEXT ENTRY
    text_input = st.text_input("WORD_ENTRY", key="manual_entry", placeholder="TYPE WORD HERE...", label_visibility="collapsed")
    if text_input and text_input.upper() != st.session_state.active_word:
        st.session_state.active_word = text_input.upper()
        st.session_state.active_def = None

# --- SHARED RESULTS AREA ---
if st.session_state.active_word:
    st.markdown(f"**WORD DETECTED:** <span class='detected-word'>{st.session_state.active_word}</span>", unsafe_allow_html=True)
    
    if not st.session_state.active_def:
        with st.spinner("Defining..."):
            response = client.chat.completions.create(
                model="gpt-4o",
                temperature=0.0,
                messages=[{"role": "system", "content": "Format: 'DEFINITION: [Text] NUANCE: [Cognitive Hook]'"},
                          {"role": "user", "content": f"Define: {st.session_state.active_word}"}]
            )
            st.session_state.active_def = response.choices[0].message.content
    
    st.info(st.session_state.active_def)
    
    if st.button("COMMIT WORD TO VOCABULARY DATABASE", use_container_width=True):
        st.success(f"STAGED: {st.session_state.active_word}")
