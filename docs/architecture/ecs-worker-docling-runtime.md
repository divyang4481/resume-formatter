# ECS Worker Docling Runtime

## The Parsing Challenge
Docling and its underlying AI pipelines (RT-DETR, layout detection, OCR) are compute and memory intensive. Running this within AWS Lambda frequently leads to timeout restrictions (15m limits) and OOM errors, and limits access to GPU acceleration.

## Solution
We have migrated the parsing workload to an **ECS Fargate Worker**.
- The dedicated parser image includes all heavy PyTorch and system dependencies required for robust native processing; the worker calls it as a service.
- The queue-driven architecture (SQS) allows decoupling the frontend upload speed from the backend processing time.

## Parser Routing Guard
To optimize costs and speed:
1. Worker jobs route document parsing through the configured parser provider.
2. Heavy PDF/DOCX parsing is handled by the dedicated `parser-docling` service.
3. If Docling encounters errors, the job is failed or retried according to queue/job policy rather than silently switching parser engines.
