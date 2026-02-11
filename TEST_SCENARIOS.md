# KAOS — Test Scenarios

> Run all commands from the project root: `e:\VG Codes\KAOS`

---

## Pre-requisites

```bash
# 1. Seed Neo4j (run once)
python -m scripts.seed_neo4j

# 2. Ensure Kafka topics exist (run once)
python -m scripts.setup_kafka
```

---

## Agent 1: The Triager

Start Agent 1 first, then send the test event in a **separate terminal**.

```bash
# Terminal 1: Start Agent 1
python -m agents.triager.main
```

### Scenario 1.1 — New Bug (PaymentService)

```bash
python -m scripts.produce_test_event --service PaymentService
```

**Expected flow:**
1. `find_service_owner` → Dave (Active, Senior)
2. `add_to_notion_dashboard` → Creates Notion entry (Status: Open)
3. `create_jira_ticket` → Creates Jira ticket (Priority: Highest)
4. `send_slack_message` → DMs `#dave` + announces in `#all-kaos`

### Scenario 1.2 — New Bug (AuthService)

```bash
python -m scripts.produce_test_event --service AuthService
```

**Expected flow:**
1. `find_service_owner` → Alice (Active, Senior)
2. `add_to_notion_dashboard` → Creates Notion entry
3. `create_jira_ticket` → Creates Jira ticket
4. `send_slack_message` → DMs `#alice` + announces in `#all-kaos`

### Scenario 1.3 — Duplicate Bug (same service twice)

```bash
# Send the same event again (don't delete the Notion entry from 1.1)
python -m scripts.produce_test_event --service PaymentService
```

**Expected flow:**
1. `find_service_owner` → Dave
2. `add_to_notion_dashboard` → **Detects duplicate**, returns existing URL
3. Agent **stops** — no Jira ticket, no Slack message

---

## Agent 2: The Review Manager

Start Agent 2 first, then send PR events in a **separate terminal**.

```bash
# Terminal 1: Start Agent 2
python -m agents.review_manager.main
```

> **Important:** Run Agent 1 first (Scenario 1.1) so there's a Notion entry + Jira ticket to update.

### Scenario 2.1 — Clean PR (PR opened, no conflicts)

```bash
python -m scripts.produce_pr_event --type push --repo PaymentService --author Dave --pr-id 101
```

**Expected flow:**
1. `check_pr_status` → CLEAN
2. `find_reviewer` → finds a Senior reviewer (e.g., Alice for PaymentService if author is Dave)
3. `send_slack_dm` → DMs **reviewer** (e.g., `#alice`) to review the PR
4. `send_slack_dm` → DMs **author** (`#dave`) that reviewer is assigned
5. `send_slack_dm` → Announces in `#all-kaos`
6. `update_notion_status` → Status → **"To be reviwed"**
7. `update_jira_status` → Adds comment to Jira ticket

### Scenario 2.2 — Merge Conflict

```bash
python -m scripts.produce_pr_event --type conflict --repo PaymentService --author Dave --pr-id 102
```

**Expected flow:**
1. `send_slack_dm` → DMs **author** (`#dave`) to resolve the conflict
2. `update_notion_status` → Status → **"Needs attention"**
3. `update_jira_status` → Adds comment: "Merge conflict detected"

### Scenario 2.3 — PR Rejected (Changes Requested)

```bash
python -m scripts.produce_pr_event --type rejection --repo PaymentService --actor Alice --comment "Fix the null check on line 45" --pr-id 103
```

**Expected flow:**
1. `send_slack_dm` → DMs **author** with reviewer's feedback
2. `send_slack_dm` → Announces in `#all-kaos`: "PR needs changes"
3. `update_notion_status` → Status → **"Needs attention"**
4. `update_jira_status` → Adds comment with reviewer's feedback

### Scenario 2.4 — PR Approved

```bash
python -m scripts.produce_pr_event --type approval --repo PaymentService --actor Alice --pr-id 104
```

**Expected flow:**
1. `send_slack_dm` → Announces in `#all-kaos`: "PR approved, ready for merge!"
2. `update_notion_status` → Status → **"To be deployed"**
3. `update_jira_status` → Adds comment: "PR approved"

---

## Full End-to-End Flow

Run these in order to simulate the complete bug lifecycle:

```bash
# Step 1: Bug discovered → Agent 1 triages
python -m agents.triager.main          # Terminal 1
python -m scripts.produce_test_event --service PaymentService  # Terminal 2
# Stop Agent 1 (Ctrl+C)

# Step 2: Developer raises PR → Agent 2 assigns reviewer
python -m agents.review_manager.main   # Terminal 1
python -m scripts.produce_pr_event --type push --repo PaymentService --author Dave --pr-id 201
# Notion: Open → To be reviwed | Jira: comment added

# Step 3: Reviewer requests changes
python -m scripts.produce_pr_event --type rejection --repo PaymentService --actor Alice --comment "Fix null check" --pr-id 201
# Notion: To be reviwed → Needs attention | Jira: comment added

# Step 4: Developer fixes and re-pushes
python -m scripts.produce_pr_event --type push --repo PaymentService --author Dave --pr-id 201
# Notion: Needs attention → To be reviwed | Jira: comment added

# Step 5: Reviewer approves
python -m scripts.produce_pr_event --type approval --repo PaymentService --actor Alice --pr-id 201
# Notion: To be reviwed → To be deployed | Jira: comment added

# Stop Agent 2 (Ctrl+C)
```

---

## Status Flow Summary

```
Open → To be reviwed → Needs attention → To be reviwed → To be deployed
  ↑        ↑                ↑                  ↑              ↑
Agent 1   Clean PR      Conflict/Reject     Re-push PR     Approved
```

---

## Slack Channels Required

| Channel     | Purpose                        |
|-------------|--------------------------------|
| `#alice`    | DMs for Alice                  |
| `#bob`      | DMs for Bob                    |
| `#charlie`  | DMs for Charlie                |
| `#dave`     | DMs for Dave                   |
| `#all-kaos` | Team-wide announcements        |

> Make sure the KAOS bot is invited to all channels: `/invite @KAOS`
