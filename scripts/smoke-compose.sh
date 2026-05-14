#!/usr/bin/env bash
set -euo pipefail

COMPOSE=${COMPOSE:-"docker compose"}
API_BASE_URL=${API_BASE_URL:-"http://localhost:8000"}
LOCALSTACK_URL=${LOCALSTACK_URL:-"http://localhost:4566"}
AWS_REGION=${AWS_REGION:-"ap-south-1"}
S3_BUCKET_INPUT=${S3_BUCKET_INPUT:-"local-resume-input-bucket"}
S3_BUCKET_OUTPUT=${S3_BUCKET_OUTPUT:-"local-resume-output-bucket"}
SQS_PROCESSING_QUEUE_NAME=${SQS_PROCESSING_QUEUE_NAME:-"resume-processing-queue"}
START_STACK=${START_STACK:-"1"}
INCLUDE_WORKER=${INCLUDE_WORKER:-"0"}
INCLUDE_FRONTEND=${INCLUDE_FRONTEND:-"0"}

log() {
  printf '\n[%s] %s\n' "$(date -u +%H:%M:%S)" "$*"
}

wait_for_http() {
  local url="$1"
  local label="$2"
  local max_attempts="${3:-60}"
  local attempt=1
  until curl -fsS "$url" >/dev/null; do
    if (( attempt >= max_attempts )); then
      echo "Timed out waiting for ${label} at ${url}" >&2
      return 1
    fi
    sleep 2
    attempt=$((attempt + 1))
  done
}

curl_json() {
  local method="$1"
  local url="$2"
  shift 2
  curl -fsS -X "$method" "$url" "$@"
}

if [[ "$START_STACK" == "1" ]]; then
  services=(postgres localstack api)
  if [[ "$INCLUDE_WORKER" == "1" ]]; then
    services+=(worker)
  fi
  if [[ "$INCLUDE_FRONTEND" == "1" ]]; then
    services+=(frontend)
  fi
  log "Starting Docker Compose services: ${services[*]}"
  $COMPOSE up -d --build "${services[@]}"
fi

log "Waiting for API and LocalStack health endpoints"
wait_for_http "${LOCALSTACK_URL}/_localstack/health" "LocalStack"
wait_for_http "${API_BASE_URL}/api/health" "API"

log "Checking API discovery and health endpoints"
curl_json GET "${API_BASE_URL}/api" | python -m json.tool >/dev/null
curl_json GET "${API_BASE_URL}/api/health" | python -m json.tool >/dev/null
curl_json GET "${API_BASE_URL}/api/capabilities" | python -m json.tool >/dev/null
curl_json GET "${API_BASE_URL}/api/health/dependencies" | python -m json.tool >/dev/null
curl_json GET "${API_BASE_URL}/.well-known/agent-card.json" | python -m json.tool >/dev/null
curl_json GET "${API_BASE_URL}/.well-known/agent.json" | python -m json.tool >/dev/null
curl_json GET "${API_BASE_URL}/.well-known/mcp.json" | python -m json.tool >/dev/null
curl_json GET "${API_BASE_URL}/openapi.json" | python -m json.tool >/dev/null

log "Checking LocalStack S3 buckets and SQS queue"
$COMPOSE exec -T localstack awslocal s3api head-bucket --bucket "${S3_BUCKET_INPUT}" >/dev/null
$COMPOSE exec -T localstack awslocal s3api head-bucket --bucket "${S3_BUCKET_OUTPUT}" >/dev/null
QUEUE_URL="$($COMPOSE exec -T localstack awslocal sqs get-queue-url --queue-name "${SQS_PROCESSING_QUEUE_NAME}" --query QueueUrl --output text | tr -d '\r')"
$COMPOSE exec -T localstack awslocal sqs get-queue-attributes --queue-url "${QUEUE_URL}" --attribute-names All >/dev/null

log "Checking RDS-compatible Postgres through the Compose network"
$COMPOSE exec -T postgres pg_isready -U app_user -d app_db >/dev/null

log "Exercising runtime upload, queue confirm, and status APIs"
tmp_resume="$(mktemp)"
printf 'Jane Candidate\nSoftware Engineer\nPython, AWS, PostgreSQL\n' > "${tmp_resume}"
trap 'rm -f "${tmp_resume}"' EXIT

upload_response="$(curl -fsS -X POST "${API_BASE_URL}/api/runtime/resumes/upload" -F "file=@${tmp_resume};filename=smoke-resume.txt;type=text/plain")"
job_id="$(python -c 'import json,sys; print(json.load(sys.stdin)["job_id"])' <<<"${upload_response}")"
[[ -n "${job_id}" ]]

confirm_response="$(curl_json POST "${API_BASE_URL}/api/runtime/resumes/${job_id}/confirm")"
python -c 'import json,sys; data=json.load(sys.stdin); assert data["status"] == "QUEUED", data' <<<"${confirm_response}"
status_response="$(curl_json GET "${API_BASE_URL}/api/runtime/resumes/${job_id}/status")"
python -c 'import json,sys; data=json.load(sys.stdin); assert data["job_id"], data; assert data["status"] in {"QUEUED", "PROCESSING", "COMPLETED", "FAILED"}, data' <<<"${status_response}"

log "Checking that upload reached S3 and confirm reached SQS"
$COMPOSE exec -T localstack awslocal s3 ls "s3://${S3_BUCKET_OUTPUT}/jobs/${job_id}/input/" >/dev/null
$COMPOSE exec -T localstack awslocal sqs get-queue-attributes --queue-url "${QUEUE_URL}" --attribute-names ApproximateNumberOfMessages >/dev/null

log "Docker Compose smoke test passed. API, LocalStack S3/SQS, and Postgres are reachable. Job ${job_id} is queued."
