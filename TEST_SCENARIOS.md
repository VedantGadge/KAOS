# KAOS — Test Scenarios (Updated)

> Run all commands from the project root: `e:\VG Codes\KAOS`

---

## 1. Verify Infrastructure

### Kafka Connection
Check if your `.env` credentials are valid and you can reach Confluent Cloud.
```bash
python scripts/test_kafka_connection.py
```
**Expected Output:** `✅ Connection Successful!` with a list of topics.

### Database & Embeddings
Check if `EventLogger` can write to DB and Bedrock can generate embeddings.
```bash
python scripts/demo_bot_query.py
```
**Expected Output:** Logs of PR events and a simulated bot query response.

---

## 2. Agent 1: The Triager (Input Handler)
This agent listens for `system.quality.reports` (Bugs).

### Step 1: Start the Agent
Open a terminal and run:
```bash
python agents/triager/consumer.py
```
*It will sit and wait for events...*

### Step 2: Simulate a Bug Report
Open a **second terminal** and run:
```bash
python scripts/produce_test_event.py
```
This script sends a `null-pointer` bug event to Kafka.

### Expected Result (Terminal 1)
1.  **Receives Event**: `Test Bug 001`.
2.  **Finds Owner**: Consults Neo4j (Mock/Real).
3.  **Creates Jira**: Creates a ticket in your Jira project.
4.  **Logs Event**: Saves to `kaos_events.db` with Bedrock embedding.

---

## 3. Agent 2: Review Manager (Dev Loop)
This agent listens for `dev.pr.updates` (GitHub Webhooks).

### Step 1: Start the Agent
Open a terminal and run:
```bash
python agents/review_manager/consumer.py
```
*It will sit and wait for events...*

### Step 2: Simulate a PR Event
Open a **second terminal** and run:
```bash
python scripts/produce_test_event.py
```
This script *also* sends a `PR_OPENED` event to Kafka.

### Expected Result (Terminal 1)
1.  **Receives Event**: `PR #105 Opened`.
2.  **Finds Reviewer**: Consults Neo4j.
3.  **Logs Event**: `REVIEW_NEEDED` saved to DB with Bedrock embedding.

---

## 4. Agent 3: Ops Manager (Deployment)
This agent listens for `ops.deploy.status`.

### Step 1: Start the Agent
Open a terminal and run:
```bash
python agents/ops_manager/main.py
```

### Step 2: Simulate Success (Jira Closure)
Create a Jira ticket for `PaymentService`. Then run:
```bash
python scripts/produce_ops_event.py --success
```
**Expected Result:** Agent 3 finds the Jira ticket, closes it, and announces success in Slack.

### Step 3: Simulate Failure (Log Analysis)
```bash
python scripts/produce_ops_event.py --failure
```
**Expected Result:** Agent 3 calls Bedrock to analyze logs, announces the failure + fix in Slack, and logs a searchable `DEPLOYMENT_REPORT`.

---

## 5. The "Great Loop" (Autonomous Closed-Loop)
This verifies that a production failure re-triggers the whole cycle.

### Preparation:
Start **Agent 1 (Triager)** and **Agent 3 (Ops Manager)** in separate terminals.

### Step 1: Trigger a Prod Failure
```bash
python scripts/produce_ops_event.py --failure
```

### Step 2: Watch the Loop
1.  **Agent 3** receives the failure, analyzes it, and calls `emit_quality_report`.
2.  **Agent 1** automatically receives the new report.
3.  **Agent 1** sees "suggested_assignee: Dave" and re-assigns him directly.
4.  **Slack DM**: Dave receives: *"Your approved PR had a prod failure... please look into it."*

---

## Troubleshooting
- **ModuleNotFoundError**: Ensure you run from root (`e:\VG Codes\KAOS`).
- **Kafka Auth Error**: Check `SASL_USERNAME` / `SASL_PASSWORD` in `.env`.
- **Bedrock Error**: Check `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` in `.env`.
- **Jira Auth Error**: Ensure your API token is valid.
