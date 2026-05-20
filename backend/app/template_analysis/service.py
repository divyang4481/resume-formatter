import logging
import time
import json
import hashlib
from typing import Optional, Any

from .complexity import compute_template_complexity
from .docx_decomposer import decompose_docx
from .evidence_normalizer import normalize_evidence_with_model
from .llm_manifest_generator import generate_manifest_with_llm
from .manifest_repair import repair_manifest_with_model
from .manifest_validator import validate_manifest_against_evidence
from .manifest_enricher import enrich_manifest_from_evidence
from .manifest_critic import review_manifest_with_critic
from .model_roles import TemplateAnalysisModelRole
from .models import TemplateManifest

logger = logging.getLogger(__name__)

async def analyze_template_docx(
    file_path: Optional[str] = None, 
    content: Optional[bytes] = None,
    llm_runtime: Any = None, 
    model_router: Any = None,
    template_id: Optional[str] = None,
    docling_text: Optional[str] = None
) -> TemplateManifest:
    """
    Main entry point for the multi-stage, model-routed template analysis pipeline.
    """
    start_time = time.time()
    
    # 1. Decomposition
    evidence = decompose_docx(file_path=file_path, content=content, docling_text=docling_text)
    complexity_score = compute_template_complexity(evidence)
    logger.info(f"[TemplateAnalysis] Complexity score: {complexity_score:.2f}")

    model_usage = []
    llm_attempts = 0
    repair_attempts = 0

    # 2. Evidence Normalization (Stage 1)
    normalizer_config = model_router.get_model_config(
        TemplateAnalysisModelRole.evidence_normalizer,
        complexity_score=complexity_score,
    )

    norm_start = time.time()
    normalized_evidence = await normalize_evidence_with_model(
        evidence=evidence,
        llm_runtime=llm_runtime,
        model_config=normalizer_config,
    )
    model_usage.append({
        "role": TemplateAnalysisModelRole.evidence_normalizer.value,
        "provider": normalizer_config.provider,
        "model_id": normalizer_config.model_id,
        "latency_ms": int((time.time() - norm_start) * 1000)
    })
    llm_attempts += 1

    # 3. Manifest Generation (Stage 2)
    generator_config = model_router.get_model_config(
        TemplateAnalysisModelRole.manifest_generator,
        complexity_score=complexity_score,
    )

    gen_start = time.time()
    manifest = await generate_manifest_with_llm(
        evidence=evidence,
        normalized_evidence=normalized_evidence,
        llm_runtime=llm_runtime,
        model_config=generator_config,
    )
    manifest.template_id = template_id or "template-" + hashlib.sha256((file_path or "template.docx").encode()).hexdigest()[:8]
    manifest.complexity_score = complexity_score
    manifest = enrich_manifest_from_evidence(manifest, evidence)
    
    model_usage.append({
        "role": TemplateAnalysisModelRole.manifest_generator.value,
        "provider": generator_config.provider,
        "model_id": generator_config.model_id,
        "latency_ms": int((time.time() - gen_start) * 1000)
    })
    llm_attempts += 1

    # 4. Validation & Repair (Stage 3 & 4)
    errors, warnings = validate_manifest_against_evidence(manifest, evidence)

    if errors:
        logger.info(f"[TemplateAnalysis] Manifest has {len(errors)} errors. Triggering repair...")
        repair_config = model_router.get_model_config(
            TemplateAnalysisModelRole.manifest_repair,
            complexity_score=complexity_score,
        )

        rep_start = time.time()
        repaired_manifest = await repair_manifest_with_model(
            evidence=evidence,
            manifest=manifest,
            errors=errors,
            warnings=warnings,
            llm_runtime=llm_runtime,
            model_config=repair_config,
        )
        model_usage.append({
            "role": TemplateAnalysisModelRole.manifest_repair.value,
            "provider": repair_config.provider,
            "model_id": repair_config.model_id,
            "latency_ms": int((time.time() - rep_start) * 1000)
        })
        llm_attempts += 1
        repair_attempts += 1

        manifest = enrich_manifest_from_evidence(repaired_manifest, evidence)
        errors, warnings = validate_manifest_against_evidence(manifest, evidence)

    # 5. Optional Critic Review (Stage 5)
    critic_config = model_router.get_model_config(
        TemplateAnalysisModelRole.manifest_critic,
        complexity_score=complexity_score,
    )
    
    if critic_config.enabled:
        logger.info("[TemplateAnalysis] Triggering Critic review...")
        critic_start = time.time()
        critic_result = await review_manifest_with_critic(
            evidence=evidence,
            manifest=manifest,
            llm_runtime=llm_runtime,
            model_config=critic_config,
        )
        model_usage.append({
            "role": TemplateAnalysisModelRole.manifest_critic.value,
            "provider": critic_config.provider,
            "model_id": critic_config.model_id,
            "latency_ms": int((time.time() - critic_start) * 1000)
        })
        llm_attempts += 1
        
        if not critic_result.get("approved", True):
            manifest.requires_human_review = True
            manifest.review_reasons.extend([issue["issue"] for issue in critic_result.get("issues", [])])

    # Finalize manifest
    manifest.validation_errors = errors
    manifest.validation_warnings = warnings
    manifest.analysis_status = "completed" if not errors else "partial"
    manifest.model_usage = {"complexity_score": complexity_score, "models": model_usage}
    manifest.llm_attempt_count = llm_attempts
    manifest.repair_attempt_count = repair_attempts
    
    # Calculate average confidence
    manifest = enrich_manifest_from_evidence(manifest, evidence)
    confidences = [f.confidence for f in manifest.fields if f.confidence > 0]
    if confidences:
        manifest.average_confidence = sum(confidences) / len(confidences)
    
    # Heuristic for human review
    if errors or (manifest.average_confidence is not None and manifest.average_confidence < 0.75):
        manifest.requires_human_review = True
        if errors:
            manifest.review_reasons.append(f"Validation failed with {len(errors)} errors.")
        if manifest.average_confidence and manifest.average_confidence < 0.75:
            manifest.review_reasons.append(f"Average confidence ({manifest.average_confidence:.2f}) is below threshold.")

    # Cache docling markdown extract of template
    manifest.docling_markdown = evidence.docling_markdown

    logger.info(f"[TemplateAnalysis] Completed in {time.time() - start_time:.2f}s. Status: {manifest.analysis_status}")
    return manifest
