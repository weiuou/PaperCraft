import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import TaskStage, TaskStatus


class TaskStatusResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    task_id: uuid.UUID
    project_id: uuid.UUID
    status: TaskStatus
    stage: TaskStage
    progress: int = Field(ge=0, le=100)
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime
