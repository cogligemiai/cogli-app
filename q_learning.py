import requests

# --- CONFIGURATION ---
TOKEN = 'HoCG1HxBMWGasYlhraWvrWxg2iHTOGTN3AL2wv7hLmDUgywHDF'  # <--- PASTE YOUR TOKEN HERE
# ---------------------

def fetch_full_content_queue():
    url = "https://readwise.io/api/v3/list/"
    headers = {"Authorization": f"Token {TOKEN}"}
    # This parameter ensures we get the actual transcript/text for Gemini Live
    params = {"location": "new", "withHtmlContent": "true"} 
    
    print("\nConnecting to Readwise Reader for Q.learning Queue...")
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        docs = response.json().get('results', [])
        if not docs:
            print("Your Reader Inbox is empty!")
            return
            
        for doc in docs:
            print(f"\n{'='*60}")
            print(f"TITLE: {doc.get('title')}")
            print(f"{'='*60}")
            # Pulls the clean text version for Gemini to ingest
            content = doc.get('html_content', 'No full content found.')
            print(content) 
            print(f"\n--- END OF {doc.get('title')} ---\n")
    else:
        print(f"Error connecting to Readwise: {response.status_code}")

if __name__ == "__main__":
    fetch_full_content_queue()