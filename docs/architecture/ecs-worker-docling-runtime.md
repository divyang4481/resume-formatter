# ECS Worker Docling Runtime

## The Parsing Challenge
Docling and its underlying AI pipelines (RT-DETR, layout detection, OCR) are compute and memory intensive. Running this within AWS Lambda frequently leads to timeout restrictions (15m limits) and OOM errors, and limits access to GPU acceleration.

## Solution
We have migrated the parsing workload to an **ECS Fargate Worker**.
- The `Dockerfile.worker` includes all heavy PyTorch and system dependencies required for robust native processing.
- The queue-driven architecture (SQS) allows decoupling the frontend upload speed from the backend processing time.

## Parser Routing Guard
To optimize costs and speed:
1. Native DOCX files can be routed to a lightweight parser (`tika` or `unstructured`).
2. Scanned PDFs are routed to `docling`.
3. If Docling encounters errors, it gracefully falls back to a simpler extraction technique, ensuring pipeline stability.
