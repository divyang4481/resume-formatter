from enum import Enum


class TemplateAnalysisModelRole(str, Enum):
    evidence_normalizer = "evidence_normalizer"
    manifest_generator = "manifest_generator"
    manifest_repair = "manifest_repair"
    manifest_critic = "manifest_critic"
