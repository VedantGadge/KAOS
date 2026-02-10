# KAOS: Kafka Automated Ops System

KAOS is an Event-Driven, Closed-Loop CI/CD orchestration platform powered by autonomous AI Agents.

## Architecture

The system consists of 3 core agents:
1.  **Triager:** Ingests bug reports and routes them to the correct owner.
2.  **Review Manager:** Manages the PR lifecycle and development loop.
3.  **Ops Manager:** Handles deployment and post-release monitoring.

## Tech Stack
-   **Language:** Python 3.11+
-   **Event Bus:** Confluent Cloud (Kafka)
-   **Database:** Neo4j Aura (Graph DB)
-   **AI:** AWS Bedrock

## Setup

1.  **Install Dependencies:**
    ```bash
    poetry install
    ```

2.  **Configure Environment:**
    Copy `.config/.env.example` to `.env` and fill in your Cloud credentials.
    ```bash
    cp config/.env.example .env
    ```

3.  **Run Connectivity Test:**
    Verify your connection to Confluent and Neo4j.
    ```bash
    poetry run python tests/verify_connectivity.py
    ```

4.  **Run Agents:**
    ```bash
    poetry run python agents/triager/main.py
    ```
