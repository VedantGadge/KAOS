import os
import sys

# Ensure project root is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mangum import Mangum
from agents.ingestion.main import app

# Wrap the FastAPI application using Mangum.
# We set lifespan="on" to ensure that the global Kafka producer compiles on startup.
handler = Mangum(app, lifespan="on")
