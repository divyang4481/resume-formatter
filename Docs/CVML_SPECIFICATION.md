# CVML (Candidate Visual Markup Language) Specification

## 1. Overview
**CVML** is a proprietary, agentic-focused markup language designed specifically for professional document generation. It serves as a collision-free communication bridge between the **AI Executive Architect** and the **Visual Docx Composer.**

### Why CVML?
- **Zero Data Collision**: Standard markdown characters (*, -, #) can often appear in raw candidate data (e.g., technical project names). CVML uses reserved `[:KEYWORDS:]` ensuring that formatting instructions are never confused with candidate content.
- **Narrative Stability**: By using a Tagged Block transport, we eliminate the syntax fragility of JSON for complex multi-line professional prose.

---

## 2. Transport Protocol
AI Harmonization outputs are wrapped in **Tagged Blocks**:
`[[PLACEHOLDER_NAME :: ...content containing CVML...]]`

---

## 3. Visual Syntax Reference

| Command | Visual Action | Description |
|---------|---------------|-------------|
| `[:B:]...[:/B:]` | **Bold Emphasis** | Used for high-impact professional identifiers (Job Titles, Companies). |
| `[:L1:]` | • Primary Bullet | Level 1 indentation for major career points. |
| `[:L2:]` | &nbsp;&nbsp;&nbsp;&nbsp;- Nested Detail | Level 2 indentation for granular project or technical details. |
| `[:PIPE:]` | &bull; | Clean visual separator for skill lists. |
| `[:BR:]` | `\n` | Explicit newline/paragraph break for clean white-space. |

---

## 4. Elite Composition Example

A professional experience narrative should be architected like this:

```text
[[Professional Experience :: 
[:B:]Solution Architect | Cognizant (2020 - Present)[:/B:][:BR:]
[:L1:]Architected a cross-functional data engine for high-traffic financial systems.[:BR:]
[:L2:]Reduced latency by 45% using a Kafka-based event stream.[:BR:]
[:L1:]Spearheaded a Zero-Trust security initiative for the core API gateway.
]]
```

---

## 5. System Implementation
- **Source Node**: `backend/app/agent/nodes/formatter_resume_node.py`
- **Sanitizer**: `backend/app/agent/utils/llm_sanitizer.py`
- **Visual Composer**: `backend/app/services/resume_generator_service.py`
