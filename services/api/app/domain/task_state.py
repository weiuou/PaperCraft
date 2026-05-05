from .enums import TaskStage, TaskStatus


PIPELINE_STAGES: tuple[TaskStage, ...] = (
    TaskStage.UPLOAD_VALIDATION,
    TaskStage.PREPROCESSING,
    TaskStage.MODEL_GENERATING,
    TaskStage.PAPERABILITY_OPTIMIZING,
    TaskStage.DECIMATING,
    TaskStage.UNFOLDING,
    TaskStage.EXPORTING,
    TaskStage.COMPLETED,
)

ALLOWED_STATUS_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.DRAFT: {TaskStatus.QUEUED},
    TaskStatus.QUEUED: {TaskStatus.IN_PROGRESS, TaskStatus.CANCELED},
    TaskStatus.IN_PROGRESS: {
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELED,
    },
    TaskStatus.FAILED: {TaskStatus.QUEUED},
    TaskStatus.CANCELED: {TaskStatus.QUEUED},
    TaskStatus.COMPLETED: set(),
}


def can_transition_status(current: TaskStatus, next_status: TaskStatus) -> bool:
    return next_status in ALLOWED_STATUS_TRANSITIONS[current]


def next_stage(stage: TaskStage) -> TaskStage | None:
    index = PIPELINE_STAGES.index(stage)
    if index == len(PIPELINE_STAGES) - 1:
        return None
    return PIPELINE_STAGES[index + 1]


def can_advance_stage(current: TaskStage, next_value: TaskStage) -> bool:
    return next_stage(current) == next_value


def can_retry_from_stage(stage: TaskStage) -> bool:
    return stage in PIPELINE_STAGES and stage != TaskStage.COMPLETED
