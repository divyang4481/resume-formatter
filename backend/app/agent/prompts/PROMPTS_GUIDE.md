# AI Prompt Architecture Guide

This directory follows a **Dual-Part Prompt Strategy** to ensure maximum instruction-following from LLMs (especially local models like Ollama).

## 📂 Directory Structure

Prompts are organized by **Pipeline Phase**:
- `classification/`: Document triage and kind identification.
- `extraction/`: Mapping raw text to structured JSON (Fidelity-focused).
- `linearization/`: Turning JSON into stylized CVML (Creative/Writing-focused).
- `analysis/`: Discovering template structural metadata.
- `summary/`: Generating professional career overviews.
- `validation/`: Auditing the generated result against raw facts.

## 🏷️ Naming Convention

Every feature MUST have two parts:

1.  `{feature_name}.jinja2` (**User Intent**):
    - Contains the dynamic data (e.g., `{{ extracted_text }}`).
    - Contains the task-specific instructions.
    - Specifies the required output format (JSON, CVML, etc.).

2.  `{feature_name}_system.jinja2` (**System Persona**):
    - Defines the AI's Identity ("You are a World-Class...").
    - Defines behavioral constraints (e.g., "100% Fidelity," "No summaries").
    - Sets the "Mode" of the model (e.g., "Data Exfiltrator").

## 💻 Programmatic Usage

Always use the `PromptManager` (Singleton) via:

```python
from app.agent.prompt_manager import prompt_manager

# This automatically finds both user and system parts across any subdirectory
system_prompt, user_prompt = prompt_manager.get_chat_prompt("context_aware_extraction", data=...)
```

## ⚠️ Critical Rules
- **NEVER** hardcode personas in Python. Use a `_system.jinja2` file.
- **NEVER** use generic names like `prompt.jinja2` in the root.
- **ALWAYS** include a `_system.jinja2` for new features to maintain high accuracy.
