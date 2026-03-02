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

# --- CUSTOM "IUI" CSS ---
st.markdown("""
<style>
    .word-label { font-size: 24px; color: white; }
    .blue-word { color: #1E90FF; font-size: 42px; font-weight: bold; text-transform: uppercase; }
    
    /* Symmetry for Ingest Console */
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
if "ingest_word" not in st.session_state: st.session_state.ingest_word = ""
if "ingest_def" not in st.session_state: st.session_state.ingest_def = None

# --- UI ---
st.title("🏎️ COGLI Vocab")

# Quiz Section
st.subheader("Select Vocabulary Tiers")
cols = st.columns(3)
with cols[0]: st.checkbox("Maintenance", value=True)
with cols[1]: st.checkbox("Advanced", value=True)
with cols[2]: st.checkbox("Specialized", value=True)
st.button("▶ START VOCAB QUIZ", type="primary")

st.divider()
st.subheader("📥 COGLI Vocab Lookup")

# --- UNIFIED INGEST CONSOLE ---
col1, col2 = st.columns([1.5, 1])

with col1:
    # NATIVE VOICE RECORDER: Bulletproof stability.
    audio_value = st.audio_input("Record your word", label_visibility="collapsed")
    if audio_value:
        with st.spinner("Transcribing..."):
            transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_value)
            st.session_state.ingest_word = transcript.text.strip().strip('.').upper()
            st.session_state.ingest_def = None

with col2:
    # TEXT INPUT: For manual entry.
    text_input = st.text_input("TYPE WORD", key="main_text_input", placeholder="OR TYPE HERE...", label_visibility="collapsed")
    if text_input and text_input.upper() != st.session_state.ingest_word:
        st.session_state.ingest_word = text_input.upper()
        st.session_state.ingest_def = None

# --- RESULTS & COMMIT ---
if st.session_state.ingest_word:
    st.markdown(f"**WORD DETECTED:** `{st.session_state.ingest_word}`")
    
    if not st.session_state.ingest_def:
        with st.spinner("Defining..."):
            response = client.chat.completions.create(
                model="gpt-4o",
                temperature=0.0,
                messages=[{"role": "system", "content": "Format: 'DEFINITION: [Text] NUANCE: [Cognitive Hook]'"},
                          {"role": "user", "content": f"Define: {st.session_state.ingest_word}"}]
            )
            st.session_state.ingest_def = response.choices[0].message.content

    st.info(st.session_state.ingest_def)
    
    if st.button("COMMIT WORD TO VOCABULARY DATABASE", use_container_width=True):
        st.success(f"STAGED: {st.session_state.ingest_word}. Database logic ready.")
