import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    BuildDifficultyMode,
    ComplexityLevel,
    PaperSize,
    ProjectCategory,
    ProjectStatus,
    TaskStage,
    TaskStatus,
    TextureMode,
)


class CreateProjectRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    category: ProjectCategory


class ProjectResponse(BaseModel):
    project_id: uuid.UUID
    title: str
    category: ProjectCategory
    status: ProjectStatus
    latest_task_id: uuid.UUID | None
    image_count: int
    task_count: int
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]


class ImageResponse(BaseModel):
    image_id: uuid.UUID
    project_id: uuid.UUID
    storage_key: str
    mime_type: str
    width: int
    height: int
    file_size: int
    sort_order: int
    created_at: datetime


class CreateTaskRequest(BaseModel):
    complexity_level: ComplexityLevel = ComplexityLevel.BALANCED
    target_poly_count: int = Field(gt=0)
    paper_size: PaperSize = PaperSize.A4
    texture_mode: TextureMode = TextureMode.PRINT_FRIENDLY
    flap_size: int = Field(gt=0)
    max_pages: int = Field(gt=0)
    build_difficulty_mode: BuildDifficultyMode = BuildDifficultyMode.STANDARD


class TaskCreatedResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    task_id: uuid.UUID
    project_id: uuid.UUID
    initial_status: TaskStatus
    status: TaskStatus
    stage: TaskStage
    progress: int
