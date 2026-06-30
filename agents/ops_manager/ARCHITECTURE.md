# Ops Manager (Agent 3) Architecture

The **Ops Manager** handles the post-deployment phase of the KAOS pipeline. It listens for deployment outcome events from AWS CodePipeline (via the `ops.deploy.status` Kafka topic) and deterministically routes them through a LangGraph state machine.

The only AI/LLM call in this agent is `analyze_deployment_failure`, which invokes **AWS Bedrock** to diagnose failure logs. Everything else is pure, deterministic Python.

## System Architecture

```mermaid
flowchart TD
    K1["Kafka Topic<br/>ops.deploy.status"]

    subgraph "Consumer Process"
        C["consumer.py"]
    end

    subgraph "LangGraph State Machine"
        Start([START])
        N1["extract_event"]
        N2{"route_status"}

        N3["handle_success"]
        N4["log_success"]

        N5["analyze_failure"]
        N6["notify_failure"]
        N7["close_loop"]

        End([END])

        Start --> N1
        N1 --> N2

        N2 -->|SUCCEEDED| N3
        N3 --> N4
        N4 --> End

        N2 -->|FAILED| N5
        N5 --> N6
        N6 --> N7
        N7 --> End
    end

    Bedrock[(AWS Bedrock)]
    Jira[(Jira)]
    Notion[(Notion)]
    Slack[(Slack)]
    Sqlite[(SQLite Event DB)]
    K2["Kafka Topic<br/>system.quality.reports"]

    K1 -->|Consumes Event| C
    C -->|Invokes Graph| Start

    N3 -.->|Status to Done| Jira
    N3 -.->|Status to Resolved| Notion
    N3 -.->|Broadcast Success| Slack
    N4 -.->|Log Report| Sqlite

    N5 -.->|Diagnose Logs| Bedrock
    N6 -.->|Update Status| Jira
    N6 -.->|Needs Attention| Notion
    N6 -.->|DM Author and Reviewer| Slack
    N7 -.->|Emit Quality Report| K2
    N7 -.->|Log Report| Sqlite
```

---

## Directory & File Breakdown

### `1. consumer.py`

**Role:** The Entry Point & Message Broker

- **Inheritance:** Inherits from `BaseAgentConsumer`, consistent with the Triager and Review Manager.
- **Initialization:** Compiles the LangGraph (`build_ops_graph()`) once on startup.
- **Execution:** Listens to the `ops.deploy.status` topic. On each message, it invokes the compiled graph with the raw Kafka payload.

### `2. graph.py`

**Role:** The Brain (Deterministic State Machine + Bedrock AI)

- **State Management:** Defines `OpsState` as a `TypedDict` holding execution details, author/reviewer info, and the AI diagnosis.
- **Nodes:**
  - `extract_event`: Parses the Kafka payload into typed fields.
  - `handle_success`: Updates Jira (Done), Notion (Resolved), broadcasts to Slack.
  - `log_success`: Persists the deployment report to the event database.
  - `analyze_failure`: Calls AWS Bedrock to diagnose the failure logs (the **only LLM call**).
  - `notify_failure`: Updates Jira/Notion, sends personalized Slack DMs to author and reviewer.
  - `close_loop`: Emits a quality report back to Agent 1 (Triager) via Kafka, closing the feedback loop.
- **Edges:** A conditional edge (`route_status`) branches on `SUCCEEDED` vs `FAILED`.

### `3. __init__.py`

**Role:** Package Definition — marks the directory as an importable module.

> [!NOTE]
> **Closed-Loop Architecture:** On failure, the Ops Manager emits a `CRITICAL` quality report back to the `system.quality.reports` Kafka topic. This re-triggers **Agent 1 (Triager)**, which creates a new ticket with a `suggested_assignee` (the original PR author), completing the feedback loop without any human intervention.
