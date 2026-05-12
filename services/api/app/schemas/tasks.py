import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import ArtifactKind, TaskStage, TaskStatus


class ArtifactResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    artifact_id: uuid.UUID
    kind: ArtifactKind
    storage_key: str
    download_url: str
    mime_type: str
    file_size: int | None
    metadata: dict[str, Any]
    created_at: datetime


class AssemblyMetadataResponse(BaseModel):
    page_count: int
    part_count: int
    difficulty_score: int = Field(ge=1, le=10)
    estimated_build_minutes: int
    metadata: dict[str, Any]


class TaskStatusResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    task_id: uuid.UUID
    project_id: uuid.UUID
    status: TaskStatus
    stage: TaskStage
    progress: int = Field(ge=0, le=100)
    error_code: str | None
    error_message: str | None
    artifacts: list[ArtifactResponse]
    assembly_metadata: AssemblyMetadataResponse | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RetryTaskRequest(BaseModel):
    stage: TaskStage


class ProjectTaskHistoryResponse(BaseModel):
    tasks: list[TaskStatusResponse]
