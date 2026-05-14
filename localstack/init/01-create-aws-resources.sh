#!/usr/bin/env bash
set -euo pipefail

INPUT_BUCKET="${S3_BUCKET_INPUT:-local-resume-input-bucket}"
OUTPUT_BUCKET="${S3_BUCKET_OUTPUT:-local-resume-output-bucket}"
QUEUE_NAME="${SQS_PROCESSING_QUEUE_NAME:-resume-processing-queue}"

echo "Creating local S3 buckets..."
awslocal s3 mb "s3://${INPUT_BUCKET}" || true
awslocal s3 mb "s3://${OUTPUT_BUCKET}" || true

echo "Creating local SQS queue..."
awslocal sqs create-queue \
  --queue-name "${QUEUE_NAME}" \
  --attributes VisibilityTimeout=300,ReceiveMessageWaitTimeSeconds=10

echo "Listing buckets..."
awslocal s3 ls

echo "Listing queues..."
awslocal sqs list-queues

echo "Local AWS resources ready."
