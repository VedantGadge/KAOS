from agents.triager.tools import find_service_owner

def test_escalataion():
    service_name = "PaymentService"
    print(f"🧪 Testing Escalation for {service_name}...")
    
    # This should find Charlie because Bob is On_Leave
    # Note: When using @tool, we must use .invoke() or call the function directly if not wrapped yet? 
    # Actually, @tool wraps it. So we need .invoke() with a dict.
    result = find_service_owner.invoke({"service_name": service_name})
    
    print("\n📝 Result:")
    print(result)
    
    if "Charlie" in result and "Assigned to Contributor" in result:
        print("\n✅ PASS: Correctly escalated to Active Contributor (Charlie)!")
    elif "Alice" in result:
        print("\n⚠️ PARTIAL: Escalated to Manager (Alice). Check if Charlie was found.")
    elif "Bob" in result:
        print("\n❌ FAIL: Assigned to Inactive Owner (Bob). Escalation failed.")
    else:
        print("\n❌ FAIL: Unexpected result.")

if __name__ == "__main__":
    test_escalataion()
