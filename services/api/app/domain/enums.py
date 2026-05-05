from enum import StrEnum


class ProjectCategory(StrEnum):
    PET = "pet"
    BUST = "bust"
    SIMPLE_OBJECT = "simple_object"


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class TaskStatus(StrEnum):
    DRAFT = "draft"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class TaskStage(StrEnum):
    UPLOAD_VALIDATION = "upload_validation"
    PREPROCESSING = "preprocessing"
    MODEL_GENERATING = "model_generating"
    PAPERABILITY_OPTIMIZING = "paperability_optimizing"
    DECIMATING = "decimating"
    UNFOLDING = "unfolding"
    EXPORTING = "exporting"
    COMPLETED = "completed"


class ComplexityLevel(StrEnum):
    SIMPLE = "simple"
    BALANCED = "balanced"
    DETAILED = "detailed"


class PaperSize(StrEnum):
    A4 = "a4"
    A3 = "a3"


class TextureMode(StrEnum):
    PLAIN = "plain"
    SOURCE_TEXTURE = "source_texture"
    PRINT_FRIENDLY = "print_friendly"


class BuildDifficultyMode(StrEnum):
    EASY = "easy"
    STANDARD = "standard"
    ADVANCED = "advanced"


class ArtifactKind(StrEnum):
    SOURCE_IMAGE = "source_image"
    PREPROCESS_MASK = "preprocess_mask"
    PREPROCESS_CROP = "preprocess_crop"
    BASE_MESH = "base_mesh"
    REPAIRED_MESH = "repaired_mesh"
    LOW_POLY_MESH = "low_poly_mesh"
    NET_JSON = "net_json"
    NET_SVG = "net_svg"
    PREVIEW_IMAGE = "preview_image"
    PREVIEW_MODEL = "preview_model"
    EXPORT_PDF = "export_pdf"


class TaskEventType(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    PROGRESS_UPDATED = "progress_updated"
    FAILED = "failed"
    RETRY_REQUESTED = "retry_requested"
    CANCELED = "canceled"
    COMPLETED = "completed"


class ErrorCode(StrEnum):
    REQUEST_VALIDATION_FAILED = "REQUEST_VALIDATION_FAILED"
    UPLOAD_UNSUPPORTED_TYPE = "UPLOAD_UNSUPPORTED_TYPE"
    UPLOAD_FILE_TOO_LARGE = "UPLOAD_FILE_TOO_LARGE"
    UPLOAD_TOO_MANY_IMAGES = "UPLOAD_TOO_MANY_IMAGES"
    UPLOAD_IMAGE_INVALID = "UPLOAD_IMAGE_INVALID"
    PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    TASK_INVALID_STATE = "TASK_INVALID_STATE"
    TASK_RETRY_NOT_ALLOWED = "TASK_RETRY_NOT_ALLOWED"
    PREPROCESS_SUBJECT_NOT_FOUND = "PREPROCESS_SUBJECT_NOT_FOUND"
    PREPROCESS_FAILED = "PREPROCESS_FAILED"
    MODEL_GEN_FAILED = "MODEL_GEN_FAILED"
    PAPERABILITY_OPT_FAILED = "PAPERABILITY_OPT_FAILED"
    DECIMATE_FAILED = "DECIMATE_FAILED"
    UNFOLD_FAILED = "UNFOLD_FAILED"
    EXPORT_FAILED = "EXPORT_FAILED"
    STORAGE_WRITE_FAILED = "STORAGE_WRITE_FAILED"
    STORAGE_READ_FAILED = "STORAGE_READ_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
