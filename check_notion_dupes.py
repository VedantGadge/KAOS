"""
Check for duplicate pages in Notion using Search (Deduplication Verification)
"""
from notion_client import Client
from config.settings import settings

notion = Client(auth=settings.NOTION_API_KEY)
database_id = settings.NOTION_DATABASE_ID.replace("-", "")

title_to_check = "NullPointerException in PaymentService"

try:
    print(f"Checking for pages with title: '{title_to_check}' via Search...")
    # Using search because databases.query is missing
    results = notion.search(query=title_to_check, filter={"value": "page", "property": "object"})
    
    pages = results.get("results", [])
    
    # Filter for pages in the correct database
    match_count = 0
    for page in pages:
        db_id = page.get("parent", {}).get("database_id", "").replace("-", "")
        if db_id == database_id:
            match_count += 1
            print(f"Match found: {page.get('url')}")

    print(f"\nFound {match_count} page(s) in the target database.")
    if match_count > 1:
        print("❌ DEDUPLICATION FAILED: Found more than 1 page.")
    elif match_count == 1:
        print("✅ DEDUPLICATION SUCCESS: Found exactly 1 page.")
    else:
        print("⚠️ No pages found yet. Agent might still be processing.")

except Exception as e:
    print(f"Error: {e}")
