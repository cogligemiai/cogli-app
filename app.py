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
st.set_page_config(page_title="COGLI Driving Mode", layout="centered")

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
    try:
        response = client.audio.speech.create(model="tts-1", voice="alloy", input=text)
        b64 = base64.b64encode(response.content).decode()
        md = f'<audio autoplay="true"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>'
        st.markdown(md, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Voice Error: {e}")

# --- APP UI ---
df = load_data()

if df is not None:
    st.title("🚗 COGLI Driving Mode")

    # Initialize session state for the loop
    if 'drive_loop_active' not in st.session_state:
        st.session_state.drive_loop_active = False

    # Get a random word
    row = df.iloc[random.randint(0, len(df)-1)]
    word, correct_def, nuance = row['Word'], row['Definition'], row.get('Nuance', 'No nuance provided.')
    
    # Generate options
    others = df[df['Definition'] != correct_def]['Definition'].sample(2).tolist()
    opts = [correct_def] + others
    random.shuffle(opts)
    correct_letter = chr(65 + opts.index(correct_def))

    st.markdown(f"### **Word:** {word.upper()}")
    st.write(f"**A:** {opts[0]}\n\n**B:** {opts[1]}\n\n**C:** {opts[2]}")
    st.divider()

    # --- DRIVING LOOP LOGIC ---
    if not st.session_state.drive_loop_active:
        if st.button("▶️ START DRIVING LOOP", type="primary"):
            st.session_state.drive_loop_active = True
            st.rerun() # Immediately restart the script in active mode
    
    if st.session_state.drive_loop_active:
        st.success("Audio Loop is Active...")
        
        # 1. The Challenge
        speak(f"The word is {word}. Option A: {opts[0]}. Option B: {opts[1]}. Option C: {opts[2]}.")
        
        # 2. The Cognitive Pause
        placeholder = st.empty()
        for i in range(10, 0, -1):
            placeholder.metric("Thinking time...", f"{i}s")
            time.sleep(1)
        
        # 3. The Resolution
        speak(f"The correct answer is {correct_letter}: {correct_def}. Nuance: {nuance}.")
        time.sleep(5) # Pause after resolution
        
        # 4. Automatically transition to the next word
        st.rerun()

else:
    st.warning("Connecting to COGLI Data...")
```After pasting, click **"Commit changes..."**.

#### **Step 2: Reboot the App**
1.  Go to your app's URL.
2.  Click **"Manage app"** in the bottom right.
3.  Click the **three dots (⋮)** at the top of the sidebar.
4.  Select **"Reboot app"**.

---

### **DETERMINISTIC VERIFICATION**

1.  Open your **Driving Mode URL** on your phone.
2.  You will see the first word and a single, large **`▶️ START DRIVING LOOP`** button.
3.  **Tap this button once.**
4.  The app will immediately speak the challenge, begin the 10-second countdown, speak the answer, and then **automatically load the next word and continue the loop without any further interaction.**

**Confirm once you have tested the "One-Tap Start" and the automatic loop is functioning correctly!**

---
PROVENANCE WORD: RESUME
