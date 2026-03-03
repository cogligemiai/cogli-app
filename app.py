import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
import time
import base64

# --- INITIALIZATION & IDENTITY ---
# MISSION: High-precision, deterministic PKM.
# SPELLING ENFORCEMENT: COGLI.
# TEMPERATURE: 0.0.

st.set_page_config(page_title="COGLI Vocab", page_icon="🏎️", layout="centered")

# --- AUTHENTICATION & CLIENTS ---
def init_clients():
    # OpenAI Client
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    
    # Google Sheets Client
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    gc = gspread.authorize(creds)
    sheet_id = "1KQ7VX8qS23Hfd9WQ_2PZ50XKpFtTLMz4UaZHQtWx54Q"
    sh = gc.open_by_key(sheet_id)
    worksheet = sh.get_worksheet(0)
    return client, worksheet

client, worksheet = init_clients()

# --- SESSION STATE MANAGEMENT ---
if "view" not in st.session_state:
    st.session_state.view = "LOOKUP"  # LOOKUP or QUIZ
if "quiz_mode" not in st.session_state:
    st.session_state.quiz_mode = "MANUAL" # MANUAL or CAR
if "current_index" not in st.session_state:
    st.session_state.current_index = 0
if "quiz_step" not in st.session_state:
    st.session_state.quiz_step = "INIT" # INIT, THINKING, REVEAL, RESOLUTION

# --- DATA ENGINE ---
def load_data():
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

def update_mastery(word, column):
    # Logic to increment R, W, or M in Google Sheets
    cell = worksheet.find(word)
    col_idx = {"R": 4, "W": 5, "M": 6}[column] # Assuming schema: Word, Def, Date, R, W, M
    current_val = int(worksheet.cell(cell.row, col_idx).value or 0)
    worksheet.update_cell(cell.row, col_idx, current_val + 1)

# --- AUDIO ENGINE (TTS) ---
def speak(text):
    response = client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=text
    )
    audio_base64 = base64.b64encode(response.content).decode('utf-8')
    audio_tag = f'<audio autoplay="true" src="data:audio/mp3;base64,{audio_base64}">'
    st.markdown(audio_tag, unsafe_allow_html=True)

# --- UI COMPONENTS: INGEST CONSOLE (v2.8) ---
def ingest_console():
    st.subheader("📥 COGLI Quick Ingest")
    
    # Unified Input Row
    col1, col2 = st.columns([1, 3])
    
    with col1:
        # JavaScript One-Tap Recorder (3-second auto-stop)
        st.markdown("""
            <button id="voiceBtn" style="width:100%; height:45px; background-color:#FF4B4B; color:white; border:none; border-radius:5px; font-weight:bold;">🎤 VOICE</button>
            <script>
            const btn = document.getElementById('voiceBtn');
            btn.onclick = function() {
                btn.innerText = "RECORDING...";
                btn.style.backgroundColor = "#000000";
                // Logic for 3-second capture would be injected here via Streamlit Custom Component
                // For now, this acts as a trigger for the Whisper logic
            }
            </script>
        """, unsafe_allow_html=True)

    with col2:
        word_input = st.text_input("", placeholder="TYPE WORD HERE...", label_visibility="collapsed")

    if word_input:
        st.info(f"Processing: {word_input}...")
        # Synthesis Logic: OED/Cambridge/Webster/Dictionary.com
        # (Placeholder for API synthesis)
        st.success(f"Word '{word_input}' synthesized and ready for COMMIT.")
        if st.button("COMMIT TO COGLI"):
            worksheet.append_row([word_input, "Definition Placeholder", time.strftime("%Y-%m-%d"), 0, 0, 0])
            st.balloons()

# --- UI COMPONENTS: QUIZ ENGINE ---
def quiz_engine():
    df = load_data()
    if st.session_state.current_index >= len(df):
        st.success("Session Complete!")
        if st.button("Return to Home"):
            st.session_state.view = "LOOKUP"
            st.rerun()
        return

    row = df.iloc[st.session_state.current_index]
    word = row['Word']
    correct_def = row['Definition']
    # Mocking options for deterministic display
    options = [correct_def, "To formally surrender or give up.", "To reach a final decision."]
    
    st.title(f"Word: {word}")
    
    # PERSISTENT BLOCK DISPLAY
    st.markdown(f"""
    **A)** {options[0]}  
    **B)** {options[1]}  
    **C)** {options[2]}
    """)

    # --- CAR MODE LOGIC (AUTONOMOUS) ---
    if st.session_state.quiz_mode == "CAR":
        if st.session_state.quiz_step == "INIT":
            speak(f"The word is {word}. Option A: {options[0]}. Option B: {options[1]}. Option C: {options[2]}.")
            st.session_state.quiz_step = "THINKING"
            st.rerun()

        elif st.session_state.quiz_step == "THINKING":
            time.sleep(12) # 12s Thinking Gap
            st.session_state.quiz_step = "REVEAL"
            st.rerun()

        elif st.session_state.quiz_step == "REVEAL":
            speak(f"The answer is A. DEFINITION: {correct_def}. NUANCE: Focus on the continuation after a pause.")
            st.session_state.quiz_step = "RESOLUTION"
            st.rerun()

        elif st.session_state.quiz_step == "RESOLUTION":
            time.sleep(8) # 8s Resolution Gap
            st.session_state.current_index += 1
            st.session_state.quiz_step = "INIT"
            st.rerun()

    # --- MANUAL MODE LOGIC ---
    else:
        cols = st.columns(3)
        if cols[0].button("A"):
            st.success("CORRECT")
            update_mastery(word, "R")
            time.sleep(1)
            st.session_state.current_index += 1
            st.rerun()
        if cols[1].button("B"):
            st.error("WRONG")
            update_mastery(word, "W")
        if cols[2].button("C"):
            st.error("WRONG")
            update_mastery(word, "W")
        
        if st.button("🌟 I MASTERED THIS"):
            update_mastery(word, "M")
            st.session_state.current_index += 1
            st.rerun()

# --- MAIN ROUTER ---
def main():
    st.sidebar.title("COGLI Control")
    st.session_state.quiz_mode = st.sidebar.radio("Mode", ["MANUAL", "CAR"])
    
    if st.sidebar.button("Start/Resume Quiz"):
        st.session_state.view = "QUIZ"
        st.session_state.quiz_step = "INIT"
    
    if st.sidebar.button("Home / Ingest"):
        st.session_state.view = "LOOKUP"

    if st.session_state.view == "LOOKUP":
        st.title("🏎️ COGLI Vocab")
        ingest_console()
    else:
        quiz_engine()

if __name__ == "__main__":
    main()
