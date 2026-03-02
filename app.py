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
st.set_page_config(page_title="COGLI Vocab", page_icon="🏎️", layout="centered")

# --- CUSTOM "IUI" CSS (Precision Alignment & Styling) ---
st.markdown("""
<style>
    /* Headers & Labels */
    .word-label { font-size: 24px; font-weight: normal; color: white; }
    .blue-word { color: #1E90FF; font-size: 42px; font-weight: bold; text-transform: uppercase; }

    /* Hanging Indent for A, B, C */
    .option-box { display: flex; align-items: flex-start; margin-bottom: 15px; font-size: 18px; line-height: 1.4; }
    .option-label { min-width: 50px; font-weight: bold; }
    .option-text { flex: 1; }

    /* Fat-Finger Button Geometry */
    .stButton > button {
        width: 100% !important;
        height: 3em !important;
        font-size: 18px !important;
        font-weight: bold !important;
        border-radius: 10px !important;
    }

    /* Primary Red Start Button */
    div.stButton > button[kind="primary"] {
        background-color: #FF4B4B !important;
        color: white !important;
        height: 3.5em !important;
        font-size: 20px !important;
    }

    /* INGEST CONSOLE SYMMETRY */
    div[data-testid="stTextInput"] input {
        height: 45px !important;
        font-size: 16px !important;
        text-transform: uppercase !important;
    }

    /* Completely hide the technical data bridge */
    div[data-testid="stVerticalBlock"] > div:has(input[aria-label="audio_bridge"]) {
        display: none !important;
        height: 0px !important;
        margin: 0px !important;
        padding: 0px !important;
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
    file_id = "1R7vB9-mXQO7_Wp8pY3j5k9_T_V7v-Q-p" # Replace with your Master CSV File ID
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.seek(0)
    return pd.read_csv(fh)

try:
    df = load_data()
except:
    st.error("Data connection failed. Check Google Drive permissions.")
    df = pd.DataFrame()

# --- APP LOGIC ---
st.title("🏎️ COGLI Vocab")

# 1. TIER SELECTION
st.subheader("Select Vocabulary Tiers")
cols = st.columns(3)
with cols[0]: maintenance = st.checkbox("Maintenance", value=True)
with cols[1]: advanced = st.checkbox("Advanced", value=True)
with cols[2]: specialized = st.checkbox("Specialized", value=True)

if st.button("▶ START VOCAB QUIZ", kind="primary"):
    st.session_state.quiz_active = True
    st.session_state.current_index = 0

# --- COGLI QUICK INGEST CONSOLE (CLEAN & PERSISTENT) ---
st.divider()
st.subheader("📥 COGLI Quick Ingest")

# State Initialization
if "ingest_word" not in st.session_state: st.session_state.ingest_word = None
if "ingest_def" not in st.session_state: st.session_state.ingest_def = None
if "last_audio_b64" not in st.session_state: st.session_state.last_audio_b64 = ""

# Hidden Data Bridge
audio_b64 = st.text_input("audio_bridge", key="audio_b64", label_visibility="collapsed")

# Input Row
col1, col2 = st.columns(2)

with col1:
    import streamlit.components.v1 as components
    components.html("""
    <div style="display: flex; justify-content: center; margin-top: 0px;">
        <button id="cogli-mic" style="width: 100%; height: 45px; font-size: 16px; font-weight: bold; background-color: #FF4B4B; color: white; border: none; border-radius: 8px; cursor: pointer; text-transform: uppercase;">
            🎤 Voice
        </button>
    </div>
    <script>
        const btn = document.getElementById('cogli-mic');
        btn.onclick = async () => {
            btn.innerText = "🔴 LISTENING...";
            btn.style.backgroundColor = "#cc0000";
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                const mediaRecorder = new MediaRecorder(stream);
                const audioChunks = [];
                mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
                mediaRecorder.onstop = () => {
                    btn.innerText = "⏳ PROCESSING...";
                    const blob = new Blob(audioChunks, { type: 'audio/webm' });
                    const reader = new FileReader();
                    reader.readAsDataURL(blob);
                    reader.onloadend = () => {
                        const base64String = reader.result;
                        const parentDoc = window.parent.document;
                        const inputs = parentDoc.querySelectorAll('input[aria-label="audio_bridge"]');
                        if (inputs.length > 0) {
                            const hiddenInput = inputs[0];
                            const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                            nativeSetter.call(hiddenInput, base64String);
                            hiddenInput.dispatchEvent(new Event('input', { bubbles: true }));
                        }
                        setTimeout(() => { btn.innerText = "🎤 Voice"; btn.style.backgroundColor = "#FF4B4B"; }, 1500);
                    };
                };
                mediaRecorder.start();
                setTimeout(() => { 
                    mediaRecorder.stop(); 
                    stream.getTracks().forEach(t => t.stop());
                }, 3000); 
            } catch (err) { btn.innerText = "❌ MIC ERROR"; }
        };
    </script>
    """, height=50)

with col2:
    text_input = st.text_input("TEXT_ENTRY", key="text_lookup_input", placeholder="TYPE WORD HERE...", label_visibility="collapsed")
    if text_input and text_input.strip().upper() != st.session_state.ingest_word:
        st.session_state.ingest_word = text_input.strip().upper()
        st.session_state.ingest_def = None

# Audio Processing
if audio_b64 and audio_b64 != st.session_state.last_audio_b64:
    st.session_state.last_audio_b64 = audio_b64
    with st.spinner("Transcribing..."):
        try:
            b64_data = audio_b64.split(",")[1]
            audio_file = io.BytesIO(base64.b64decode(b64_data))
            audio_file.name = "audio.webm"
            transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
            st.session_state.ingest_word = transcript.text.strip().strip('.').upper()
            st.session_state.ingest_def = None
            st.rerun()
        except: pass

# Results & Commit
if st.session_state.ingest_word:
    st.markdown(f"**TARGET WORD:** `{st.session_state.ingest_word}`")
    if not st.session_state.ingest_def:
        with st.spinner("Defining..."):
            response = client.chat.completions.create(
                model="gpt-4o",
                temperature=0.0,
                messages=[
                    {"role": "system", "content": "Provide definition using OED/Cambridge. Format: 'DEFINITION: [Text] NUANCE: [Cognitive Hook]'"},
                    {"role": "user", "content": f"Define: {st.session_state.ingest_word}"}
                ]
            )
            st.session_state.ingest_def = response.choices[0].message.content
    st.info(st.session_state.ingest_def)
    if st.button("COMMIT THIS WORD TO THE VOCABULARY DATABASE", use_container_width=True):
        st.warning("Database Write-back connection is the final step.")
