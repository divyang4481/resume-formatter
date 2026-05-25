"""Deterministic enrichment for generated template manifests.

The LLM is good at semantic interpretation, but rendering and extraction need
stable, exact structural facts.  This module reconciles generated fields with
DOCX evidence, adds any missing evidence-backed fields, and attaches detailed
metadata used by extraction and injection code paths.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional

from app.services.template_structure_extractor import FIELD_ALIAS_MAP

from .models import PlaceholderCandidate, TableCandidate, TemplateEvidence, TemplateField, TemplateManifest


RESUME_SOURCE_KIND = "resume_fact"
RECRUITER_SOURCE_KIND = "recruiter_input"
INSTRUCTION_SOURCE_KIND = "instruction"


def enrich_manifest_from_evidence(manifest: TemplateManifest, evidence: TemplateEvidence) -> TemplateManifest:
    """Return a complete, evidence-grounded manifest.

    The enrichment is deterministic and intentionally conservative: it never
    removes LLM-provided fields, but it heals marker spelling, fills missing
    metadata, and creates fallback fields for structural targets that the model
    omitted. This makes the manifest useful both for resume fact extraction and
    for exact DOCX injection.
    """
    marker_lookup = {_norm_marker(ph.marker): ph.marker for ph in evidence.placeholder_candidates}
    table_lookup = _table_lookup(evidence.tables)
    existing_markers = {_norm_marker(field.marker_text) for field in manifest.fields if field.marker_text}
    existing_fieldnames = set()

    enriched_fields: List[TemplateField] = []
    marker_occurrences: Dict[str, int] = defaultdict(int)

    for field in manifest.fields:
        field.fieldname = _unique_fieldname(field.fieldname, existing_fieldnames)
        existing_fieldnames.add(field.fieldname)
        healed_marker = marker_lookup.get(_norm_marker(field.marker_text))
        if healed_marker:
            field.marker_text = healed_marker

        marker_occurrences[field.marker_text] += 1
        _enrich_field(field, evidence, table_lookup, marker_occurrences[field.marker_text])
        _ensure_array_complex_sub_fields(field, evidence)
        enriched_fields.append(field)

    for ph in evidence.placeholder_candidates:
        if ph.candidate_kind == "repeat_end" or "TableEnd:" in ph.marker:
            continue
        marker_key = _norm_marker(ph.marker)
        if marker_key in existing_markers:
            continue

        field = _field_from_placeholder(ph, evidence, table_lookup, existing_fieldnames)
        existing_fieldnames.add(field.fieldname)
        marker_occurrences[field.marker_text] += 1
        _enrich_field(field, evidence, table_lookup, marker_occurrences[field.marker_text])
        _ensure_array_complex_sub_fields(field, evidence)
        enriched_fields.append(field)
        existing_markers.add(marker_key)

    for table in evidence.tables:
        if not table.is_blank:
            continue
        fieldname = _unique_fieldname(_canonical_from_text(table.label) or _slug(table.label), existing_fieldnames)
        existing_fieldnames.add(fieldname)
        field = TemplateField(
            fieldname=fieldname,
            canonical_fieldname=_canonical_from_text(table.label),
            original_label=table.label,
            marker_text=table.marker or table.label,
            field_type="scalar",
            meaning=f"Value for the template label '{table.label}'.",
            source_hints=[
                f"Fill from resume data matching the adjacent table label '{table.label}'.",
                "Injection target is the blank value cell immediately after this label.",
            ],
            confidence=0.78,
            render_locator={"strategy": "fill_blank_cell_after_label", "label": table.label, "marker_text": table.marker},
            extraction_hints={"labels": [table.label], "resume_sections": _section_hints(table.label)},
            injection_hints={"strategy": "fill_blank_cell_after_label", "label": table.label, "marker_text": table.marker},
            provenance={"source": "deterministic_table_slot", "evidence_type": "blank_label_slot"},
        )
        _enrich_field(field, evidence, table_lookup, 1)
        enriched_fields.append(field)

    for heading in evidence.paste_zones:
        if any(_norm_marker(f.marker_text) == _norm_marker(heading) for f in enriched_fields):
            continue
        fieldname = _unique_fieldname(_canonical_from_text(heading) or _slug(heading), existing_fieldnames)
        existing_fieldnames.add(fieldname)
        field = TemplateField(
            fieldname=fieldname,
            canonical_fieldname=_canonical_from_text(heading),
            original_label=heading,
            marker_text=heading,
            field_type="paste_zone",
            meaning=f"Rich resume content intended for the '{heading}' section.",
            source_hints=[
                f"Extract relevant resume paragraphs for section '{heading}'.",
                "Injection target is the body of the section under this heading.",
            ],
            confidence=0.72,
            render_locator={"strategy": "replace_section_body", "heading": heading},
            extraction_hints={"resume_sections": _section_hints(heading), "labels": [heading]},
            injection_hints={"strategy": "replace_section_body", "heading": heading},
            provenance={"source": "deterministic_paste_zone", "evidence_type": "paste_zone"},
        )
        enriched_fields.append(field)

    manifest.fields = enriched_fields
    manifest.field_count = len(enriched_fields)
    manifest.extraction_contract = _build_extraction_contract(enriched_fields)
    manifest.injection_contract = _build_injection_contract(enriched_fields)
    manifest.evidence_summary = _build_evidence_summary(evidence)
    return manifest


def _enrich_field(
    field: TemplateField,
    evidence: TemplateEvidence,
    table_lookup: Dict[str, TableCandidate],
    occurrence_index: int,
) -> None:
    marker = field.marker_text or ""
    marker_key = _norm_marker(marker)
    table = table_lookup.get(marker_key)
    candidate = next((ph for ph in evidence.placeholder_candidates if _norm_marker(ph.marker) == marker_key), None)
    loop_name = _loop_name(marker)
    original_label = field.original_label or (table.label if table else _label_from_marker(marker))
    canonical = field.canonical_fieldname or _canonical_from_text(original_label) or _canonical_from_text(field.fieldname)

    if canonical:
        field.canonical_fieldname = canonical
    field.original_label = original_label
    field.source_kind = _source_kind(field.fieldname, marker, field.meaning)
    field.resume_fillable = field.source_kind == RESUME_SOURCE_KIND
    field.required = bool(field.required or _looks_required(original_label))
    field.occurrence_index = occurrence_index
    field.context = _field_context(marker, evidence, table, candidate)
    field.provenance = {
        **(field.provenance or {}),
        "source": (field.provenance or {}).get("source", "llm_manifest"),
        "evidence_type": candidate.candidate_kind if candidate else ("table_slot" if table else "semantic_field"),
        "exact_marker_found": bool(candidate or table or marker in evidence.paste_zones),
    }

    if not field.extraction_hints:
        field.extraction_hints = {}
    field.extraction_hints.setdefault("canonical_fieldname", canonical or field.fieldname)
    field.extraction_hints.setdefault("labels", [x for x in [original_label, marker] if x])
    field.extraction_hints.setdefault("resume_sections", _section_hints(original_label or field.fieldname))
    field.extraction_hints.setdefault("source_kind", field.source_kind)

    if not field.injection_hints:
        field.injection_hints = {}
    strategy = _render_strategy(field, table, marker, loop_name)
    field.injection_hints.setdefault("strategy", strategy)
    field.injection_hints.setdefault("marker_text", marker)
    if table:
        field.injection_hints.setdefault("label", table.label)
    if loop_name:
        field.injection_hints.setdefault("loop_name", loop_name)

    if not field.render_locator:
        field.render_locator = dict(field.injection_hints)
    field.render_locator.setdefault("strategy", strategy)
    field.render_locator.setdefault("marker_text", marker)

    if field.field_type == "scalar" and loop_name:
        field.field_type = "table_loop"
    elif marker.startswith("[") and marker.endswith("]") and field.field_type == "scalar":
        field.field_type = _type_from_alias(canonical) or field.field_type

    if not field.source_hints:
        field.source_hints = [
            f"Use resume evidence matching '{original_label or field.fieldname}'.",
            f"Inject into exact template marker '{marker}'." if marker else "Inject using the provided render locator.",
        ]
    elif isinstance(field.source_hints, str):
        field.source_hints = [field.source_hints]




def _ensure_array_complex_sub_fields(field: TemplateField, evidence: TemplateEvidence) -> None:
    """Deterministically backfill sub_fields for array_complex when LLM omitted them."""
    if field.field_type != "array_complex" or field.sub_fields:
        return

    heading = (field.render_locator or {}).get("heading") or field.original_label
    marker_candidates: List[str] = []
    if heading and heading in evidence.object_patterns:
        marker_candidates.extend(evidence.object_patterns.get(heading, []))

    if not marker_candidates and evidence.raw_text_summary:
        marker_candidates = _extract_markers_near_heading(evidence.raw_text_summary, heading, field.marker_text)

    # fallback: repeated markers that are likely section children
    if not marker_candidates and evidence.repeated_markers:
        marker_candidates = [m for m in evidence.repeated_markers if m != field.marker_text]

    deduped = []
    seen = set()
    for marker in marker_candidates:
        key = _norm_marker(marker)
        if not marker or key in seen or key == _norm_marker(field.marker_text):
            continue
        seen.add(key)
        label = _label_from_marker(marker)
        canonical = _canonical_from_text(label)
        low = label.lower()
        subtype = "array_simple" if any(t in low for t in ("bullet", "responsibil", "achiev", "task", "duty", "grade", "list")) else "scalar"
        deduped.append(TemplateField(
            fieldname=canonical or _slug(label),
            canonical_fieldname=canonical,
            original_label=label,
            marker_text=marker,
            field_type=subtype,
            meaning=f"Field '{label}' within repeatable section '{heading or field.fieldname}'.",
            source_kind=RESUME_SOURCE_KIND,
            resume_fillable=True,
            confidence=0.72,
        ))

    if deduped:
        field.sub_fields = deduped


def _extract_markers_near_heading(text: str, heading: Optional[str], fallback_marker: str) -> List[str]:
    lines = text.splitlines()
    markers_re = re.compile(r'("?\[[^\]]+\]"?|«[^»]+»)')
    if heading:
        idx = next((i for i, line in enumerate(lines) if line.strip() == heading.strip()), None)
    else:
        idx = None
    if idx is None:
        idx = next((i for i, line in enumerate(lines) if fallback_marker and fallback_marker in line), None)
    if idx is None:
        return []

    out: List[str] = []
    for line in lines[idx + 1:]:
        if line.strip().isupper() and not markers_re.search(line):
            break
        for m in markers_re.findall(line):
            out.append(m)
    return out
def _field_from_placeholder(
    ph: PlaceholderCandidate,
    evidence: TemplateEvidence,
    table_lookup: Dict[str, TableCandidate],
    existing_fieldnames: set[str],
) -> TemplateField:
    marker = ph.marker
    table = table_lookup.get(_norm_marker(marker))
    label = table.label if table else _label_from_marker(marker)
    canonical = _canonical_from_text(label)
    fieldname = _unique_fieldname(canonical or _slug(label), existing_fieldnames)
    loop_name = _loop_name(marker)
    field_type = "table_loop" if loop_name else _type_from_alias(canonical) or _infer_field_type(label, ph, evidence)
    source_kind = _source_kind(fieldname, marker, label)

    sub_fields: List[TemplateField] = []
    if loop_name:
        for name in evidence.table_loop_fields.get(loop_name, []):
            sub_label = _label_from_marker(name)
            sub_canonical = _canonical_from_text(sub_label)
            sub_fields.append(TemplateField(
                fieldname=sub_canonical or _slug(sub_label),
                canonical_fieldname=sub_canonical,
                original_label=sub_label,
                marker_text=name if name.startswith(("«", "[")) else f"«{name}»",
                field_type=_type_from_alias(sub_canonical) or "scalar",
                meaning=f"Repeated value '{sub_label}' inside loop '{loop_name}'.",
                source_hints=[f"Extract from each repeated resume item for loop '{loop_name}'."],
                confidence=0.74,
            ))

    return TemplateField(
        fieldname=fieldname,
        canonical_fieldname=canonical,
        original_label=label,
        marker_text=marker,
        field_type=field_type,
        meaning=_meaning_for(label, source_kind, loop_name),
        source_hints=[
            f"Extract resume facts matching label or marker '{label}'.",
            f"Render by replacing exact marker '{marker}'.",
        ],
        resume_fillable=source_kind == RESUME_SOURCE_KIND,
        source_kind=source_kind,
        confidence=0.82 if ph.candidate_kind == "merge_marker" else 0.74,
        sub_fields=sub_fields,
    )


def _table_lookup(tables: Iterable[TableCandidate]) -> Dict[str, TableCandidate]:
    lookup: Dict[str, TableCandidate] = {}
    for table in tables:
        if table.marker:
            lookup[_norm_marker(table.marker)] = table
    return lookup


def _canonical_from_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    normalized = _norm_alias(text)
    for canonical, info in FIELD_ALIAS_MAP.items():
        if not isinstance(info, dict):
            continue
        aliases = [canonical, *info.get("aliases", [])]
        if normalized in {_norm_alias(alias) for alias in aliases}:
            return canonical
    return None


def _type_from_alias(canonical: Optional[str]) -> Optional[str]:
    if not canonical:
        return None
    info = FIELD_ALIAS_MAP.get(canonical)
    if isinstance(info, dict):
        return info.get("type")
    return None


def _infer_field_type(label: str, ph: PlaceholderCandidate, evidence: TemplateEvidence) -> str:
    low = label.lower()
    if ph.candidate_kind in {"repeat_start", "repeat_end"} or "tablestart:" in low:
        return "table_loop"
    if any(token in low for token in ("skills", "qualification", "certification")):
        return "array_simple"
    if any(token in low for token in ("experience", "employment", "education")):
        return "rich_text"
    if any(_norm_alias(label) == _norm_alias(slot) for slot in evidence.bullet_slots):
        return "array_simple"
    return "scalar"


def _render_strategy(field: TemplateField, table: Optional[TableCandidate], marker: str, loop_name: Optional[str]) -> str:
    if field.field_type == "paste_zone":
        return "replace_section_body"
    if loop_name or field.field_type == "table_loop":
        return "replace_table_loop"
    if table and table.is_blank:
        return "fill_blank_cell_after_label"
    return "replace_marker"


def _source_kind(fieldname: str, marker: str, meaning: str) -> str:
    text = f"{fieldname} {marker} {meaning}".lower()
    if "employee" in text or "consultant" in text or "recruiter" in text:
        return RECRUITER_SOURCE_KIND
    if "instruction" in text or "remove" in text:
        return INSTRUCTION_SOURCE_KIND
    return RESUME_SOURCE_KIND


def _field_context(marker: str, evidence: TemplateEvidence, table: Optional[TableCandidate], candidate: Optional[PlaceholderCandidate]) -> Dict[str, Any]:
    related_headings = []
    for heading, placeholders in evidence.object_patterns.items():
        if marker in placeholders:
            related_headings.append(heading)
    return {
        "location": candidate.location if candidate else "document_body",
        "candidate_kind": candidate.candidate_kind if candidate else None,
        "context_snippet": candidate.context_snippet if candidate else None,
        "table_label": table.label if table else None,
        "is_blank_table_slot": table.is_blank if table else False,
        "related_headings": related_headings,
        "appears_in_header_footer": marker in evidence.header_footer_markers,
    }


def _build_extraction_contract(fields: List[TemplateField]) -> Dict[str, Any]:
    field_hints = {}
    for f in fields:
        hint = {
            "meaning": f.meaning,
            "source_hints": f.source_hints,
            "extraction_hints": f.extraction_hints,
            "field_type": f.field_type,
        }
        if f.field_type == "array_complex":
            sub_meta = {}
            paths = []
            for sf in f.sub_fields:
                sub_meta[sf.fieldname] = {
                    "field_type": sf.field_type,
                    "marker_text": sf.marker_text,
                    "meaning": sf.meaning,
                }
                suffix = "[]" if sf.field_type == "array_simple" else ""
                paths.append(f"{f.fieldname}[].{sf.fieldname}{suffix}")
            hint["sub_fields"] = sub_meta
            hint["paths"] = paths
        field_hints[f.fieldname] = hint
    return {
        "resume_fields": [f.fieldname for f in fields if f.source_kind == RESUME_SOURCE_KIND],
        "recruiter_fields": [f.fieldname for f in fields if f.source_kind == RECRUITER_SOURCE_KIND],
        "required_fields": [f.fieldname for f in fields if f.required],
        "field_hints": field_hints,
    }


def _build_injection_contract(fields: List[TemplateField]) -> Dict[str, Any]:
    return {
        "targets": [
            {
                "fieldname": f.fieldname,
                "marker_text": f.marker_text,
                "field_type": f.field_type,
                "render_locator": f.render_locator or f.injection_hints,
                "repeat_template_strategy": (f.injection_hints or {}).get("repeat_template_strategy") if f.field_type == "array_complex" else None,
                "sub_fields": [sf.model_dump(mode="json") for sf in f.sub_fields],
            }
            for f in fields
        ]
    }


def _build_evidence_summary(evidence: TemplateEvidence) -> Dict[str, Any]:
    return {
        "layout_style": evidence.layout_style,
        "marker_count": len(evidence.placeholder_candidates),
        "table_slot_count": len(evidence.tables),
        "blank_table_slot_count": len([table for table in evidence.tables if table.is_blank]),
        "section_count": len(evidence.section_candidates),
        "instruction_count": len(evidence.instruction_blocks),
        "repeat_marker_count": len(evidence.repeated_markers),
        "paste_zones": evidence.paste_zones,
        "header_footer_markers": evidence.header_footer_markers,
    }


def _section_hints(label: str) -> List[str]:
    low = label.lower()
    hints = []
    if any(token in low for token in ("skill", "competenc")):
        hints.append("skills")
    if any(token in low for token in ("education", "qualification", "degree", "academic")):
        hints.append("education")
    if any(token in low for token in ("experience", "employment", "position", "responsibil")):
        hints.append("work_experience")
    if any(token in low for token in ("salary", "benefit")):
        hints.append("compensation")
    if not hints:
        hints.append("resume_body")
    return hints


def _loop_name(marker: str) -> Optional[str]:
    match = re.search(r"TableStart:([^»\]>]+)", marker)
    return match.group(1).strip() if match else None


def _label_from_marker(marker: str) -> str:
    text = marker.strip("«»[]<> ")
    text = re.sub(r"^Table(Start|End):", "", text)
    return re.sub(r"(?<!^)([A-Z])", r" \1", text).replace("_", " ").strip() or marker


def _meaning_for(label: str, source_kind: str, loop_name: Optional[str]) -> str:
    if loop_name:
        return f"Repeatable table/list block named '{loop_name}' populated from matching resume entries."
    if source_kind == RECRUITER_SOURCE_KIND:
        return f"Recruiter or consultant-provided value for '{label}', not extracted from the candidate resume."
    return f"Candidate resume value for '{label}'."


def _looks_required(label: str) -> bool:
    return any(token in label.lower() for token in ("name", "email", "phone", "job title", "experience"))


def _unique_fieldname(base: str, existing: set[str]) -> str:
    clean = _slug(base) or "field"
    candidate = clean
    suffix = 2
    while candidate in existing:
        candidate = f"{clean}_{suffix}"
        suffix += 1
    return candidate


def _slug(text: str) -> str:
    text = re.sub(r"(?<!^)([A-Z])", r"_\1", text or "")
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return text or "field"


def _norm_marker(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _norm_alias(text: str) -> str:
    return _norm_marker(_label_from_marker(text))
