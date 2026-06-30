# Review Manager (Agent 2) Architecture

The **Review Manager** listens to Pull Request lifecycle events (usually fired via GitHub Webhooks into the `dev.pr.updates` and `dev.pr.decisions` Kafka topics) and routes them through a deterministic LangGraph.

## System Architecture

```mermaid
flowchart TD
    %% External Inputs
    K1["Kafka Topic<br/>dev.pr.updates / decisions"]

    %% Consumer
    subgraph "Consumer Process"
        C["consumer.py"]
    end

    %% State Machine (Graph)
    subgraph "LangGraph State Machine"
        Start([START])

        N1["extract_pr_details"]
        N2{"route_event"}
        
        %% Branches
        N3["assign_reviewer"]
        N4["notify_review_needed"]
        N5["update_tickets_review"]
        
        N6["process_decision"]
        N7{"route_decision"}
        N8["handle_rejection"]
        N9["handle_approval"]
        
        N10["handle_merge"]
        
        End([END])
        
        %% Internal Flow
        Start --> N1
        N1 --> N2
        
        %% Route 1: PR Opened
        N2 -->|Review Needed| N3
        N3 --> N4
        N4 --> N5
        N5 --> End
        
        %% Route 2: Decision Submitted
        N2 -->|Decision Submitted| N6
        N6 --> N7
        N7 -->|Changes Requested| N8
        N8 --> End
        N7 -->|Approved| N9
        N9 --> End
        
        %% Route 3: PR Merged
        N2 -->|PR Merged| N10
        N10 --> End
    end

    %% External Systems
    Neo4j[(Neo4j)]
    Jira[(Jira)]
    Notion[(Notion)]
    Slack[(Slack)]
    Sqlite[(SQLite Event DB)]

    %% Connections
    K1 -->|Consumes Event| C
    C -->|Invokes Graph| Start
    
    N3 -.->|Finds Reviewer| Neo4j
    N4 -.->|Sends DM to Reviewer| Slack
    
    N5 -.->|Updates Status| Notion
    N5 -.->|Updates Status| Jira
    
    N6 -.->|Looks up Author| Neo4j
    
    N8 -.->|Notifies Rejection| Slack
    N8 -.->|Notifies Rejection| Jira
    N8 -.->|Notifies Rejection| Notion
    
    N9 -.->|Notifies Approval| Slack
    N9 -.->|Notifies Approval| Jira
    
    N10 -.->|Updates Status to Deploying| Notion
    N10 -.->|Updates Status to Deploying| Jira
```

---

## Directory & File Breakdown

The `agents/review_manager/` folder is lean and modular. All integration logic (connecting to Jira, Slack, etc.) has been abstracted into the `shared/tools/` package, leaving the Review Manager folder solely responsible for business logic and routing.

### `1. consumer.py`
**Role:** The Entry Point & Message Broker
- **Inheritance:** Inherits from `BaseAgentConsumer` and listens to the GitHub webhook Kafka topics (`dev.pr.updates` and `dev.pr.decisions`).
- **Execution:** Extracts the payload and passes it directly to `graph.invoke()`.

### `2. graph.py`
**Role:** The Brain (Deterministic State Machine)
- **State Management:** Defines the `ReviewState` TypedDict to hold information as it flows through the graph (like the PR ID, Author, Reviewer Slack ID, Decision).
- **Conditional Routing:** Uses `Conditional Edges` (like `route_event` and `route_decision`) to accurately branch the logic based on the payload event type, ensuring strict control over the PR lifecycle.
