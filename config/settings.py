from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    # Kafka
    BOOTSTRAP_SERVERS: str
    SASL_USERNAME: str
    SASL_PASSWORD: str
    SECURITY_PROTOCOL: str = "SASL_SSL"
    SASL_MECHANISM: str = "PLAIN"

    # Neo4j
    NEO4J_URI: str
    NEO4J_USERNAME: str
    NEO4J_PASSWORD: str

    # AWS
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_REGION: str = "us-east-1"

    # Notion Integration
    NOTION_API_KEY: str
    NOTION_DATABASE_ID: str
    
    # Slack Integration
    SLACK_BOT_TOKEN: str | None = None

    # Jira Integration
    JIRA_URL: str | None = None
    JIRA_EMAIL: str | None = None
    JIRA_API_TOKEN: str | None = None

    # Database
    DATABASE_URL: str = "sqlite:///kaos_events.db"

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def current_time_iso(self) -> str:
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"

settings = Settings()
