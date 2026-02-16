import sys
import os
import requests
import json

# Add project root
sys.path.append(os.getcwd())

from config.settings import settings

def check_requests():
    print("--- Checking Notion API via requests ---")
    
    db_id = settings.NOTION_DATABASE_ID
    # Format UUID if needed
    if len(db_id) == 32 and "-" not in db_id:
        db_id = f"{db_id[:8]}-{db_id[8:12]}-{db_id[12:16]}-{db_id[16:20]}-{db_id[20:]}"
        
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    headers = {
        "Authorization": f"Bearer {settings.NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    print(f"POST {url}")
    
    try:
        resp = requests.post(url, headers=headers, json={"page_size": 1})
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text[:500]}") # Print first 500 chars
        
        if resp.status_code == 200:
            print("✅ Success! Database Query works.")
        else:
            print(f"❌ Failed: {resp.status_code}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_requests()
