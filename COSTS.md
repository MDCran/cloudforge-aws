# Costs

The simulator and Terraform validation create no AWS resources. A manual AWS deployment creates billable resources. Costs vary with region, volume, storage duration, alarms, and current free-tier eligibility. Check current service prices for your account before applying; AWS is not universally free.

Dev avoids always-running compute, provisioned database capacity, NAT gateways, containers, and a hosted CDN. It uses a request-driven HTTP API, Lambda, on-demand DynamoDB, S3, SQS, Cognito, bounded CloudWatch logs and alarms, and a modest dashboard. Main charges depend on API requests, Lambda duration, DynamoDB reads/writes, S3 requests and stored versions, log ingestion, alarms/dashboard and active users. Terraform history and failed messages also consume storage.

| Environment | Data and logs | Limits | Purpose |
|---|---|---|---|
| Local | In-memory; resets on restart | 10 MiB, 100,000 rows | Development without AWS billing. |
| dev | Seven-day current file/log retention; seven-day old S3 versions; PITR off by default | Five API/worker executions; 512 MiB worker | Lowest-cost demo. DynamoDB deletion protection defaults off. |
| staging | 30-day files; seven-day old versions; 14-day logs; DynamoDB PITR | Ten workers; 1 GiB worker | Isolated and data protected. |
| prod | 90-day files; seven-day old versions; 30-day logs; DynamoDB PITR | Twenty workers; 1 GiB worker | Reference configuration, requiring separate account access, backup tests and rollout policy. |

Concurrency, throttles, upload limits, processing timeouts and retention bound some usage; they do not cap total monthly spend. An optional AWS Budget email threshold alerts at 80 percent when an address is configured. Billing data is delayed, and budget notifications do not stop resources or charges. Review [AWS pricing](https://aws.amazon.com/pricing/), the [AWS Pricing Calculator](https://calculator.aws/), and [AWS Budgets](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html) for your region and expected traffic.
