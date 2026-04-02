from enum import Enum


class AssetStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class ExecutionMode(str, Enum):
    RECRUITER_RUNTIME = "recruiter_runtime"
    ADMIN_TEMPLATE_TEST = "admin_template_test"


class JobStatus(str, Enum):
    CREATED = "created"
    UPLOADED = "uploaded"
    WAITING_FOR_CONFIRMATION = "waiting_for_confirmation"
    CONFIRMED = "confirmed"
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL_SUCCESS = "partial_success"


class StageStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class PIIActionType(str, Enum):
    RETAIN = "retain"
    MASK = "mask"
    REDACT = "redact"
    TOKENIZE = "tokenize"


class ValidationCheckStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    ERROR = "error"
