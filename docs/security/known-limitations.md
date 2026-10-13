# Known limitations

- AWS deployment costs require account-specific bootstrap, reviewed IAM policies and a manually approved GitHub workflow. Tests and pull requests create no live AWS resources.
- The Cognito pool has no self-service registration or federation. An administrator invites users and grants operator membership. Configure the real HTTPS callback origin before connecting an AWS dashboard.
- The API offers public health checks. External identity management, malware scanning, content quarantine, cross-region replication, and file recovery after retention are not implemented.
- The Moto simulator is in-memory and gives local requests a sample user. It has no authentication boundary and must remain bound to loopback.
- Charts describe either labelled synthetic records or currently loaded owner-scoped jobs. AWS service metrics exist only in a deployed account. The operator queue summary is a point-in-time estimate.
- Dashboard overview counts describe the loaded page, not lifetime totals. Event history is capped at the latest 100 records.
- A live table/S3 restore and production scale test have not been performed. Alarm thresholds are initial values, not measured service objectives.
- Checkov exclusions and compensating controls are listed separately. Static scans do not certify security.
