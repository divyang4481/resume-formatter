import sys
import os

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

try:
    from app.services.resume_generator_service import ResumeGeneratorService
    print("SUCCESS")
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
