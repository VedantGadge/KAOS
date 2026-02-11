"""
Check all Notion client methods
"""
from notion_client import Client
from config.settings import settings

notion = Client(auth=settings.NOTION_API_KEY)
print(f"Client endpoints: {dir(notion)}")
print(f"Databases endpoints: {dir(notion.databases)}")
print(f"Search endpoint: {dir(notion.search)}")
