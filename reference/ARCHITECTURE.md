# Project KAOS: System Architecture

## Core Philosophy
KAOS (**K**afka **A**utomated **O**ps **S**ystem) is an Event-Driven, Closed-Loop CI/CD orchestration platform. 
It uses autonomous AI Agents to manage the software lifecycle, specifically handling "Unhappy Paths" (Bugs, Conflicts, Rejections, Crashes) without human intervention.

## The 3-Agent Model
We strictly separate concerns into three phases to avoid state leakage.

### 1. Agent 1: "The Triager" (Input Handler)
* **Trigger:** `system.quality.reports` (Bugs from Sentry/User).
* **Responsibility:** Route the failure to the correct human.
* **Key Logic:**
    * Query Neo4j for Service Owner.
    * Check Jira for active sprints.
    * **Action:** Create Jira Ticket -> Slack the Team Channel.

### 2. Agent 2: "The Review Manager" (Development Loop)
* **Trigger:** `dev.pr.updates` (Pushes) & `dev.pr.decisions` (Approvals/Rejections).
* **Responsibility:** Shepherd the PR. Handle the "Loop of Despair" (Conflicts & Rejections).
* **Key Logic:**
    * **Merge Conflict:** Agent *polls* GitHub API (don't trust webhook) -> DMs Developer directly.
    * **Rejection:** Listens for `CHANGES_REQUESTED` -> DMs Developer directly.
    * **Clean PR:** Assigns Reviewer via Neo4j (Load Balancing) -> DMs Reviewer.
* **Constraint:** This Agent *never* touches Production.

### 3. Agent 3: "The Ops Manager" (Deployment)
* **Trigger:** `ops.deploy.status` (AWS CodePipeline Events).
* **Responsibility:** Manage the "Go Live" moment and post-deploy health.
* **Key Logic:**
    * **Merge Detected:** Trigger AWS CodePipeline.
    * **Deploy Success:** Close Jira Ticket + Announce in Slack.
    * **Deploy Failure:** Fetch CloudWatch Logs -> Analyze with Bedrock -> DM Developer with specific fix.

## Infrastructure Stack
* **Event Bus:** Apache Kafka (Confluent Cloud / MSK).
* **Brain:** Neo4j (Graph DB for Employee-Service mapping).
* **Compute:** AWS Lambda (Python 3.11).
* **Intelligence:** AWS Bedrock (Claude 3.5 Sonnet) for log analysis.