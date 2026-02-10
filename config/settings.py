from pydantic_settings import BaseSettings, SettingsConfigDict

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
