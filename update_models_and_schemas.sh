sed -i 's/class TemplateAsset(Base):/class TemplateAsset(Base):\n    notes = Column(Text, nullable=True)\n    selection_weight = Column(Integer, default=50)\n    is_default_for_industry = Column(Boolean, default=False)\n/' backend/app/db/models.py

cat << 'INNER_EOF' >> backend/app/db/models.py

class TemplateTestRun(Base):
    __tablename__ = "template_test_runs"

    id = Column(String, primary_key=True, index=True)
    template_id = Column(String, ForeignKey("template_assets.id"), nullable=False)
    sample_resume_asset_id = Column(String, nullable=True)
    processing_job_id = Column(String, nullable=False)
    decision = Column(String, nullable=True) # PASS, FAIL, None
    review_notes = Column(Text, nullable=True)
    generated_summary = Column(Text, nullable=True)
    output_doc_path = Column(String, nullable=True)
    output_pdf_path = Column(String, nullable=True)
    extracted_json_path = Column(String, nullable=True)
    validation_result_json = Column(Text, nullable=True)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)
INNER_EOF
