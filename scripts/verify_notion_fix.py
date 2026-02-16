import sys
import os
import time

# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.triager.tools import add_to_notion_dashboard

def verify_fix():
    print("--- Verifying Notion Deduplication & Date Fix ---")
    
    # Generate unique title to avoid clashing with existing real tickets
    unique_id = int(time.time())
    title = f"Test Bug {unique_id}"
    assignee = "Test User"
    service = "TestService"
    severity = "LOW"
    desc = "This is a test description."

    print(f"1. Creating first ticket: '{title}'")
    # LangChain tool usage: .invoke(input_dict) or try direct call if simple decorator
    # The @tool decorator makes it a StructuredTool, so we likely need .invoke or .run
    try:
        # direct call might work if retry decorator wraps the function before @tool?
        # In tools.py: @tool is outer, @retry is inner? No.
        # @tool
        # @retry
        # def func...
        # So func is wrapped by retry, then by tool.
        # accessing func directly might be tricky. Let's try .invoke
        
        args = {
            "title": title,
            "assignee": assignee,
            "service_name": service,
            "severity": severity,
            "description": desc
        }
        
        # First Call
        result1 = add_to_notion_dashboard.invoke(args)
        print(f"Result 1: {result1}")
        
        if "Created" in result1 or "created" in result1:
            print("[SUCCESS] First creation successful.")
        else:
            print(f"[FAILURE] First creation failed: {result1}")
            return

        print("\n2. Attempting duplicate creation...")
        # Second Call (Should be duplicate)
        result2 = add_to_notion_dashboard.invoke(args)
        print(f"Result 2: {result2}")
        
        if "Duplicate" in result2:
            print("[SUCCESS] Deduplication logic worked! Duplicate detected.")
        else:
            print("[FAILURE] Deduplication failed! It created another ticket or errored.")

    except Exception as e:
        print(f"[EXCEPTION] {e}")

if __name__ == "__main__":
    verify_fix()
