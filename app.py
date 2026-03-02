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
st.set_page_config(page_title="COGLI Vocab", page_icon="🚗", layout="centered")

# --- CUSTOM "IUI" CSS ---
st.markdown("""
    <style>
    /* The Word Header */
    .word-label { font-size: 24px; font-weight: normal; color: white; }
    .blue-word { color: #1E90FF; font-size: 42px; font-weight: bold; text-transform: uppercase; }
    
    /* Hanging Indent for A, B, C */
    .option-box {
        display: flex;
        align-items: flex-start;
        margin-bottom: 15px;
        font-size: 18px;
        line-height: 1.4;
    }
    .option-label {
        min-width: 50px; 
        font-weight: bold;
    }
    .option-text {
        flex: 1;
    }

    /* Button Geometry - Wide and Short */
    .stButton > button {
        width: 100% !important;
        height: 3em !important;
        font-size: 16px !important;
        font-weight: bold !important;
        border-radius: 10px !important;
    }
    
    /* Start Button - Red */
    div.stButton > button[kind="primary"] {
        background-color: #FF4B4B !important;
        color: white !important;
        border: none !important;
        height: 3.5em !important;
        font-size: 20px !important;
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
    except: return None, None

client, drive_service = init_engines()

@st.cache_data(ttl=10)
def load_data():
    if not drive_service: return None
    try:
        results = drive_service.files().list(q="name contains 'VOCAB_COGLI_MASTER_CLEAN'", fields="files(id, name, mimeType)").execute()
        items = results.get('files',[])
        if not items: return None
        target = items[0]
        request = drive_service.files().get_media(fileId=target['id']) if target['mimeType'] != 'application/vnd.google-apps.spreadsheet' else drive_service.files().export_media(fileId=target['id'], mimeType='text/csv')
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done: status, done = downloader.next_chunk()
        fh.seek(0)
        return pd.read_csv(fh)
    except: return None

def get_audio_html(text):
    if not client: return ""
    try:
        response = client.audio.speech.create(model="tts-1", voice="alloy", input=text)
        b64 = base64.b64encode(response.content).decode()
        rnd_id = random.randint(1000, 999999)
        return f'<audio id="audio-{rnd_id}" autoplay="true" preload="auto"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>'
    except: return ""

def generate_word_bundle(df, is_first=False):
    row = df.iloc[random.randint(0, len(df)-1)]
    word = str(row.iloc[0]) 
    correct_def = str(row.iloc[1]) 
    
    nuance_text = ""
    if 'Nuance' in df.columns:
        raw_n = str(row['Nuance']).strip()
        if raw_n.lower() not in ['', 'nan', 'none', 'no nuance provided.']:
            nuance_text = f" {raw_n}"

    others = df[df.iloc[:, 1] != correct_def].iloc[:, 1].sample(min(2, len(df)-1)).tolist()
    opts = [correct_def] + others
    random.shuffle(opts)
    correct_letter = chr(65 + opts.index(correct_def))

    prefix = "First word" if is_first else "Next word"
    challenge_text = f"{prefix}. {word}. Option A: {opts[0]}. Option B: {opts[1]}. Option C: {opts[2]}."
    answer_text = f"The correct answer is {correct_letter}. {correct_def}.{nuance_text}"

    return {
        'word': word, 'opts': opts, 'correct_letter': correct_letter,
        'challenge_text': challenge_text, 'answer_text': answer_text,
        'challenge_audio': get_audio_html(challenge_text),
        'answer_audio': get_audio_html(answer_text)
    }

# --- APP UI ---
if not client or not drive_service:
    st.error("Credentials Error: Check Secrets.")
    st.stop()

df_master = load_data()

if df_master is not None:
    st.title("🚗 COGLI Vocab")
    
    if 'loop_running' not in st.session_state:
        st.session_state.loop_running = False
        st.session_state.welcome_played = False
        st.session_state.is_first_word = True
    if 'selected_tiers' not in st.session_state:
        st.session_state.selected_tiers = [2] 

    # --- START SCREEN ---
    if not st.session_state.loop_running:
        st.write("### Select Vocabulary Tiers")
        t_col1, t_col2, t_col3 = st.columns(3)
        
        with t_col1:
            if st.button("Maintenance", type="primary" if 1 in st.session_state.selected_tiers else "secondary"):
                if 1 in st.session_state.selected_tiers: st.session_state.selected_tiers.remove(1)
                else: st.session_state.selected_tiers.append(1)
                st.rerun()
        with t_col2:
            if st.button("Advanced", type="primary" if 2 in st.session_state.selected_tiers else "secondary"):
                if 2 in st.session_state.selected_tiers: st.session_state.selected_tiers.remove(2)
                else: st.session_state.selected_tiers.append(2)
                st.rerun()
        with t_col3:
            if st.button("Specialized", type="primary" if 3 in st.session_state.selected_tiers else "secondary"):
                if 3 in st.session_state.selected_tiers: st.session_state.selected_tiers.remove(3)
                else: st.session_state.selected_tiers.append(3)
                st.rerun()

        if st.button("▶️ START VOCAB QUIZ", type="primary"):
            if not st.session_state.selected_tiers:
                st.error("Please select at least one tier!")
            else:
                df_filtered = df_master[df_master['Level'].astype(float).isin(st.session_state.selected_tiers)]
                st.session_state.df = df_filtered
                with st.spinner("Pre-loading Audio..."):
                    st.session_state.welcome_audio = get_audio_html("Welcome to the COGLI Vocab Quiz.")
                    st.session_state.current_bundle = generate_word_bundle(df_filtered, is_first=True)
                st.session_state.loop_running = True
                st.rerun()

    # --- THE ACTIVE LOOP ---
    if st.session_state.loop_running:
        header_spot = st.empty()
        content_spot = st.empty()
        status_spot = st.empty()
        audio_spot = st.empty()
        
        # 1. WELCOME
        if not st.session_state.welcome_played:
            audio_spot.markdown(st.session_state.welcome_audio, unsafe_allow_html=True)
            time.sleep(3.5) 
            st.session_state.welcome_played = True
            
        bundle = st.session_state.current_bundle
        
        # 2. DISPLAY CHALLENGE
        header_spot.markdown(f"<span class='word-label'>Word: </span><span class='blue-word'>{bundle['word']}</span>", unsafe_allow_html=True)
        options_html = f"""
        <div class='option-box'><div class='option-label'>A:</div><div class='option-text'>{bundle['opts'][0]}</div></div>
        <div class='option-box'><div class='option-label'>B:</div><div class='option-text'>{bundle['opts'][1]}</div></div>
        <div class='option-box'><div class='option-label'>C:</div><div class='option-text'>{bundle['opts'][2]}</div></div>
        """
        content_spot.markdown(options_html, unsafe_allow_html=True)
        
        # 3. PLAY CHALLENGE AUDIO
        audio_spot.empty()
        time.sleep(0.2) # Buffer for browser
        audio_spot.markdown(bundle['challenge_audio'], unsafe_allow_html=True)
        
        # 4. PRE-FETCH NEXT WORD WHILE SPEAKING
        start_time = time.time()
        st.session_state.next_bundle = generate_word_bundle(st.session_state.df, is_first=False)
        
        # 5. WAIT FOR CHALLENGE TO FINISH
        speech_wait = (len(bundle['challenge_text'].split()) / 2.1)
        time.sleep(max(0, speech_wait - (time.time() - start_time)) + 2.0)

        # 6. RESOLUTION
        status_spot.success(f"Answer: {bundle['correct_letter']}")
        audio_spot.empty()
        time.sleep(0.2)
        audio_spot.markdown(bundle['answer_audio'], unsafe_allow_html=True)
        
        # 7. WAIT FOR ANSWER TO FINISH
        res_wait = (len(bundle['answer_text'].split()) / 2.1)
        time.sleep(res_wait + 2.0)
        
        # 8. RECYCLE BUNDLE AND RERUN
        st.session_state.current_bundle = st.session_state.next_bundle
        st.rerun()
else:
    st.warning("Connecting to COGLI Data...")



# --- COGLI QUICK INGEST MODULE (ZERO-RISK EXPANDER) ---
# --- COGLI QUICK INGEST MODULE (ZERO-RISK EXPANDER) ---
st.divider()
with st.expander("📥 OPEN COGLI QUICK INGEST (Voice & Text)"):
    st.markdown("Lookup and stage new words directly to COGLI.")
    
    # Initialize specific session state for Ingest to avoid quiz conflicts
    if "ingest_word" not in st.session_state:
        st.session_state.ingest_word = None
    if "ingest_def" not in st.session_state:
        st.session_state.ingest_def = None
    if "last_audio_b64" not in st.session_state:
        st.session_state.last_audio_b64 = ""

    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Voice Lookup")
        
        import streamlit.components.v1 as components
        import base64
        import io
        
        # Hidden input to receive the audio data from JavaScript
        audio_b64 = st.text_input("audio_data_target", key="audio_b64", label_visibility="hidden")
            
        # The Custom HTML5/JS Auto-Stop Recorder
        components.html("""
        <div style="display: flex; justify-content: center; margin-top: -25px;">
            <button id="cogli-mic" style="width: 100%; padding: 15px; font-size: 16px; font-weight: bold; background-color: #FF4B4B; color: white; border: none; border-radius: 8px; cursor: pointer;">
                🎤 TAP ONCE & SPEAK (3s Auto-Stop)
            </button>
        </div>
        <script>
            const btn = document.getElementById('cogli-mic');
            btn.onclick = async () => {
                btn.innerText = "🔴 LISTENING... (Speak Now)";
                btn.style.backgroundColor = "#cc0000";
                
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    const mediaRecorder = new MediaRecorder(stream);
                    const audioChunks =[];
                    
                    mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
                    mediaRecorder.onstop = () => {
                        btn.innerText = "⏳ PROCESSING...";
                        btn.style.backgroundColor = "#555555";
                        
                        const blob = new Blob(audioChunks, { type: 'audio/webm' });
                        const reader = new FileReader();
                        reader.readAsDataURL(blob);
                        reader.onloadend = () => {
                            const base64String = reader.result;
                            
                            // Secretly inject the audio into Streamlit's hidden text input
                            const parentDoc = window.parent.document;
                            const inputs = parentDoc.querySelectorAll('input[aria-label="audio_data_target"]');
                            if (inputs.length > 0) {
                                const hiddenInput = inputs[0];
                                const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                                nativeSetter.call(hiddenInput, base64String);
                                hiddenInput.dispatchEvent(new Event('input', { bubbles: true }));
                            }
                            
                            // Reset button UI
                            setTimeout(() => {
                                btn.innerText = "🎤 TAP ONCE & SPEAK (3s Auto-Stop)";
                                btn.style.backgroundColor = "#FF4B4B";
                            }, 2000);
                        };
                    };
                    
                    mediaRecorder.start();
                    
                    // The Deterministic 3-Second Auto-Stop Timer
                    setTimeout(() => {
                        mediaRecorder.stop();
                        stream.getTracks().forEach(track => track.stop());
                    }, 3000); 
                    
                } catch (err) {
                    btn.innerText = "❌ Mic Access Denied";
                }
            };
        </script>
        """, height=70)

        # Python Handoff: Decode Base64 and send to Whisper
        if audio_b64 and audio_b64 != st.session_state.last_audio_b64:
            st.session_state.last_audio_b64 = audio_b64
            with st.spinner("Transcribing..."):
                try:
                    b64_data = audio_b64.split(",")[1]
                    audio_bytes = base64.b64decode(b64_data)
                    audio_file = io.BytesIO(audio_bytes)
                    audio_file.name = "audio.webm"
                    
                    client, drive_service = init_engines() 
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file
                    )
                    st.session_state.ingest_word = transcript.text.strip().strip('.').upper()
                    st.session_state.ingest_def = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Audio processing error: {e}")
    
    with col2:
        st.subheader("Text Lookup")
        text_input = st.text_input("Type the word", key="text_lookup_input")
        if st.button("Lookup Text"):
            if text_input:
                st.session_state.ingest_word = text_input.strip().upper()
                st.session_state.ingest_def = None

    # --- SYNTHESIS SECTION ---
    if st.session_state.ingest_word:
        st.markdown(f"### Target Word: **{st.session_state.ingest_word}**")
        
        if not st.session_state.ingest_def:
            with st.spinner("Synthesizing COGLI Definition..."):
                client, drive_service = init_engines()
                response = client.chat.completions.create(
                    model="gpt-4o",
                    temperature=0.0,
                    messages=[
                        {"role": "system", "content": "You are a high-precision lexicographer. Provide the definition of the word using best-of-breed sources (OED, Cambridge). Format strictly as: 'DEFINITION: [Text] NUANCE: [Cognitive Hook]'"},
                        {"role": "user", "content": f"Define: {st.session_state.ingest_word}"}
                    ]
                )
                st.session_state.ingest_def = response.choices[0].message.content

        st.info(st.session_state.ingest_def)

        # --- STAGING BUTTON ---
        if st.button("COMMIT THIS WORD TO THE VOCABULARY DATABASE", use_container_width=True):
            st.warning("Staging UI works! Google Drive write-back will be connected next.")
