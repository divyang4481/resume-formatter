import asyncio
import argparse
import sys
import json
from pathlib import Path

from app.adapters.llm.ollama_runtime import LocalOllamaLlmRuntime
from app.adapters.extraction.docling_parser import DoclingParserAdapter
from app.services.resume_ai_service import ResumeAiService

async def analyze_template(file_path: str, model: str, endpoint: str, output: str = None):
    path = Path(file_path)
    if not path.exists():
        print(f"Error: File not found at {file_path}")
        sys.exit(1)

    with open(path, "rb") as f:
        content = f.read()

    llm = LocalOllamaLlmRuntime(model_name=model, endpoint=endpoint)
    extractor = DoclingParserAdapter()

    service = ResumeAiService(llm=llm, extraction_service=extractor)

    print(f"Analyzing {path.name} using {model} at {endpoint}...")
    try:
        result = await service.analyze_template_metadata(content, path.name)
        result_json = result.model_dump_json(indent=2)

        if output:
            with open(output, "w") as f:
                f.write(result_json)
            print(f"Result saved to {output}")
        else:
            print("\n--- Analysis Result ---")
            print(result_json)

    except Exception as e:
        print(f"Analysis failed: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Analyze a CV template to produce field semantics metadata.")
    parser.add_argument("file", help="Path to the .docx template file")
    parser.add_argument("--output", "-o", help="Optional output JSON file path")
    parser.add_argument("--model", "-m", default="llama3", help="Ollama model name (default: llama3)")
    parser.add_argument("--endpoint", "-e", default="http://localhost:11434/api/generate", help="Ollama API endpoint")

    args = parser.parse_args()

    asyncio.run(analyze_template(args.file, args.model, args.endpoint, args.output))

if __name__ == "__main__":
    main()
