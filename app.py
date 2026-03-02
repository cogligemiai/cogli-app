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

# --- CSS (ALIGNMENT & HIDDEN BRIDGE) ---
st.markdown("""
<style>
    /* 1. Force the Voice Button and Text Input to be identical heights */
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
        text-transform: uppercase !important;
    }

    /* 2. Physically hide the technical bridge triggers from the UI */
    div:has(> input[aria-label="bridge_storage"]),
    div:has(> button[key="bridge_trigger"]) {
        display: none !important;
        height: 0px !important;
    }
    
    /* 3. Ensure columns are level */
    [data-testid="column"] {
        display: flex;
        align-items: flex-end;
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

st.subheader("Select Vocabulary Tiers")
cols = st.columns(3)
with cols[0]: st.checkbox("Maintenance", value=True)
with cols[1]: st.checkbox("Advanced", value=True)
with cols[2]: st.checkbox("Specialized", value=True)
st.button("▶ START VOCAB QUIZ", type="primary")

st.divider()
st.subheader("📥 COGLI Vocab Lookup")

# --- THE HARDENED BRIDGE (Technical - Hidden by CSS) ---
bridge_data = st.text_input("bridge_storage", key="bridge_storage", label_visibility="collapsed")
# Removed label_visibility from button to fix TypeError; CSS now handles hiding it
bridge_trigger = st.button("bridge_click", key="bridge_trigger")

# --- THE UNIFIED INPUT ROW ---
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
                        const storage = Array.from(parentDoc.querySelectorAll('input')).find(el => el.getAttribute('aria-label') === 'bridge_storage');
                        const trigger = Array.from(parentDoc.querySelectorAll('button')).find(el => el.innerText === 'bridge_click');
                        
                        if (storage && trigger) {
                            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                            setter.call(storage, reader.result);
                            storage.dispatchEvent(new Event('input', { bubbles: true }));
                            setTimeout(() => { trigger.click(); }, 100);
                        }
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
    # This function handles the manual typing update
    def sync_text():
        st.session_state.ingest_word = st.session_state.main_input.upper()
        st.session_state.ingest_def = None

    # THE UNIFIED BOX: value is tied to state so voice transcription appears here too
    st.text_input(
        "WORD_ENTRY", 
        value=st.session_state.ingest_word, 
        key="main_input", 
        on_change=sync_text,
        placeholder="TYPE OR SPEAK...", 
        label_visibility="collapsed"
    )

# --- VOICE PROCESSING (Triggered by Hidden Button) ---
if bridge_trigger and bridge_data:
    with st.status("⏳ TRANSCRIBING VOICE...") as status:
        try:
            b64_data = bridge_data.split(",")[1]
            audio_file = io.BytesIO(base64.b64decode(b64_data))
            audio_file.name = "audio.webm"
            transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
            st.session_state.ingest_word = transcript.text.strip().strip('.').upper()
            st.session_state.ingest_def = None
            status.update(label="✅ DONE!", state="complete", expanded=False)
            st.rerun()
        except:
            status.update(label="❌ ERROR", state="error")

# --- RESULTS AREA ---
if st.session_state.ingest_word:
    st.markdown(f"**WORD:** `{st.session_state.ingest_word}`")
    
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
        st.success(f"STAGED: {st.session_state.ingest_word}. Writing to Drive...")
