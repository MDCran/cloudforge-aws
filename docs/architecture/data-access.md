# Data access and retention

- Job metadata is private to its Cognito subject. Resource IDs alone do not grant access.
- The browser never picks an S3 key. The API derives an opaque job path, signs an exact object size and type for five minutes, and signs result reads for five minutes.
- Uploaded data and reports use encrypted, versioned buckets with explicit environment lifecycle rules. The separate bootstrap state bucket remains protected and versioned.
- Job state can be deleted by a deliberate reviewed environment teardown. Event rows have a 90-day DynamoDB TTL; transaction idempotency records have a 24-hour TTL. S3 object expiry and DynamoDB TTL are asynchronous.
- Uploaded values and CSV error examples are not copied into logs. The JSON report records a bounded sample of row/column/error codes, with raw values omitted.

Confirm these defaults meet your contract and retention needs before processing third-party data.
