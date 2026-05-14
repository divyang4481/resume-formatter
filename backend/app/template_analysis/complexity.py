from .models import TemplateEvidence


def compute_template_complexity(evidence: TemplateEvidence) -> float:
    placeholder_count = len(evidence.placeholder_candidates)
    section_count = len(evidence.section_candidates)
    table_count = len(evidence.tables)

    repeat_count = sum(
        1 for ph in evidence.placeholder_candidates
        if ph.candidate_kind in {"repeat_start", "repeat_end"}
    )

    generic_count = sum(
        1 for ph in evidence.placeholder_candidates
        if ph.candidate_kind == "generic_fill_instruction"
    )

    score = 0.0

    # Weights for complexity scoring
    score += min(placeholder_count / 30.0, 0.30)
    score += min(section_count / 15.0, 0.20)
    score += min(table_count / 8.0, 0.15)
    score += min(repeat_count / 6.0, 0.20)
    score += min(generic_count / 20.0, 0.15)

    return min(score, 1.0)
