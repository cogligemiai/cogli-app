import streamlit as st
import pandas as pd
import json
import io
import base64
import random
from openai import OpenAI
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# --- CONFIGURATION ---
st.set_page_config(page_title="COGLI Vocab", page_icon="🏎️", layout="centered")

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .word-label { font-size: 24px; color: white; margin-bottom: 10px; }
    .blue-word { color: #1E90FF; font-size: 42px; font-weight: bold; text-transform: uppercase; margin-bottom: 20px; }
    .option-box { display: flex; align-items: flex-start; margin-bottom: 15px; font-size: 18px; line-height: 1.4; }
    .option-label { min-width: 40px; font-weight: bold; color: #1E90FF; }
    .option-text { flex: 1; }
    div[data-testid="stTextInput"] input { height: 45px !important; font-size: 16px !important; text-transform: uppercase !important; }
    .stButton > button { width: 100% !important; height: 45px !important; font-size: 16px !important; font-weight: bold !important; border-radius: 8px !important; text-transform: uppercase !important; }
    div[data-testid="stVerticalBlock"] > div:has(input[aria-label="audio_bridge"]) { position: absolute !important; opacity: 0 !important; height: 0 !important; width: 0 !important; overflow: hidden !important; pointer-events: none !important; }
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
    # UPDATED TO YOUR CORRECT FILE ID
    file_id = "1KQ7VX8qS23Hfd9WQ_2PZ50XKpFtTLMz4UaZHQtWx54Q"
    try:
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.seek(0)
        data = pd.read_csv(fh)
        data.columns = data.columns.str.strip()
        
        # Fix for the "Actually we go" header in Column A
        if data.columns[0] != "Word":
            data.rename(columns={data.columns[0]: "Word"}, inplace=True)
            
        return data
    except Exception as e:
        st.error(f"Drive Error: {e}")
        return pd.DataFrame()

df = load_data()

# --- STATE MANAGEMENT ---
if "quiz_active" not in st.session_state: st.session_state.quiz_active = False
if "current_word" not in st.session_state: st.session_state.current_word = None
if "options" not in st.session_state: st.session_state.options = []
if "user_choice" not in st.session_state: st.session_state.user_choice = None
if "active_word" not in st.session_state: st.session_state.active_word = ""
if "active_def" not in st.session_state: st.session_state.active_def = None
if "last_audio_b64" not in st.session_state: st.session_state.last_audio_b64 = ""

# --- UI ---
st.title("🏎️ COGLI Vocab")

# 1. TIER SELECTION & QUIZ START
if not st.session_state.quiz_active:
    st.subheader("Select Vocabulary Tiers")
    cols = st.columns(3)
    with cols[0]: m_tier = st.checkbox("Maintenance", value=True)
    with cols[1]: a_tier = st.checkbox("Advanced", value=True)
    with cols[2]: s_tier = st.checkbox("Specialized", value=True)
    
    if st.button("▶ START VOCAB QUIZ", type="primary"):
        selected_tiers = []
        if m_tier: selected_tiers.append(1)
        if a_tier: selected_tiers.append(2)
        if s_tier: selected_tiers.append(3)
        
        if not df.empty and 'Level' in df.columns:
            filtered_df = df[df['Level'].isin(selected_tiers)]
            if not filtered_df.empty:
                st.session_state.quiz_active = True
                st.session_state.current_word = filtered_df.sample(1).iloc[0]
                distractors = df[df['Word'] != st.session_state.current_word['Word']].sample(2)['Definition'].tolist()
                options = distractors + [st.session_state.current_word['Definition']]
                random.shuffle(options)
                st.session_state.options = options
                st.rerun()
        else:
            st.error("Could not find 'Level' column or data is empty.")

# 2. THE QUIZ ENGINE
if st.session_state.quiz_active and st.session_state.current_word is not None:
    word = st.session_state.current_word['Word']
    st.markdown(f"<div class='word-label'>The word is...</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='blue-word'>{word}</div>", unsafe_allow_html=True)

    labels = ["A", "B", "C"]
    for i, opt in enumerate(st.session_state.options):
        st.markdown(f"<div class='option-box'><div class='option-label'>{labels[i]}:</div><div class='option-text'>{opt}</div></div>", unsafe_allow_html=True)

    if st.session_state.user_choice is None:
        choice_cols = st.columns(3)
        if choice_cols[0].button("A"): st.session_state.user_choice = st.session_state.options[0]
        if choice_cols[1].button("B"): st.session_state.user_choice = st.session_state.options[1]
        if choice_cols[2].button("C"): st.session_state.user_choice = st.session_state.options[2]
        if st.session_state.user_choice: st.rerun()
    else:
        if st.session_state.user_choice == st.session_state.current_word['Definition']:
            st.success("CORRECT")
        else:
            st.error(f"INCORRECT. Correct answer: {st.session_state.current_word['Definition']}")
        
        # Use 'M' column as fallback for Nuance if needed
        nuance = st.session_state.current_word.get('Nuance') or st.session_state.current_word.get('M')
        st.info(f"**NUANCE:** {nuance}")
        
        if st.button("NEXT WORD ▶"):
            st.session_state.current_word = None
            st.session_state.user_choice = None
            st.session_state.quiz_active = False
            st.rerun()

# 3. COGLI VOCAB LOOKUP
st.divider()
st.subheader("📥 COGLI Vocab Lookup")
audio_b64 = st.text_input("audio_bridge", key="audio_b64", label_visibility="collapsed")

col1, col2 = st.columns(2)
with col1:
    import streamlit.components.v1 as components
    components.html("""
    <div style="display: flex; justify-content: center;"><button id="cogli-mic" style="width: 100%; height: 45px; font-size: 16px; font-weight: bold; background-color: #FF4B4B; color: white; border: none; border-radius: 8px; cursor: pointer; text-transform: uppercase;">🎤 Voice</button></div>
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
                        const bridge = Array.from(parentDoc.querySelectorAll('input')).find(el => el.getAttribute('aria-label') === 'audio_bridge');
                        if (bridge) {
                            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                            setter.call(bridge, reader.result);
                            bridge.dispatchEvent(new Event('input', { bubbles: true }));
                        }
                        setTimeout(() => { btn.innerText = "🎤 Voice"; btn.style.backgroundColor = "#FF4B4B"; }, 1500);
                    };
                };
                mediaRecorder.start();
                setTimeout(() => { mediaRecorder.stop(); stream.getTracks().forEach(t => t.stop()); }, 3000); 
            } catch (err) { btn.innerText = "❌ ERROR"; }
        };
    </script>
    """, height=50)

with col2:
    text_input = st.text_input("WORD_ENTRY", key="manual_entry", placeholder="TYPE WORD HERE...", label_visibility="collapsed")
    if text_input and text_input.upper() != st.session_state.active_word:
        st.session_state.active_word = text_input.upper()
        st.session_state.active_def = None

if audio_b64 and audio_b64 != st.session_state.last_audio_b64:
    st.session_state.last_audio_b64 = audio_b64
    with st.spinner("⏳ TRANSCRIBING..."):
        try:
            b64_data = audio_b64.split(",")[1]
            audio_file = io.BytesIO(base64.b64decode(b64_data))
            audio_file.name = "audio.webm"
            transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
            st.session_state.active_word = transcript.text.strip().strip('.').upper()
            st.session_state.active_def = None
            st.rerun()
        except: pass

if st.session_state.active_word:
    st.markdown(f"**WORD DETECTED:** <span class='detected-word'>{st.session_state.active_word}</span>", unsafe_allow_html=True)
    if not st.session_state.active_def:
        with st.spinner("Defining..."):
            response = client.chat.completions.create(model="gpt-4o", temperature=0.0, messages=[{"role": "system", "content": "Format: 'DEFINITION: [Text] NUANCE: [Cognitive Hook]'"},{"role": "user", "content": f"Define: {st.session_state.active_word}"}])
            st.session_state.active_def = response.choices[0].message.content
    st.info(st.session_state.active_def)
    if st.button("COMMIT WORD TO VOCABULARY DATABASE", use_container_width=True):
        st.success(f"STAGED: {st.session_state.active_word}")
