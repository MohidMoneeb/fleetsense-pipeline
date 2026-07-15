# Day 2 — Lesson: access patterns drive DynamoDB design

- Query requires the partition key. It's cheap and targeted.
- Scan reads the whole table; filters only cut what's returned, not what's read.
- "All records for one vehicle" -> Query on vehicle_id (PK). Easy.
- "One vehicle in a time range" -> Query on vehicle_id + timestamp range (SK). Easy.
- "ALL vehicles in a time range" -> NOT possible efficiently with this schema,
  because no single partition key value covers all vehicles. Options:
    - Scan + filter (reads entire table — bad at scale)
    - A GSI keyed by time (e.g. PK = date bucket, SK = timestamp)
- Takeaway: model the table around the queries you need. Each new access
  pattern may require a new index.

TODO (Day 5): replace AmazonDynamoDBFullAccess on the ingest role with a
scoped policy (PutItem/Query on VehicleTelemetry only).
