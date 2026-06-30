from langchain_core.tools import tool
from config.settings import settings
from datetime import datetime
from shared.logger import event_logger, logger
from shared.utils.retries import retry_with_backoff
import httpx
from notion_client import Client as NotionClient

@tool
@retry_with_backoff(retries=3, backoff_in_seconds=2)
def add_to_notion_dashboard(title: str, assignee: str, service_name: str, severity: str, description: str) -> str:
    """
    Add a bug/issue entry to the Notion Dashboard.
    """
    logger.info(f"📋 Adding to Notion Dashboard: {title} -> Assigned to {assignee}")
    try:
        notion = NotionClient(auth=settings.NOTION_API_KEY)
        database_id = settings.NOTION_DATABASE_ID

        db_id = database_id.strip()
        if len(db_id) == 32 and "-" not in db_id:
            db_id = f"{db_id[:8]}-{db_id[8:12]}-{db_id[12:16]}-{db_id[16:20]}-{db_id[20:]}"

        query_filter = {
            "and": [
                {"property": "Tasks", "title": {"equals": title}},
                {"property": "Status", "status": {"equals": "Open"}}
            ]
        }
        
        try:
            url = f"https://api.notion.com/v1/databases/{db_id}/query"
            headers = {
                "Authorization": f"Bearer {settings.NOTION_API_KEY}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            }
            
            with httpx.Client() as client:
                resp = client.post(url, headers=headers, json={"filter": query_filter})
                resp.raise_for_status()
                response = resp.json()

            search_results = response.get("results", [])
            
            if search_results:
                page_url = search_results[0].get("url")
                logger.info(f"⏭️  Duplicate found in Notion: {page_url}. Proceeding to create NEW one for demo.")
                
        except Exception as e:
            logger.warning(f"⚠️ Deduplication check failed: {e}. Proceeding with creation.")

        new_page = notion.pages.create(
            parent={"database_id": database_id},
            properties={
                "Tasks": {"title": [{"text": {"content": title}}]},
                "Text": {"rich_text": [{"text": {"content": assignee}}]},
                "Text 1": {"rich_text": [{"text": {"content": service_name}}]},
                "Severity": {"select": {"name": severity}},
                "Status": {"status": {"name": "Open"}},
                "Date": {"date": {"start": datetime.utcnow().isoformat() + "Z"}}
            },
            children=[
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"text": {"content": description}}]}
                }
            ]
        )

        page_url = new_page.get("url", "No URL")
        logger.info(f"✅ Notion Page Created: {page_url}")
        event_logger.log_event(
            event_type="NOTION_TICKET_CREATED",
            actor="Agent",
            repo=service_name,
            details={
                "title": title, 
                "description": description, 
                "service": service_name, 
                "url": page_url, 
                "severity": severity
            }
        )
        
        page_id = new_page.get("id")
        event_logger.log_notion_ticket(service=service_name, page_id=page_id, title=title, status="Open")
        
        return f"Notion page created: {page_url}"

    except Exception as e:
        return f"Error adding to Notion: {str(e)}"

@tool
def update_notion_status(title: str, new_status: str) -> str:
    """
    Update the status of an existing bug entry in Notion.
    """
    logger.info(f"📋 Updating Notion status for '{title}' -> {new_status}")
    try:
        notion = NotionClient(auth=settings.NOTION_API_KEY)
        database_id = settings.NOTION_DATABASE_ID

        page_id = event_logger.get_active_notion_ticket(service=title)
        if page_id:
            logger.info(f"💾 Found persisted Notion Page ID: {page_id}")
            try:
                notion.pages.update(
                    page_id=page_id,
                    properties={"Status": {"status": {"name": new_status}}}
                )
                event_logger.update_notion_ticket_status(page_id, new_status)
                return f"Notion status updated to '{new_status}' (via ID: {page_id})."
            except Exception as e:
                logger.warning(f"⚠️ Failed to update via ID {page_id}: {e}. Falling back to search.")

        logger.info(f"🔍 Falling back to search for '{title}'...")
        search_results = notion.search(
            query=title,
            filter={"value": "page", "property": "object"}
        ).get("results", [])

        for page in search_results:
            if page.get("parent", {}).get("database_id", "").replace("-", "") == database_id.replace("-", ""):
                page_id = page["id"]
                notion.pages.update(
                    page_id=page_id,
                    properties={"Status": {"status": {"name": new_status}}}
                )
                
                page_url = page.get("url", "")
                logger.info(f"✅ Notion status updated to '{new_status}': {page_url}")
                return f"Notion status updated to '{new_status}': {page_url}"

        logger.warning(f"⚠️ No matching Notion page found for '{title}'")
        return f"No matching Notion page found for '{title}'"

    except Exception as e:
        return f"Error updating Notion: {str(e)}"
