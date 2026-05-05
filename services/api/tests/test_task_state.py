from app.domain.enums import TaskStage, TaskStatus
from app.domain.task_state import (
    can_advance_stage,
    can_retry_from_stage,
    can_transition_status,
    next_stage,
)


def test_status_transition_allows_expected_mvp_flow() -> None:
    assert can_transition_status(TaskStatus.DRAFT, TaskStatus.QUEUED)
    assert can_transition_status(TaskStatus.QUEUED, TaskStatus.IN_PROGRESS)
    assert can_transition_status(TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED)


def test_status_transition_rejects_completed_requeue() -> None:
    assert not can_transition_status(TaskStatus.COMPLETED, TaskStatus.QUEUED)


def test_stage_advancement_is_linear() -> None:
    assert next_stage(TaskStage.PREPROCESSING) == TaskStage.MODEL_GENERATING
    assert can_advance_stage(TaskStage.UNFOLDING, TaskStage.EXPORTING)
    assert not can_advance_stage(TaskStage.PREPROCESSING, TaskStage.UNFOLDING)


def test_retry_is_not_allowed_from_completed_stage() -> None:
    assert can_retry_from_stage(TaskStage.DECIMATING)
    assert not can_retry_from_stage(TaskStage.COMPLETED)
