import os

import boto3


def create_resources() -> None:
    os.environ.update(
        AWS_ACCESS_KEY_ID="local",
        AWS_SECRET_ACCESS_KEY="local",
        AWS_DEFAULT_REGION="us-east-1",
        AWS_REGION="us-east-1",
        TABLE_NAME="cloudforge-local",
        UPLOAD_BUCKET="cloudforge-local-uploads",
        RESULT_BUCKET="cloudforge-local-results",
    )
    dynamodb = boto3.client("dynamodb", region_name="us-east-1")
    dynamodb.create_table(
        TableName=os.environ["TABLE_NAME"],
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": k, "AttributeType": "S"}
            for k in ("pk", "sk", "gsi1pk", "gsi1sk", "gsi2pk", "gsi2sk")
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": name,
                "KeySchema": [
                    {"AttributeName": f"gsi{i}pk", "KeyType": "HASH"},
                    {"AttributeName": f"gsi{i}sk", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
            for i, name in enumerate(("by-owner", "by-status"), 1)
        ],
    )
    s3 = boto3.client("s3", region_name="us-east-1")
    for bucket in (os.environ["UPLOAD_BUCKET"], os.environ["RESULT_BUCKET"]):
        s3.create_bucket(Bucket=bucket)
        s3.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
    sqs = boto3.client("sqs", region_name="us-east-1")
    os.environ["QUEUE_URL"] = sqs.create_queue(QueueName="cloudforge-local")["QueueUrl"]
