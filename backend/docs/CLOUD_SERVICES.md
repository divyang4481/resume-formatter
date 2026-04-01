# Cloud Services & Storage Comparison

The Resume Formatter platform acts on a **Cloud-Agnostic Core**, meaning that all core business logic, validation, PII constraints, and templates are fully portable. To interact with cloud infrastructure, we rely on pluggable orchestrators (Adapters) for Storage and Document Intelligence.

This document compares the supported cloud storage providers and document parsing services.

---

## 1. Supported Storage Providers (`StorageProvider`)

The platform abstracts object storage into a generic `StorageProvider` interface. Whenever a resume is uploaded, parsed, or finalized, the core application simply calls `storage.save()`, and the configured adapter routes it to the specific cloud target.

### **AWS (Amazon Web Services)**
- **Storage Service:** Amazon S3 (Simple Storage Service)
- **Adapter Implementation:** `S3StorageProvider`
- **Required Extra:** `poetry install --extras "cloud-aws-native"` (`boto3`)
- **Local Emulation:** Can be fully emulated using **LocalStack**.

### **Azure (Microsoft)**
- **Storage Service:** Azure Blob Storage
- **Adapter Implementation:** `AzureBlobStorageProvider`
- **Required Extra:** `poetry install --extras "cloud-azure-native"` (`azure-storage-blob`)
- **Local Emulation:** Can be fully emulated using **Azurite**.

### **GCP (Google Cloud Platform)**
- **Storage Service:** Google Cloud Storage (GCS)
- **Adapter Implementation:** `GCPStorageProvider`
- **Required Extra:** `poetry install --extras "cloud-gcp-native"` (`google-cloud-storage`)
- **Local Emulation:** Built-in SDK mocking or local GCP emulators.

---

## 2. Advanced Document Extraction Services

Alongside storage, the core feature of the app relies on extracting raw text, tables, and bounded layout data from resumes. We support native AI extraction features for each cloud:

| Cloud Platform | Default Storage | AI Document Extraction Service | Adapter Name |
|---|---|---|---|
| **AWS** | Amazon S3 | AWS Textract | `TextractParserAdapter` |
| **Azure** | Azure Blob Storage | Azure AI Document Intelligence | `AzureDocumentIntelligenceAdapter` |
| **GCP** | Google Cloud Storage | Google Cloud Document AI | `GCPDocumentAIAdapter` |

---

## 3. How Runtime Configuration Works

Rather than changing code, you swap cloud adapters primarily by modifying your environment variables. 

During startup, the application reads the `CLOUD` property and dynamically injects the appropriate `StorageProvider` and `DocumentParser`.

### Examples (`.env` file):

#### Targeted for Azure Blob & AI:
```env
CLOUD=azure
STORAGE_BACKEND=azure_blob
DOCUMENT_PARSER_BACKEND=azure_document_intelligence
```

#### Targeted for GCP Storage & Document AI:
```env
CLOUD=gcp
STORAGE_BACKEND=gcs
DOCUMENT_PARSER_BACKEND=document_ai
```

---

## 4. Golden Rule of Adapters

> **Isolation:** The core application logic (e.g., FastAPI routes and LangGraph workflows) MUST NOT import `boto3`, `azure-storage-blob`, or `google-cloud-storage`. 

All cloud interactions must implement base classes defined in `app/adapters/`. This strict separation ensures that if an Azure SDK update breaks, it never affects the AWS or GCP pipelines.

---

## 5. Mapping the Agentic Stack

When orchestrating agent workflows, the platform maps its core reasoning requirements to the equivalent managed services natively provided by each cloud ecosystem:

| Component | AWS Agentic Core | GCP (Vertex AI Agent Builder) | Azure AI Foundry |
| :--- | :--- | :--- | :--- |
| **Core LLM** | Bedrock (Claude, Llama, etc.) | Vertex AI (Gemini 3) | Azure OpenAI (GPT-4o/5) |
| **Hosting** | Lambda / Fargate / App Runner | Agent Engine (Serverless) | Agent Service (Managed) |
| **Memory** | DynamoDB / Bedrock Sessions | Context Management (Memory Bank) | Memory Store API |
| **Knowledge** | Bedrock Knowledge Bases | Vertex AI Search (RAG) | Foundry IQ / AI Search |
| **Tooling** | Action Groups / Lambda | ADK Connectors (100+) | Foundry Tools |
| **MCP Support** | Supported via SDK | Native MCP Support | Supported via SDK |
| **Guardrails** | Guardrails for Bedrock | Model Armor | Azure AI Content Safety |
