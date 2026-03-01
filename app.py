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
st.set_page_config(page_title="COGLI PKM", layout="centered")

# --- ENGINES (Cached to run only once) ---
@st.cache_resource
def init_engines():
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    creds_info = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n").strip()
    creds = service_account.Credentials.from_service_account_info(creds_info)
    drive_service = build('drive', 'v3', credentials=creds)
    return client, drive_service

client, drive_service = init_engines()

@st.cache_data(ttl=300)
def load_data():
    results = drive_service.files().list(q="name contains 'VOCAB_COGLI_MASTER_CLEAN'", fields="files(id, name, mimeType)").execute()
    items = results.get('files', [])
    if not items: return None
    target = items[0]
    request = drive_service.files().get_media(fileId=target['id']) if target['mimeType'] != 'application/vnd.google-apps.spreadsheet' else drive_service.files().export_media(fileId=target['id'], mimeType='text/csv')
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done: status, done = downloader.next_chunk()
    fh.seek(0)
    return pd.read_csv(fh)

def speak(text):
    response = client.audio.speech.create(model="tts-1", voice="alloy", input=text)
    b64 = base64.b64encode(response.content).decode()
    md = f'<audio autoplay="true"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>'
    st.markdown(md, unsafe_allow_html=True)

# --- APP ROUTER ---
df = load_data()

if df is not None:
    # Check URL for ?mode=drive to auto-start driving mode
    if st.query_params.get("mode") == "drive":
        st.title("🚗 COGLI Driving Mode")
        st.header("Loop Active...")
        
        row = df.iloc[random.randint(0, len(df)-1)]
        word, correct_def, nuance = row['Word'], row['Definition'], row.get('Nuance', 'No nuance provided.')
        
        others = df[df['Definition'] != correct_def]['Definition'].sample(2).tolist()
        opts = [correct_def] + others
        random.shuffle(opts)
        correct_letter = chr(65 + opts.index(correct_def))

        st.markdown(f"### **Word:** {word.upper()}")
        st.write(f"**A:** {opts[0]}\n\n**B:** {opts[1]}\n\n**C:** {opts[2]}")
        
        speak(f"The word is {word}. Option A: {opts[0]}. Option B: {opts[1]}. Option C: {opts[2]}.")
        time.sleep(15) # Cognitive Pause
        speak(f"The correct answer is {correct_letter}: {correct_def}. Nuance: {nuance}.")
        time.sleep(5) # Transition Pause
        st.rerun()

    else: # Default to Quiz Mode
        st.title("🎯 COGLI Vocabulary Quiz")
        
        if 'index' not in st.session_state:
            st.session_state.index = random.randint(0, len(df)-1)
            st.session_state.options = []
            st.session_state.answered = False

        row = df.iloc[st.session_state.index]
        word, correct_def, nuance = row['Word'], row['Definition'], row.get('Nuance', 'No nuance provided.')

        if not st.session_state.options:
            others = df[df['Definition'] != correct_def]['Definition'].sample(2).tolist()
            opts = [correct_def] + others
            random.shuffle(opts)
            st.session_state.options = opts

        st.subheader(f"Word: :blue[{word}]")
        
        with st.form("quiz_form"):
            choice = st.radio("Select the correct definition:", st.session_state.options, key=f"q_{st.session_state.index}")
            if st.form_submit_button("Submit"):
                st.session_state.answered = True
                if choice == correct_def:
                    st.success(f"✅ **CORRECT!**")
                    st.info(f"**NUANCE:** {nuance}")
                else:
                    st.error(f"❌ **INCORRECT.** Correct answer: {correct_def}")
        
        if st.session_state.answered and st.button("Next Word ➡️"):
            st.session_state.index = random.randint(0, len(df)-1)
            st.session_state.options = []
            st.session_state.answered = False
            st.rerun()
else:
    st.warning("Connecting to COGLI Data...")
