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

# --- CSS (ULTRA-PRECISION ALIGNMENT) ---
st.markdown("""
<style>
    /* 1. Header Styling */
    .word-label { font-size: 24px; color: white; }
    .blue-word { color: #1E90FF; font-size: 42px; font-weight: bold; text-transform: uppercase; }
    
    /* 2. Symmetrical Ingest Console Alignment */
    [data-testid="column"] {
        display: flex;
        align-items: flex-end; /* Force vertical alignment */
    }

    div[data-testid="stTextInput"] input {
        height: 45px !important;
        font-size: 16px !important;
        text-transform: uppercase !important;
        margin-bottom: 0px !important;
    }
    
    .stButton > button {
        width: 100% !important;
        height: 45px !important; /* Matches Input Box */
        font-size: 16px !important;
        font-weight: bold !important;
        border-radius: 8px !important;
        text-transform: uppercase !important;
    }

    /* 3. The Active-Hidden Bridge (Invisible but functional) */
    div[data-testid="stVerticalBlock"] > div:has(input[aria-label="audio_bridge"]) {
        position: absolute !important;
        opacity: 0 !important;
        height: 0 !important;
        width: 0 !important;
        overflow: hidden !important;
        pointer-events: none !important;
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
if "last_audio_b64" not in st.session_state: st.session_state.last_audio_b64 = ""

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

# 1. THE ACTIVE-HIDDEN BRIDGE
audio_b64 = st.text_input("audio_bridge", key="audio_b64", label_visibility="collapsed")

# 2. THE SYMMETRICAL INPUT ROW
col1, col2 = st.columns(2)

with col1:
    import streamlit.components.v1 as components
    components.html("""
    <div style="display: flex; justify-content: center;">
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
                        const parentDoc = window.parent.document;
                        const inputs = Array.from(parentDoc.querySelectorAll('input'));
                        const bridge = inputs.find(el => el.getAttribute('aria-label') === 'audio_bridge');
                        
                        if (bridge) {
                            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                            setter.call(bridge, reader.result);
                            bridge.dispatchEvent(new Event('input', { bubbles: true }));
                        }
                        setTimeout(() => { btn.innerText = "🎤 Voice"; btn.style.backgroundColor = "#FF4B4B"; }, 2000);
                    };
                };
                mediaRecorder.start();
                setTimeout(() => { 
                    mediaRecorder.stop(); 
                    stream.getTracks().forEach(t => t.stop());
                }, 3000); 
            } catch (err) { btn.innerText = "❌ ERROR"; }
        };
    </script>
    """, height=50)

with col2:
    # THE UNIFIED BOX: Transcribed word lands here. Typing word stays here.
    word_box_input = st.text_input("WORD_HOLDER", value=st.session_state.ingest_word, key="main_word_input", placeholder="TYPE OR SPEAK...", label_visibility="collapsed")
    if word_box_input.upper() != st.session_state.ingest_word:
        st.session_state.ingest_word = word_box_input.upper()
        st.session_state.ingest_def = None

# 3. VOICE ENGINE PROCESSING
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
            st.rerun() # Refresh so the word appears in the box
        except: pass

# 4. RESULTS SECTION
if st.session_state.ingest_word != "":
    st.markdown(f"**DETECTED:** `{st.session_state.ingest_word}`")
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
        st.success(f"STAGED: {st.session_state.ingest_word}. Database logic is ready.")
