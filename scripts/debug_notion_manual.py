import sys
import os

# Add project root BEFORE importing local modules
sys.path.append(os.getcwd())

from notion_client import Client
from config.settings import settings

def check_manual_request():
    print("--- Checking Manual Request ---")
    try:
        notion = Client(auth=settings.NOTION_API_KEY)
        db_id = settings.NOTION_DATABASE_ID
        if len(db_id) == 32 and "-" not in db_id:
            db_id = f"{db_id[:8]}-{db_id[8:12]}-{db_id[12:16]}-{db_id[16:20]}-{db_id[20:]}"
        
        print(f"Querying DB (formatted): {db_id}")
        
        import traceback
        
        # 1. Try Retrieve as Database
        print("--- Attempting Retrieve Database ---")
        try:
            resp = notion.request(path=f"databases/{db_id}", method="GET")
            print("✅ ID is a valid Database.")
            print(f"Title: {resp.get('title', 'No Title')}")
        except Exception as e:
            print(f"❌ Not a Database or Error: {e}")
            
        # 2. Try Retrieve as Page
        print("\n--- Attempting Retrieve Page ---")
        try:
             resp = notion.request(path=f"pages/{db_id}", method="GET")
             print("✅ ID is a valid Page.")
        except Exception as e:
             print(f"❌ Not a Page or Error: {e}")

    except Exception:
        traceback.print_exc()

if __name__ == "__main__":
    check_manual_request()
