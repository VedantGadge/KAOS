"""
Test Notion API with correct property names
"""
from notion_client import Client
from config.settings import settings
from datetime import datetime

notion = Client(auth=settings.NOTION_API_KEY)
database_id = settings.NOTION_DATABASE_ID

print(f"Testing Notion API with corrected property names...")
print(f"Database ID: {database_id}\n")

try:
    new_page = notion.pages.create(
        parent={"database_id": database_id},
        properties={
            "Tasks": { 
                "title": [{"text": {"content": "Test Bug from Agent 1"}}]
            },
            "Text": {
                "rich_text": [{"text": {"content": "Charlie"}}]
            },
            "Text 1": {
                "rich_text": [{"text": {"content": "PaymentService"}}]
            },
            "Severity": {
                "select": {"name": "HIGH"}
            },
            "Status": {
                "status": {"name": "Open"}
            },
            "Date": {
                "date": {"start": datetime.now().isoformat()}
            }
        },
        children=[
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"text": {"content": "NullPointerException in ProcessTransaction - Test from debugging"}}]
                }
            }
        ]
    )
    
    print(f"✅ Success! Page created!")
    print(f"Page URL: {new_page.get('url')}")
except Exception as e:
    print(f"❌ Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
