import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.dialects.postgresql import JSONB
import boto3
from config.settings import settings

# Defines the base class for SQLAlchemy models
Base = declarative_base()

class PREvent(Base):
    __tablename__ = 'pr_events'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    event_type = Column(String, nullable=False)
    pr_id = Column(String, nullable=True)
    repo = Column(String, nullable=True)
    actor = Column(String, nullable=True)
    # Store as Text for SQLite, but intended to be JSONB in Postgres ideally.
    # For portability in this hybrid local/AWS setup without complex conditional types,
    # we will store as JSON string in Text column for SQLite compatibility,
    # OR we can use a custom type. For simplicity in this step, we use Text and serialize manually,
    # which works on both. In a strict Postgres env, we'd use JSONB.
    details = Column(Text, nullable=True) 
    
    # Store embedding as JSON string "[-0.1, ...]" for compatibility with SQLite & Postgres (without pgvector)
    # in the initial phase.
    embedding = Column(Text, nullable=True)

class EventLogger:
    def __init__(self, connection_string: Optional[str] = None):
        # Default to local SQLite if no connection string provided
        if not connection_string:
            connection_string = os.getenv("DATABASE_URL", "sqlite:///kaos_events.db")
        
        self.engine = create_engine(connection_string)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        
        # Bedrock Client
        self.bedrock_client = None
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            try:
                self.bedrock_client = boto3.client(
                    'bedrock-runtime',
                    region_name=settings.AWS_REGION,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
                )
                print("✅ Bedrock client initialized for embeddings.")
            except Exception as e:
                print(f"⚠️ Bedrock init failed: {e}")

    def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding using AWS Bedrock (Titan)."""
        if not self.bedrock_client or not text:
            return None
            
        try:
            body = json.dumps({"inputText": text})
            response = self.bedrock_client.invoke_model(
                modelId="amazon.titan-embed-text-v1",
                body=body,
                contentType="application/json",
                accept="application/json"
            )
            response_body = json.loads(response.get("body").read())
            return response_body.get("embedding")
        except Exception as e:
            print(f"⚠️ Embedding generation failed: {e}")
            return None

    def log_event(self, 
                  event_type: str, 
                  actor: str, 
                  repo: str = "Unknown", 
                  pr_id: Optional[str] = None, 
                  details: Optional[Dict[str, Any]] = None,
                  embedding: Optional[List[float]] = None):
        """
        Log an event to the database.
        
        Args:
            embedding: List of floats (vector). If None, will attempt to generate from details.
        """
        session = self.Session()
        try:
            # Auto-generate embedding if not provided and details exist
            if embedding is None and details and self.bedrock_client:
                 # Construct text to embed
                 text_parts = []
                 if details.get("title"): text_parts.append(f"Title: {details['title']}")
                 if details.get("description"): text_parts.append(f"Description: {details['description']}")
                 if details.get("summary"): text_parts.append(f"Summary: {details['summary']}")
                 if details.get("body"): text_parts.append(f"Body: {details['body']}")
                 
                 full_text = "\n".join(text_parts)
                 if full_text.strip():
                     print(f"🧠 Generating embedding for event: {event_type}...")
                     embedding = self._generate_embedding(full_text)

            details_json = json.dumps(details) if details else "{}"
            embedding_json = json.dumps(embedding) if embedding else None
            
            new_event = PREvent(
                event_type=event_type,
                actor=actor,
                repo=repo,
                pr_id=str(pr_id) if pr_id else None,
                details=details_json,
                embedding=embedding_json,
                timestamp=datetime.utcnow()
            )
            session.add(new_event)
            session.commit()
            print(f"📝 Logged event: {event_type} for PR #{pr_id}")
        except Exception as e:
            print(f"❌ Failed to log event: {e}")
            session.rollback()
        finally:
            session.close()

    def get_logs_for_pr(self, pr_id: str) -> List[Dict[str, Any]]:
        """Retrieve all logs for a specific PR."""
        session = self.Session()
        try:
            events = session.query(PREvent).filter(PREvent.pr_id == str(pr_id)).order_by(PREvent.timestamp.asc()).all()
            
            logs = []
            for event in events:
                logs.append({
                    "timestamp": event.timestamp.isoformat(),
                    "event_type": event.event_type,
                    "actor": event.actor,
                    "details": json.loads(event.details) if event.details else {}
                })
            return logs
        finally:
            session.close()

# Singleton instance
event_logger = EventLogger()
