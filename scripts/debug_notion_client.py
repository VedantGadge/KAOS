import sys
import os
from notion_client import Client

def check_notion_methods():
    print("--- Checking Notion Client Methods ---")
    try:
        notion = Client(auth="dummy")
        print(f"Has .databases? {hasattr(notion, 'databases')}")
        if hasattr(notion, 'databases'):
            print(f"Dir(notion.databases): {dir(notion.databases)}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_notion_methods()
