# Architecture Design

## 1. Overview
The platform represents a **bounded agentic workflow system**. Instead of loose LLM loops, we employ an orchestrated pipeline via LangGraph. Agents and LLM reasoning are embedded inside the workflow to solve targeted sub-problems.

## 2. Logical Architecture
### Core Agnostic Workflow
Core business logic (parsing, canonical mapping, privacy transform, validation) sits securely at the center of the architecture, uncoupled from any single cloud environment.

### The Adapter Pattern
- **Extraction Adapters:** Cloud-native adapters run depending on the system config (`AzureDocumentIntelligenceParser`, `AwsTextractParser`, `GcpDocumentAiParser`).
- **Dependency Factory:** Business services depend exclusively on the abstract `DocumentParserAdapter`. The `dependencies.py` layer resolves the correct adapter to inject into the workflow based on the current configuration mode.

## 3. Supported Parsers & Selection Model
Document processing avoids hardcoding an extraction implementation. The configured backend at runtime will serve as the primary parser with fallbacks available (e.g. Apache Tika for lightweight extraction).

### Config Driven Selection
```yaml
cloud: "azure"
document_parser_backend: "azure_document_intelligence"
document_parser_fallback: "tika"
```

### Supported Cloud-native Backends
- Azure AI Document Intelligence
- Amazon Textract
- Google Document AI
- IBM Docling
- Apache Tika (Local/Fallback)
- Local Parsing Tools (PyPDF2, etc)

## 4. Agentic Interaction Layers
The platform exposes several unified channels to connect humans, legacy systems, and new cloud AI orchestrators (e.g. Bedrock Agents, Vertex Agents).

### Runtime & Admin REST API
Standard JSON REST APIs for application interfaces and document pipeline integration.

### A2A Interface
The platform exposes an A2A-discoverable agent card (`/.well-known/agent.json`), empowering external orchestrators to discover its skills (`format_document`, `generate_blind_profile`, etc) and dynamically construct service-to-service payloads.

### MCP (Model Context Protocol) Interface
The platform natively exposes MCP tools (`/mcp/manifest` & `/mcp/tools/{tool_name}`) suitable for desktop copilots, IDE tools, or internal AI hosts. This bridges the cloud-agnostic platform cleanly into existing LLM UI environments.

## 5. Deployment Model
The system uses containerized microservice deployments. The `Dockerfile` relies on a multi-stage Poetry build where cloud-specific dependencies (such as heavy SDKs) are conditionally installed during CI/CD using Poetry Extras (e.g., `poetry install --extras "aws"`). This ensures lean container sizes across AWS ECS, Azure Container Apps, and GCP Cloud Run.
