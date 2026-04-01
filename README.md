# resume-formatter

Agent-driven document transformation system that extracts, normalises, and generates structured outputs from PDFs, DOCX, and images with built-in privacy, validation, and template intelligence.

## Features

| Feature | Description |
|---|---|
| **Multi-format extraction** | PDF (pypdf), DOCX (python-docx), images with OCR (Pillow + pytesseract) |
| **Smart normalisation** | Heuristic section detection → structured `Resume` model |
| **Privacy (PII masking)** | E-mail, phone, SSN, LinkedIn, GitHub, and more |
| **Validation** | Pydantic-powered + business-rule validation reports |
| **Template intelligence** | `modern` (HTML), `classic` (HTML), `minimal` (Markdown), `json` |
| **CLI** | `resume-formatter` command-line tool |
| **Python API** | `Pipeline` class for programmatic use |

## Architecture

```
resume_formatter/
├── agents/
│   ├── extraction_agent.py    # PDF / DOCX / image → raw text
│   ├── normalization_agent.py # raw text → Resume model
│   ├── privacy_agent.py       # PII detection & masking
│   ├── validation_agent.py    # business-rule validation
│   └── template_agent.py      # Jinja2 / JSON rendering
├── models/
│   └── __init__.py            # Pydantic Resume schema
├── templates/
│   ├── modern.html.j2
│   ├── classic.html.j2
│   └── minimal.md.j2
├── pipeline.py                # end-to-end orchestration
└── cli.py                     # CLI entry-point
```

## Installation

```bash
pip install -e .
```

> **OCR support** additionally requires [Tesseract](https://github.com/tesseract-ocr/tesseract) to be installed on the host system.

## Quick start

### CLI

```bash
resume-formatter resume.pdf
resume-formatter resume.docx --template classic --output out.html
resume-formatter scan.png --template json --no-privacy
resume-formatter resume.pdf --template minimal --show-validation --show-privacy
```

### Python API

```python
from resume_formatter import Pipeline
from resume_formatter.pipeline import PipelineConfig

# Default: modern HTML, privacy masking enabled, validation enabled
pipeline = Pipeline()
result = pipeline.run("resume.pdf")

print(result.rendered)          # formatted HTML
print(result.validation)        # ValidationReport
print(result.privacy.findings)  # list of (pii_type, original_value)

# Custom config
config = PipelineConfig(template="json", apply_privacy=False)
result = Pipeline(config).run("resume.docx")

# Start from already-extracted text
result = pipeline.run_text(raw_text, source_file="resume.txt")
```

## Running tests

```bash
pip install -e ".[dev]"
pytest
```
