import json
import os
import logging
import sys
from datetime import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, func
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import text
from pgvector.sqlalchemy import Vector
import boto3
from config.settings import settings

# Configure Structured Logging
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "funcName": record.funcName,
            "lineNo": record.lineno
        }
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

logger = setup_logger("event_logger")

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
    details = Column(Text, nullable=True) 
    
    # Store embedding as pgvector Vector(384) since all-MiniLM-L6-v2 is 384d.
    embedding = Column(Vector(384), nullable=True)

class NotionTicket(Base):
    __tablename__ = 'notion_tickets'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    service = Column(String, nullable=False, index=True)
    page_id = Column(String, nullable=False)
    status = Column(String, default="Open")
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class JiraTicket(Base):
    __tablename__ = 'jira_tickets'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    service = Column(String, nullable=False, index=True)
    issue_key = Column(String, nullable=False)
    status = Column(String, default="To Do")
    summary = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class EventLogger:
    def __init__(self, connection_string: Optional[str] = None):
        # Default to settings if no connection string provided
        if not connection_string:
            from config.settings import settings as _settings
            connection_string = _settings.DATABASE_URL
        
        self.engine = create_engine(connection_string)
        
        # Ensure vector extension exists if using Postgres
        if "postgres" in connection_string:
            with self.engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()

        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        
        # Embedding Model (Lazy Loaded)
        self.embedding_model = None

    def _get_embedding_model(self):
        """Lazy load the local embedding model."""
        if not self.embedding_model:
            try:
                from sentence_transformers import SentenceTransformer
                # Use a small, efficient model suitable for Lambdas
                logger.info("🧠 Loading local embedding model (all-MiniLM-L6-v2)...")
                self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            except ImportError:
                logger.error("❌ sentence-transformers not installed. Run `pip install sentence-transformers`.")
            except Exception as e:
                logger.error(f"❌ Failed to load embedding model: {e}")
        return self.embedding_model

    def _generate_embedding_bedrock(self, text: str) -> Optional[List[float]]:
        """Generate embedding using AWS Bedrock."""
        if not text:
            return None
        try:
            # boto3 client creation
            bedrock = boto3.client(
                'bedrock-runtime',
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
            )
            model_id = settings.BEDROCK_EMBEDDING_MODEL_ID or "cohere.embed-english-v3"
            if "cohere" in model_id.lower():
                body = json.dumps({
                    "texts": [text],
                    "input_type": "search_document"
                })
                response = bedrock.invoke_model(
                    modelId=model_id,
                    body=body,
                    contentType="application/json",
                    accept="application/json"
                )
                response_body = json.loads(response.get("body").read())
                embeddings = response_body.get("embeddings", [])
                if embeddings:
                    # Match the 384 dimensions of database vector column
                    embedding = embeddings[0]
                    if len(embedding) > 384:
                        embedding = embedding[:384]
                    elif len(embedding) < 384:
                        embedding = embedding + [0.0] * (384 - len(embedding))
                    return embedding
            else:
                body = json.dumps({
                    "inputText": text
                })
                response = bedrock.invoke_model(
                    modelId=model_id,
                    body=body,
                    contentType="application/json",
                    accept="application/json"
                )
                response_body = json.loads(response.get("body").read())
                embedding = response_body.get("embedding", [])
                if len(embedding) > 384:
                    embedding = embedding[:384]
                elif len(embedding) < 384:
                    embedding = embedding + [0.0] * (384 - len(embedding))
                return embedding
        except Exception as e:
            logger.error(f"⚠️ Bedrock embedding generation failed: {e}")
            return None

    def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding using local Sentence Transformer or AWS Bedrock."""
        if settings.USE_BEDROCK_EMBEDDINGS:
            return self._generate_embedding_bedrock(text)
            
        model = self._get_embedding_model()
        if not model or not text:
            return None
            
        try:
            # Generate embedding
            embedding = model.encode(text).tolist()
            return embedding
        except Exception as e:
            logger.error(f"⚠️ Embedding generation failed: {e}")
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
            if embedding is None and details:
                 # Check/Load model
                 if settings.USE_BEDROCK_EMBEDDINGS or self._get_embedding_model():
                     # Construct text to embed
                     text_parts = []
                     if details.get("title"): text_parts.append(f"Title: {details['title']}")
                     if details.get("description"): text_parts.append(f"Description: {details['description']}")
                     if details.get("summary"): text_parts.append(f"Summary: {details['summary']}")
                     if details.get("body"): text_parts.append(f"Body: {details['body']}")
                     if details.get("error_message"): text_parts.append(f"Error: {details['error_message']}")
                     if details.get("comment"): text_parts.append(f"Comment: {details['comment']}")
                     
                     full_text = "\n".join(text_parts)
                     if full_text.strip():
                         logger.info(f"🧠 Generating embedding for event: {event_type}...")
                         embedding = self._generate_embedding(full_text)

            details_json = json.dumps(details) if details else "{}"
            
            new_event = PREvent(
                event_type=event_type,
                actor=actor,
                repo=repo,
                pr_id=str(pr_id) if pr_id else None,
                details=details_json,
                embedding=embedding,
                timestamp=datetime.utcnow()
            )
            session.add(new_event)
            session.commit()
            logger.info(f"📝 Logged event: {event_type} for PR #{pr_id}")
        except Exception as e:
            logger.error(f"❌ Failed to log event: {e}")
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

    def log_notion_ticket(self, service: str, page_id: str, title: str, status: str = "Open"):
        """Log a new Notion ticket linkage."""
        session = self.Session()
        try:
            ticket = NotionTicket(
                service=service,
                page_id=page_id,
                title=title,
                status=status
            )
            session.add(ticket)
            session.commit()
            logger.info(f"📝 Persisted Notion Ticket: {service} -> {page_id}")
        except Exception as e:
            logger.error(f"❌ Failed to persist Notion ticket: {e}")
            session.rollback()
        finally:
            session.close()

    def get_active_notion_ticket(self, service: str) -> Optional[str]:
        """Get the most recent Notion Page ID for a service."""
        session = self.Session()
        try:
            ticket = session.query(NotionTicket).filter_by(service=service).order_by(NotionTicket.created_at.desc()).first()
            if ticket:
                return ticket.page_id
            return None
        except Exception as e:
            logger.error(f"⚠️ Failed to lookup Notion ticket: {e}")
            return None
        finally:
            session.close()

    def update_notion_ticket_status(self, page_id: str, new_status: str):
        """Update status of a persisted Notion ticket."""
        session = self.Session()
        try:
            ticket = session.query(NotionTicket).filter_by(page_id=page_id).first()
            if ticket:
                ticket.status = new_status
                session.commit()
                logger.info(f"🔄 Updated local Notion record {page_id} to {new_status}")
            else:
                 logger.warning(f"⚠️ Local Notion record not found for {page_id}")
        except Exception as e:
            logger.error(f"❌ Failed to update local Notion record: {e}")
            session.rollback()
        finally:
            session.close()

    def log_jira_ticket(self, service: str, issue_key: str, summary: str, status: str = "To Do"):
        """Log a new Jira ticket linkage."""
        session = self.Session()
        try:
            ticket = JiraTicket(
                service=service,
                issue_key=issue_key,
                summary=summary,
                status=status
            )
            session.add(ticket)
            session.commit()
            logger.info(f"📝 Persisted Jira Ticket: {service} -> {issue_key}")
        except Exception as e:
            logger.error(f"❌ Failed to persist Jira ticket: {e}")
            session.rollback()
        finally:
            session.close()

    def get_active_jira_ticket(self, service: str) -> Optional[str]:
        """Get the most recent Jira Issue Key for a service."""
        session = self.Session()
        try:
            ticket = session.query(JiraTicket).filter_by(service=service).order_by(JiraTicket.created_at.desc()).first()
            if ticket:
                return ticket.issue_key
            return None
        except Exception as e:
            logger.error(f"⚠️ Failed to lookup Jira ticket: {e}")
            return None
        finally:
            session.close()

    def update_jira_ticket_status(self, issue_key: str, new_status: str):
        """Update status of a persisted Jira ticket."""
        session = self.Session()
        try:
            ticket = session.query(JiraTicket).filter_by(issue_key=issue_key).first()
            if ticket:
                ticket.status = new_status
                session.commit()
                logger.info(f"🔄 Updated local Jira record {issue_key} to {new_status}")
            else:
                 logger.warning(f"⚠️ Local Jira record not found for {issue_key}")
        except Exception as e:
            logger.error(f"❌ Failed to update local Jira record: {e}")
            session.rollback()
        finally:
            session.close()

    def get_bug_timeline(self, service_name: str) -> List[Dict[str, Any]]:
        """
        Retrieve the full lifecycle of events for a specific service or repo.
        Useful for answering "What happened with X?".
        """
        session = self.Session()
        try:
            # Query PR events for this service (repo)
            # Query PR events for this service (repo)
            # Normalize DB values: lower-case and strip hyphens/underscores for robust matching
            # e.g. "payment-service" -> "paymentservice" == "PaymentService" -> "paymentservice"
            
            clean_input = service_name.lower().replace("-", "").replace("_", "").replace(" ", "")
            
            events = session.query(PREvent).filter(
                func.replace(func.replace(func.lower(PREvent.repo), "-", ""), "_", "") == clean_input
            ).order_by(PREvent.timestamp.asc()).all()
            
            # Fallback: Try exact substring match if the above failed (e.g. for partial names)
            if not events:
                events = session.query(PREvent).filter(
                    PREvent.repo.ilike(f"%{service_name}%")
                ).order_by(PREvent.timestamp.asc()).all()
            
            timeline = []
            for event in events:
                timeline.append({
                    "timestamp": event.timestamp.isoformat(),
                    "event_type": event.event_type,
                    "actor": event.actor,
                    "details": json.loads(event.details) if event.details else {}
                })
            return timeline
        except Exception as e:
            logger.error(f"❌ Error fetching timeline for {service_name}: {e}")
            return []
        finally:
            session.close()

    def search_events(self, keyword: str) -> List[Dict[str, Any]]:
        """
        Search for events containing a specific keyword in their details.
        Useful for "Has there been any NPE?" type questions.
        """
        session = self.Session()
        try:
            search_term = f"%{keyword}%"
            events = session.query(PREvent).filter(
                PREvent.details.ilike(search_term)
            ).order_by(PREvent.timestamp.desc()).limit(20).all()
            
            results = []
            for event in events:
                 results.append({
                    "timestamp": event.timestamp.isoformat(),
                    "service": event.repo,
                    "event_type": event.event_type,
                    "details": json.loads(event.details) if event.details else {}
                })
            return results
        except Exception as e:
            logger.error(f"❌ Error searching events for {keyword}: {e}")
            return []
        finally:
            session.close()

    def semantic_search_events(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Perform a semantic (fuzzy) search using pgvector cosine distance.
        Finds events that are conceptually similar to the query, even if keywords don't match.
        """
        session = self.Session()
        try:
            logger.info(f"🧠 Generating query embedding for semantic search: '{query}'")
            query_vector = self._generate_embedding(query)
            if not query_vector:
                logger.warning("⚠️ Could not generate query embedding. Falling back to keyword search.")
                return self.search_events(query)

            # Use pgvector cosine_distance (<=> operator) to find nearest neighbors
            # Note: cosine_distance returns distance (0 = identical). We want smallest distance.
            events = session.query(PREvent).filter(
                PREvent.embedding.is_not(None)
            ).order_by(
                PREvent.embedding.cosine_distance(query_vector)
            ).limit(top_k).all()

            results = []
            for event in events:
                results.append({
                    "timestamp": event.timestamp.isoformat(),
                    "service": event.repo,
                    "event_type": event.event_type,
                    "details": json.loads(event.details) if event.details else {}
                })
            return results
        except Exception as e:
            logger.error(f"❌ Error in semantic search for '{query}': {e}")
            return []
        finally:
            session.close()

# Singleton instance
event_logger = EventLogger()
