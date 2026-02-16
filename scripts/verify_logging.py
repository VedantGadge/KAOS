import logging
import io
import json
import sys
import os

# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.logger import setup_logger, JsonFormatter

def verify_json_logging():
    print("--- Verifying JSON Logging ---")
    
    # Capture stdout
    capture = io.StringIO()
    handler = logging.StreamHandler(capture)
    handler.setFormatter(JsonFormatter())
    
    test_logger = logging.getLogger("test_logger")
    test_logger.addHandler(handler)
    test_logger.setLevel(logging.INFO)
    
    # Log a test message
    test_message = "This is a test log message"
    test_logger.info(test_message)
    
    # Evaluate output
    log_output = capture.getvalue().strip()
    print(f"Captured Output: {log_output}")
    
    try:
        parsed = json.loads(log_output)
        print("✅ SUCCESS: Output is valid JSON.")
        
        required_fields = ["timestamp", "level", "message", "logger", "module", "funcName"]
        missing = [f for f in required_fields if f not in parsed]
        
        if not missing:
            print("✅ SUCCESS: All required fields are present.")
        else:
            print(f"❌ FAILURE: Missing fields: {missing}")
            
        if parsed["message"] == test_message:
            print("✅ SUCCESS: Message content matches.")
        else:
            print(f"❌ FAILURE: Message mistmatch.")
            
    except json.JSONDecodeError:
        print("❌ FAILURE: Output is NOT valid JSON.")
    except Exception as e:
        print(f"❌ FAILURE: {e}")

if __name__ == "__main__":
    verify_json_logging()
