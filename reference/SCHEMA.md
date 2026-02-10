# Neo4j Graph Schema

## Nodes (Entities)
1.  **`Person`**
    * Properties: `name`, `slack_id`, `email`, `role` (Junior/Senior/Lead).
2.  **`Service`**
    * Properties: `name` (e.g., "PaymentService"), `repo_url`, `tier` (1=Critical).
3.  **`Team`**
    * Properties: `name` (e.g., "Checkout Pod"), `slack_channel`.

## Relationships (The Logic)
1.  `(:Person)-[:OWNS]->(:Service)`
    * Used by Agent 1 to find who to blame for a bug.
2.  `(:Person)-[:REPORTS_TO]->(:Person)`
    * Used by Agent 2 for escalation (if Reviewer is slow).
3.  `(:Service)-[:BELONGS_TO]->(:Team)`
    * Used by Agent 1 to post alerts to the right Slack channel.
4.  `(:Person)-[:REVIEWED]->(:PR)`
    * (Optional) History tracking.

## Sample Query (Agent 2 Logic)
"Find a Senior Engineer who owns this service but isn't the PR author."
```cypher
MATCH (p:Person)-[:OWNS]->(s:Service {name: $service_name})
WHERE p.role = 'Senior' AND p.name <> $pr_author
RETURN p.slack_id LIMIT 1
```