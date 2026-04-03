import logging
from typing import Optional, List, Dict, Any
from app.domain.interfaces import KnowledgeIndex, TemplateRepository
from app.schemas.enums import AssetStatus
from app.schemas.template import TemplateAsset

logger = logging.getLogger(__name__)

class HybridTemplateRanker:
    def __init__(self, knowledge_index: KnowledgeIndex, template_repository: TemplateRepository):
        self.knowledge_index = knowledge_index
        self.template_repository = template_repository

    def rank_templates(
        self,
        extracted_text: str,
        industry_id: Optional[str] = None,
        mode: str = "recruiter_runtime",
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        1. Pre-filter by ACTIVE templates (or draft for admin).
        2. Filter by industry if provided.
        3. Vector search via KnowledgeIndex.
        """
        # 1 & 2. Metadata Filter
        status_filter = AssetStatus.ACTIVE if mode == "recruiter_runtime" else None

        all_templates = self.template_repository.list_templates({})

        filtered_templates = []
        for t in all_templates:
            if status_filter and t.status != status_filter:
                continue

            # Simple industry exact match if provided
            if industry_id and t.industry and t.industry.lower() != industry_id.lower():
                continue

            filtered_templates.append(t)

        if not filtered_templates:
            return []

        allowed_ids = [t.id for t in filtered_templates]

        # 3. Vector Similarity Ranking
        search_results = self.knowledge_index.search(
            query=extracted_text,
            filters=None,  # Our knowledge index adapter might not support complex OR filters easily right now
            top_k=top_k * 5 # Get more and post-filter locally
        )

        # Aggregate scores by template_id
        template_scores = {tid: 0.0 for tid in allowed_ids}
        for res in search_results:
            tid = res.get("template_id")
            if tid in template_scores:
                # Accumulate or max score. Simple max score per template for now based on closest chunk.
                score = res.get("score", 0.0)
                if score > template_scores[tid]:
                    template_scores[tid] = score

        # Sort filtered templates by max chunk score
        ranked_tids = sorted(template_scores.keys(), key=lambda k: template_scores[k], reverse=True)

        results = []
        for tid in ranked_tids:
            results.append({
                "template_id": tid,
                "score": template_scores[tid]
            })

        return results[:top_k]
