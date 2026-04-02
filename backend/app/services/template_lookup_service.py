from typing import List, Dict, Optional
from app.domain.interfaces import TemplateRepository

class TemplateLookupService:
    def __init__(self, template_repository: TemplateRepository):
        self.template_repository = template_repository

    def list_active_industries(self) -> List[Dict[str, str]]:
        """
        Returns available industries for form selection from published templates.
        """
        templates = self.template_repository.list_templates({"status": "ACTIVE"})

        unique_industries = set(t.industry for t in templates if t.industry)

        industries_list = [
            {"id": ind, "name": ind.replace("_", " ").title()}
            for ind in unique_industries
        ]

        # Sort alphabetically by name
        industries_list.sort(key=lambda x: x["name"])

        return industries_list

    def list_active_templates(self, industry: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Returns available templates from the database, optionally filtered by industry.
        """
        filters = {"status": "ACTIVE"}
        if industry:
            filters["industry"] = industry

        db_templates = self.template_repository.list_templates(filters)

        # If a specific industry is requested, we might also want to fetch "general" templates
        if industry and industry.lower() != "general":
            general_filters = {"status": "ACTIVE", "industry": "general"}
            general_templates = self.template_repository.list_templates(general_filters)

            # Add general templates if they aren't already in the list
            existing_ids = {t.id for t in db_templates}
            for gt in general_templates:
                if gt.id not in existing_ids:
                    db_templates.append(gt)

        templates = [
            {
                "id": t.id,
                "name": t.name,
                "industry": t.industry
            }
            for t in db_templates
        ]

        return templates
