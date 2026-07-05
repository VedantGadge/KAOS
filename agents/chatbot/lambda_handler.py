import os
import sys

# Ensure project root is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mangum import Mangum
from agents.chatbot.main import app

# Wrap FastAPI Chatbot application for API Gateway consumption
handler = Mangum(app, lifespan="on")
