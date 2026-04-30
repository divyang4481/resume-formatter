# AWS Agentic Core Architecture

## Overview
The Hays Resume Formatter has transitioned to a scalable, pipeline-first AWS architecture using an Agentic Core strategy.
We leverage AWS Bedrock Agents to handle the complex extraction mapping between unstructured resume text and structured template JSON schemas.

## Components
1. **Stateless API (Fargate)**: The FastAPI layer handles initial uploads, returns job tracking IDs, and manages template governance. It no longer synchronously executes slow document parsing.
2. **Asynchronous Worker (Fargate)**: An ECS task continuously polls an SQS Queue. Upon receiving a job, it parses the document (routing via Docling or Tika depending on config and document type), validates if it is a resume, and maps the output to a canonical format.
3. **Bedrock Agent**: Used inside the worker pipeline specifically for data transformation. We provide the extracted text, the JSON template contract, and formatting rules as prompt context, and the Agent returns strictly structured JSON.
4. **Bedrock Knowledge Base**: Manages unstructured template rules, policies, and semantic search for template suggestions.
5. **Storage**: S3 securely stores original files, intermediate parsed artifacts, quality audit JSONs, and final rendered DOCX files in job-scoped prefixes.
