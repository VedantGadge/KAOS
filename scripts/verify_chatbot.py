
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.chatbot.tools import get_bug_timeline, search_events, find_team_info, get_jira_status
from shared.logger import event_logger

def verify_tools():
    print("🤖 Verifying Chatbot Tools...")
    
    # Check 1: Timeline
    print("\n1. Testing get_bug_timeline('PaymentService')...")
    timeline = get_bug_timeline.invoke("PaymentService")
    print(timeline)
    
    # Check 2: Search
    print("\n2. Testing search_events('NPE')...")
    results = search_events.invoke("NPE")
    print(results)
    
    # Check 3: Team Info
    print("\n3. Testing find_team_info('PaymentService')...")
    team = find_team_info.invoke("PaymentService")
    print(team)
    
    # Check 4: Jira Status
    # This might fail if no active ticket, but we want to see it run without crash
    print("\n4. Testing get_jira_status('PaymentService')...")
    try:
        jira = get_jira_status.invoke("PaymentService")
        print(jira)
    except Exception as e:
        print(f"Jira check failed as expected (no connection): {e}")

if __name__ == "__main__":
    verify_tools()
