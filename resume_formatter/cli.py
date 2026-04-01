"""CLI entry-point for the resume-formatter tool."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from resume_formatter.pipeline import Pipeline, PipelineConfig
from resume_formatter.agents.template_agent import TemplateAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="resume-formatter",
        description=(
            "Agent-driven document transformation: extract, normalise, and "
            "render resumes from PDF, DOCX, and image files."
        ),
    )
    parser.add_argument(
        "input",
        help="Path to a resume file (.pdf, .docx, .png, .jpg, .jpeg, .tiff, .bmp).",
    )
    parser.add_argument(
        "-t",
        "--template",
        default="modern",
        choices=TemplateAgent.supported_templates(),
        help="Output template (default: modern).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="-",
        help="Write rendered output to this file (default: stdout).",
    )
    parser.add_argument(
        "--no-privacy",
        action="store_true",
        help="Disable PII masking.",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip validation.",
    )
    parser.add_argument(
        "--show-validation",
        action="store_true",
        help="Print the validation report to stderr.",
    )
    parser.add_argument(
        "--show-privacy",
        action="store_true",
        help="Print the privacy report to stderr.",
    )
    parser.add_argument(
        "--raw-text",
        action="store_true",
        help="Print the extracted raw text to stderr before processing.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        parser.error(f"File not found: {input_path}")

    config = PipelineConfig(
        template=args.template,
        apply_privacy=not args.no_privacy,
        validate=not args.no_validate,
    )
    pipeline = Pipeline(config=config)

    try:
        result = pipeline.run(input_path)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ImportError as exc:
        print(f"Missing dependency: {exc}", file=sys.stderr)
        return 2

    if args.raw_text:
        print("=== Extracted Text ===", file=sys.stderr)
        print(result.raw_text, file=sys.stderr)
        print("======================", file=sys.stderr)

    if args.show_validation and result.validation:
        print("=== Validation Report ===", file=sys.stderr)
        print(str(result.validation), file=sys.stderr)
        print("=========================", file=sys.stderr)

    if args.show_privacy and result.privacy:
        print("=== Privacy Report ===", file=sys.stderr)
        if result.privacy.has_pii:
            for pii_type, value in result.privacy.findings:
                print(f"  [{pii_type}] {value}", file=sys.stderr)
        else:
            print("  No PII detected.", file=sys.stderr)
        print("======================", file=sys.stderr)

    if args.output == "-":
        print(result.rendered)
    else:
        Path(args.output).write_text(result.rendered, encoding="utf-8")
        print(f"Output written to {args.output}", file=sys.stderr)

    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
