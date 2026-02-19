# KAOS System Demo Walkthrough

This guide outlines the steps to demonstrate the **KAOS** platform, covering the full lifecycle of a bug: from detection to resolution and deployment.

## 📋 Prerequisites

Before starting, ensure you have:
1.  **Python 3.10+** installed.
2.  **Kafka** accessible (local or Confluent Cloud).
3.  **Neo4j** accessible (local or AuraDB).
4.  `.env` file correctly configured with credentials.

### 1. Verify Infrastructure
Run these scripts to ensure your environment is ready:

```powershell
# Check Kafka Connection
python scripts/test_kafka_connection.py

# Check Database & Embeddings
python scripts/demo_bot_query.py
```

---

## 🚀 Setting Up the Scene (The Control Plane)

The **Control Plane** is your command center. It will manage all agent processes and visualizations.

1.  **Open a Terminal** (PowerShell) in the project root (`e:\VG Codes\KAOS`).
2.  **Start the Control Plane**:
    ```powershell
    ./scripts/start_demo.ps1
    ```
    *(Or manually: `python agents/control_plane/backend.py`)*
3.  **Open your Browser**: Go to [http://localhost:8080](http://localhost:8080).

### Dashboard Setup
On the Control Plane Dashboard:
1.  Look at the **Agents** panel.
2.  Click **Start** on **Ingestion**, **Triager**, **Review Manager**, and **Ops Manager**.
    *   *Wait for all status indicators to turn Green.*
3.  Click **Start** on **Chatbot** if you want to demonstrate QA.

---

## 🎬 The Demo Script

### Scene 1: The Incident (Bug Report)
**Narrative:** "Imagine a critical error occurs in our Payment Service. Sentry catches it."

1.  **Action**: In the **Event Simulation** panel, find **Sentry Error**.
2.  **Click**: `Trigger` button.
3.  **Observation**:
    *   **Console Output**: See the "Sentry Webhook Received" log.
    *   **Architecture**: The **Ingestion Agent** receives the payload -> Pushes to Kafka -> **Triager Agent** picks it up.
    *   *(Optional)*: Show Jira board - a new Ticket is created (Status: To Do).

### Scene 2: The Fix (Developer Action)
**Narrative:** "The Triager has assigned this to 'dev_user'. The developer fixes the code and opens a Pull Request."

1.  **Action**: In **GitHub PR Open** card:
    *   Select Author: `External (dev_user)`.
    *   Click `Trigger`.
2.  **Observation**:
    *   **Console Output**: "Received GitHub Webhook: pull_request".
    *   **Control Plane**: Picks up the "PR Opened" event automatically.
    *   **System**: Updates Jira status to "In Progress".
    *   **Slack**: Reviewer receives a notification with a link to the PR.

### Scene 3: The Code Review (Quality Gate)
**Narrative:** "Our AI or a human reviewer (Dave) reviews the changes. Let's approve it."

1.  **Action**: In **PR Review** card:
    *   Click `Approve`.
2.  **Observation**:
    *   **Console Output**: "PR Review Submitted: APPROVED".
    *   **Review Manager**: Logs the approval.
    *   **Slack**: User would receive a "PR Approved!" notification.

### Scene 4: Deployment & Closure (The Happy Path)
**Narrative:** "The PR is merged. Now the CI/CD pipeline deploys the change."

1.  **Action**: In **Deployment** card:
    *   Select Reviewer: `Dave`.
    *   Click `Success`.
2.  **Observation**:
    *   **Ops Manager**: Receives "Success" signal.
    *   **Action**: Closes the Jira ticket automatically.
    *   **Narrative**: "The system automatically verifies the fix and closes the loop."

### Scene 5: The "What If?" (Deployment Failure)
**Narrative:** "But what if the deployment failed? KAOS handles that too."

1.  **Action**: In **Deployment** card:
    *   Click `Fail`.
2.  **Observation**:
    *   **Ops Manager**: Detects failure.
    *   **Action**: Re-opens/Updates Jira ticket.
    *   **Action**: Pings the Developer ("dev_user") on Slack with the error logs.
    *   **Narrative**: "The feedback loop is immediate. The developer knows exactly what went wrong."

### Scene 6: System Intelligence (QA)
**Narrative:** "We can ask the system what happened."

1.  **Scroll down** to **Kaos Chat**.
2.  **Type**: "What happened with the PaymentService?" or "Who fixed the bug?".
3.  **Observation**: The Chatbot retrieves the event history (Bug -> PR -> Deploy) and summarizes it.

---

## 🧹 Teardown

1.  On the Dashboard, click **Stop** for all agents.
2.  Close the terminal window.

---

## 🔧 Troubleshooting

### "Issue does not exist" or "Archived block" Errors?
If you deleted tickets in Jira/Notion but didn't clear the local database, the system might try to update old items.

**Fix:** Run the reset script to clear the local state and start fresh.
```bash
python scripts/reset_state.py
```
*(This will clear the local `kaos_events.db` and ask to reset Kafka topics).*
