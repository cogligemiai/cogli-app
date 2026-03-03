import streamlit as st
import pandas as pd
import json
import io
import base64
import random
import time
from openai import OpenAI
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

# --- CONFIGURATION ---
st.set_page_config(page_title="COGLI Vocab", page_icon="🏎️", layout="centered")

# --- CSS (SYMMETRY & CAR MODE STYLING) ---
st.markdown("""
<style>
    .word-label { font-size: 24px; color: white; }
    .blue-word { color: #1E90FF; font-size: 42px; font-weight: bold; text-transform: uppercase; }
    .option-box { display: flex; align-items: flex-start; margin-bottom: 15px; font-size: 18px; line-height: 1.4; }
    .option-label { min-width: 40px; font-weight: bold; color: #1E90FF; }
    
    /* Symmetrical Buttons */
    .stButton > button {
        width: 100% !important;
        height: 45px !important;
        font-size: 18px !important;
        font-weight: bold !important;
        border-radius: 8px !important;
        text-transform: uppercase !important;
    }
    
    /* Hidden Bridge */
    div[data-testid="stVerticalBlock"] > div:has(input[aria-label="audio_bridge"]) {
        position: absolute !important;
        opacity: 0 !important;
        height: 0 !important;
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
FILE_ID = "1KQ7VX8qS23Hfd9WQ_2PZ50XKpFtTLMz4UaZHQtWx54Q"

# --- UTILITIES ---
def speak(text):
    """Generates and plays audio using OpenAI TTS."""
    response = client.audio.speech.create(model="tts-1", voice="alloy", input=text)
    b64 = base64.b64encode(response.content).decode()
    md = f'<audio autoplay="true" src="data:audio/mp3;base64,{b64}">'
    st.markdown(md, unsafe_allow_html=True)

@st.cache_data
def load_data():
    request = drive_service.files().export(fileId=FILE_ID, mimeType='text/csv')
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.seek(0)
    data = pd.read_csv(fh)
    data.columns = data.columns.str.strip()
    return data

def commit_to_db(word, definition):
    current_df = load_data()
    new_row = pd.DataFrame([{"Word": word, "Definition": definition, "Date": pd.Timestamp.now().strftime('%Y-%m-%d'), "R": 0, "W": 0, "M": 1, "Level": 1}])
    updated_df = pd.concat([current_df, new_row], ignore_index=True)
    csv_buffer = io.StringIO()
    updated_df.to_csv(csv_buffer, index=False)
    media = MediaIoBaseUpload(io.BytesIO(csv_buffer.getvalue().encode()), mimetype='text/csv')
    drive_service.files().update(fileId=FILE_ID, media_body=media).execute()
    st.cache_data.clear()
    return True

# --- STATE MANAGEMENT ---
if "quiz_active" not in st.session_state: st.session_state.quiz_active = False
if "quiz_mode" not in st.session_state: st.session_state.quiz_mode = "Manual"
if "current_word" not in st.session_state: st.session_state.current_word = None
if "options" not in st.session_state: st.session_state.options = []
if "user_choice" not in st.session_state: st.session_state.user_choice = None
if "active_word" not in st.session_state: st.session_state.active_word = ""
if "active_def" not in st.session_state: st.session_state.active_def = None
if "last_audio_b64" not in st.session_state: st.session_state.last_audio_b64 = ""

# --- UI ---
st.title("🏎️ COGLI Vocab")

# 1. QUIZ SETUP
if not st.session_state.quiz_active:
    st.subheader("Quiz Settings")
    st.session_state.quiz_mode = st.radio("Select Mode", ["Manual", "Car Mode (Autonomous)"], horizontal=True)
    
    cols = st.columns(3)
    with cols[0]: m_tier = st.checkbox("Maintenance", value=True)
    with cols[1]: a_tier = st.checkbox("Advanced", value=True)
    with cols[2]: s_tier = st.checkbox("Specialized", value=True)
    
    if st.button("▶ START QUIZ", type="primary"):
        df = load_data()
        selected_tiers = []
        if m_tier: selected_tiers.append(1)
        if a_tier: selected_tiers.append(2)
        if s_tier: selected_tiers.append(3)
        
        filtered_df = df[df['Level'].isin(selected_tiers)]
        if not filtered_df.empty:
            st.session_state.quiz_active = True
            st.session_state.current_word = filtered_df.sample(1).iloc[0]
            distractors = df[df['Word'] != st.session_state.current_word['Word']].sample(2)['Definition'].tolist()
            st.session_state.options = distractors + [st.session_state.current_word['Definition']]
            random.shuffle(st.session_state.options)
            st.rerun()

# 2. QUIZ ENGINE
if st.session_state.quiz_active and st.session_state.current_word is not None:
    word = st.session_state.current_word['Word']
    st.markdown(f"<div class='word-label'>The word is...</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='blue-word'>{word}</div>", unsafe_allow_html=True)
    
    labels = ["A", "B", "C"]
    for i, opt in enumerate(st.session_state.options):
        st.markdown(f"<div class='option-box'><div class='option-label'>{labels[i]}:</div><div class='option-text'>{opt}</div></div>", unsafe_allow_html=True)

    # --- CAR MODE LOGIC ---
    if st.session_state.quiz_mode == "Car Mode (Autonomous)":
        if st.session_state.user_choice is None:
            # Speak the question
            q_text = f"The word is {word}. Option A: {st.session_state.options[0]}. Option B: {st.session_state.options[1]}. Option C: {st.session_state.options[2]}. What is your choice?"
            speak(q_text)
            
            # Voice Answer Bridge
            audio_b64_quiz = st.text_input("audio_bridge_quiz", key="audio_bridge_quiz", label_visibility="collapsed")
            import streamlit.components.v1 as components
            components.html("""
                <button id="quiz-mic" style="width: 100%; height: 80px; font-size: 20px; font-weight: bold; background-color: #FF4B4B; color: white; border: none; border-radius: 10px; cursor: pointer;">🎤 TAP & SAY A, B, or C</button>
                <script>
                    const btn = document.getElementById('quiz-mic');
                    btn.onclick = async () => {
                        btn.innerText = "🔴 LISTENING...";
                        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                        const mediaRecorder = new MediaRecorder(stream);
                        const chunks = [];
                        mediaRecorder.ondataavailable = e => chunks.push(e.data);
                        mediaRecorder.onstop = () => {
                            const blob = new Blob(chunks, { type: 'audio/webm' });
                            const reader = new FileReader();
                            reader.readAsDataURL(blob);
                            reader.onloadend = () => {
                                const parentDoc = window.parent.document;
                                const bridge = Array.from(parentDoc.querySelectorAll('input')).find(el => el.getAttribute('aria-label') === 'audio_bridge_quiz');
                                if (bridge) {
                                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                                    setter.call(bridge, reader.result);
                                    bridge.dispatchEvent(new Event('input', { bubbles: true }));
                                }
                            };
                        };
                        mediaRecorder.start();
                        setTimeout(() => { mediaRecorder.stop(); stream.getTracks().forEach(t => t.stop()); }, 2000);
                    };
                </script>
            """, height=100)
            
            if audio_bridge_quiz := st.session_state.get("audio_bridge_quiz"):
                if "data:audio" in audio_bridge_quiz:
                    b64_data = audio_bridge_quiz.split(",")[1]
                    transcript = client.audio.transcriptions.create(model="whisper-1", file=io.BytesIO(base64.b64decode(b64_data)))
                    ans = transcript.text.strip().upper()
                    if "A" in ans: st.session_state.user_choice = st.session_state.options[0]
                    elif "B" in ans: st.session_state.user_choice = st.session_state.options[1]
                    elif "C" in ans: st.session_state.user_choice = st.session_state.options[2]
                    st.rerun()

    # --- MANUAL MODE LOGIC ---
    else:
        if st.session_state.user_choice is None:
            choice_cols = st.columns(3)
            if choice_cols[0].button("A"): st.session_state.user_choice = st.session_state.options[0]
            if choice_cols[1].button("B"): st.session_state.user_choice = st.session_state.options[1]
            if choice_cols[2].button("C"): st.session_state.user_choice = st.session_state.options[2]
            if st.session_state.user_choice: st.rerun()

    # --- RESOLUTION ---
    if st.session_state.user_choice:
        is_correct = st.session_state.user_choice == st.session_state.current_word['Definition']
        res_text = "Correct!" if is_correct else f"Incorrect. The correct answer was {st.session_state.current_word['Definition']}."
        nuance = st.session_state.current_word.get('Nuance', '')
        
        if is_correct: st.success(res_text)
        else: st.error(res_text)
        st.info(f"**NUANCE:** {nuance}")
        
        if st.session_state.quiz_mode == "Car Mode (Autonomous)":
            speak(f"{res_text}. Nuance: {nuance}. Moving to next word.")
            time.sleep(3)
            st.session_state.current_word = None
            st.session_state.user_choice = None
            st.rerun()
        else:
            if st.button("NEXT WORD ▶"):
                st.session_state.current_word = None
                st.session_state.user_choice = None
                st.rerun()

# 3. LOOKUP SECTION
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
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mediaRecorder = new MediaRecorder(stream);
            const chunks = [];
            mediaRecorder.ondataavailable = e => chunks.push(e.data);
            mediaRecorder.onstop = () => {
                const blob = new Blob(chunks, { type: 'audio/webm' });
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
                };
            };
            mediaRecorder.start();
            setTimeout(() => { mediaRecorder.stop(); stream.getTracks().forEach(t => t.stop()); }, 3000); 
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
            transcript = client.audio.transcriptions.create(model="whisper-1", file=io.BytesIO(base64.b64decode(b64_data)))
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
        if commit_to_db(st.session_state.active_word, st.session_state.active_def):
            st.success(f"COMMITTED: {st.session_state.active_word}")
            st.session_state.active_word = ""
            st.session_state.active_def = None
