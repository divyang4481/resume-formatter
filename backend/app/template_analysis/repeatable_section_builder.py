from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

from .field_types import normalize_field_type
from .models import TemplateEvidence, TemplateField, TemplateManifest

logger = logging.getLogger(__name__)

BULLET_HINTS = {"bullet", "responsibility", "achievement", "task", "duty", "grade", "activities", "list"}


def build_repeatable_sections_from_evidence(manifest: TemplateManifest, evidence: TemplateEvidence) -> TemplateManifest:
    sections = _build_sections(evidence)
    logger.info("[RepeatableSectionBuilder] detected headings: %s", [s["heading"] for s in sections])
    fields = list(manifest.fields)

    for section in sections:
        heading = section["heading"]
        markers = section["markers"]
        if not markers:
            logger.debug("[RepeatableSectionBuilder] skipped section '%s': no markers", heading)
            continue
        pattern = _detect_pattern(markers)
        if not pattern:
            logger.debug("[RepeatableSectionBuilder] skipped section '%s': no repeated pattern", heading)
            continue

        logger.info("[RepeatableSectionBuilder] section '%s' candidate repeated pattern: %s", heading, pattern)
        parent = _build_parent_field(heading, pattern)
        existing_idx = _find_existing_parent_index(fields, heading)
        if existing_idx is not None:
            existing = fields[existing_idx]
            existing.field_type = "array_complex"
            existing.render_locator = {**(existing.render_locator or {}), "strategy": "replace_complex_block", "heading": heading, "marker_text": pattern[0]}
            existing.injection_hints = {**(existing.injection_hints or {}), "strategy": "replace_complex_block", "heading": heading, "marker_text": pattern[0], "repeat_template_strategy": "clone_block_and_replace_subfields"}
            existing.sub_fields = _dedupe_subfields((existing.sub_fields or []) + parent.sub_fields)
            parent = existing
        else:
            fields.append(parent)
            logger.info("[RepeatableSectionBuilder] parent array_complex created: %s", parent.fieldname)

        section_markers = set(pattern)
        top_before = len(fields)
        fields = [
            f for f in fields
            if (
                f is parent
                or f.field_type == "table_loop"
                or f.source_kind == "recruiter_input"
                or not (f.marker_text in section_markers and _in_same_section(f, heading))
            )
        ]
        logger.info("[RepeatableSectionBuilder] moved child fields under '%s': removed=%s", parent.fieldname, top_before - len(fields))

    manifest.fields = [TemplateField.model_validate(f) for f in fields]
    manifest.field_count = len(manifest.fields)
    return manifest


def _build_sections(evidence: TemplateEvidence) -> List[Dict[str, Any]]:
    text = evidence.docling_markdown or evidence.raw_text_summary or ""
    headings = [s.heading for s in evidence.section_candidates]
    if not headings:
        return []
    lines = [l.rstrip() for l in text.splitlines()]
    idx = [(i, l.strip()) for i, l in enumerate(lines) if l.strip() in headings]
    sections = []
    for n, (start, heading) in enumerate(idx):
        end = idx[n + 1][0] if n + 1 < len(idx) else len(lines)
        block = lines[start + 1:end]
        markers = []
        for ln in block:
            for m in re.findall(r'("?\[[^\]]+\]"?|«[^»]+»)', ln):
                markers.append(m)
        logger.debug("[RepeatableSectionBuilder] markers collected under '%s': %s", heading, markers)
        sections.append({"heading": heading, "markers": markers})
    return sections


def _detect_pattern(markers: List[str]) -> Optional[List[str]]:
    if len(markers) < 4:
        return None
    for n in range(2, max(2, len(markers)//2 + 1)):
        seq = markers[:n]
        reps = 0
        i = 0
        while i + n <= len(markers) and markers[i:i+n] == seq:
            reps += 1
            i += n
        if reps >= 2:
            return seq
    counts = Counter(markers)
    repeated = [m for m in markers if counts[m] >= 2]
    if len(set(repeated)) >= 2:
        ordered=[]
        for m in repeated:
            if m not in ordered:
                ordered.append(m)
        return ordered
    return None


def _build_parent_field(heading: str, pattern: List[str]) -> TemplateField:
    parent_name = _slug(heading)
    subs = []
    for marker in pattern:
        lbl = _clean(marker)
        fname = _canonical(lbl)
        low = lbl.lower()
        ftype = "array_simple" if any(t in low for t in BULLET_HINTS) else ("rich_text" if any(t in low for t in ["summary", "description", "profile", "body"]) else "scalar")
        subs.append(TemplateField(
            fieldname=fname,
            canonical_fieldname=fname,
            original_label=lbl,
            marker_text=marker,
            field_type=normalize_field_type(ftype),
            meaning=f"Field '{lbl}' within section '{heading}'.",
            source_kind="resume_fact",
            resume_fillable=True,
            confidence=0.8,
        ))
    return TemplateField(
        fieldname=parent_name,
        canonical_fieldname=parent_name,
        original_label=heading,
        marker_text=pattern[0],
        field_type="array_complex",
        meaning=f"Repeatable structured entries under section '{heading}'.",
        source_hints=["Extract one object per repeated block under this section.", "Use sub_fields to map each internal placeholder."],
        resume_fillable=True,
        source_kind="resume_fact",
        confidence=0.8,
        render_locator={"strategy": "replace_complex_block", "heading": heading, "marker_text": pattern[0]},
        injection_hints={"strategy": "replace_complex_block", "heading": heading, "marker_text": pattern[0], "repeat_template_strategy": "clone_block_and_replace_subfields"},
        sub_fields=_dedupe_subfields(subs),
        context={"section_heading": heading},
    )


def _find_existing_parent_index(fields: List[TemplateField], heading: str) -> Optional[int]:
    key = _slug(heading)
    for i, f in enumerate(fields):
        if normalize_field_type(f.field_type) == "array_complex" and (f.fieldname == key or (f.render_locator or {}).get("heading") == heading):
            return i
    return None

def _in_same_section(field: TemplateField, heading: str) -> bool:
    ctx_heading = (field.context or {}).get("section_heading")
    return ctx_heading in (None, heading)

def _dedupe_subfields(subs: List[TemplateField]) -> List[TemplateField]:
    seen = set(); out=[]
    for sf in subs:
        k=(sf.marker_text, sf.fieldname)
        if k in seen: continue
        seen.add(k); out.append(sf)
    return out

def _clean(marker: str) -> str:
    return re.sub(r'^["\[]+|["\]]+$', '', marker).strip('«»').strip()

def _slug(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_') or 'section'

def _canonical(label: str) -> str:
    aliases = {
        "job description date": "job_description_date",
        "organisation": "organisation",
        "company": "company",
        "client": "client",
        "institution date": "institution_date",
        "grades": "grades",
    }
    norm = re.sub(r'[^a-z0-9]+', ' ', label.lower()).strip()
    if "responsibil" in norm: return "responsibilities"
    if "achieve" in norm: return "achievements"
    return aliases.get(norm, _slug(label))
