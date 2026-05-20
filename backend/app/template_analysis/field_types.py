from __future__ import annotations

VALID_FIELD_TYPES = {
    "scalar",
    "array_simple",
    "array_complex",
    "table_loop",
    "rich_text",
    "paste_zone",
}

VALID_RENDER_STRATEGIES = {
    "replace_marker",
    "fill_blank_cell_after_label",
    "replace_section_body",
    "replace_table_loop",
    "replace_complex_block",
}

FIELD_TYPE_NORMALIZATION = {
    "repeat_block": "array_complex",
    "repeatable_block": "array_complex",
    "complex_array": "array_complex",
    "object_array": "array_complex",
    "list_object": "array_complex",
    "list_of_objects": "array_complex",
    "repeating_section": "array_complex",
}

RENDER_STRATEGY_NORMALIZATION = {
    "repeat_block": "replace_complex_block",
    "replace_repeat_block": "replace_complex_block",
    "replace_repeating_section": "replace_complex_block",
}


def normalize_field_type(value: str) -> str:
    normalized = (value or "").strip().lower()
    normalized = FIELD_TYPE_NORMALIZATION.get(normalized, normalized)
    return normalized if normalized in VALID_FIELD_TYPES else "scalar"


def normalize_render_strategy(value: str) -> str:
    normalized = (value or "").strip().lower()
    normalized = RENDER_STRATEGY_NORMALIZATION.get(normalized, normalized)
    return normalized if normalized in VALID_RENDER_STRATEGIES else "replace_marker"


def is_valid_field_type(value: str) -> bool:
    return normalize_field_type(value) in VALID_FIELD_TYPES


def is_valid_render_strategy(value: str) -> bool:
    return normalize_render_strategy(value) in VALID_RENDER_STRATEGIES
