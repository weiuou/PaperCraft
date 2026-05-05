import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.domain.enums import (
    ArtifactKind,
    BuildDifficultyMode,
    ComplexityLevel,
    PaperSize,
    ProjectCategory,
    ProjectStatus,
    TaskEventType,
    TaskStage,
    TaskStatus,
    TextureMode,
)


def enum_column(enum_type: type, length: int = 64) -> Mapped[str]:
    return mapped_column(String(length), nullable=False)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(String(120))
    plan_type: Mapped[str] = mapped_column(String(40), nullable=False, default="free")

    projects: Mapped[list["Project"]] = relationship(back_populates="user")


class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            f"category in ({','.join(repr(value.value) for value in ProjectCategory)})",
            name="ck_projects_category",
        ),
        CheckConstraint(
            f"status in ({','.join(repr(value.value) for value in ProjectStatus)})",
            name="ck_projects_status",
        ),
        Index("ix_projects_user_id", "user_id"),
        Index("ix_projects_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = enum_column(ProjectCategory)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default=ProjectStatus.DRAFT.value)
    cover_image_url: Mapped[str | None] = mapped_column(Text)
    latest_task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    user: Mapped[User] = relationship(back_populates="projects")
    source_images: Mapped[list["SourceImage"]] = relationship(back_populates="project")
    generation_tasks: Mapped[list["GenerationTask"]] = relationship(back_populates="project")


class SourceImage(Base):
    __tablename__ = "source_images"
    __table_args__ = (
        Index("ix_source_images_project_id", "project_id"),
        UniqueConstraint("project_id", "sort_order", name="uq_source_images_project_sort_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    project: Mapped[Project] = relationship(back_populates="source_images")


class GenerationTask(TimestampMixin, Base):
    __tablename__ = "generation_tasks"
    __table_args__ = (
        CheckConstraint(
            f"status in ({','.join(repr(value.value) for value in TaskStatus)})",
            name="ck_generation_tasks_status",
        ),
        CheckConstraint(
            f"stage in ({','.join(repr(value.value) for value in TaskStage)})",
            name="ck_generation_tasks_stage",
        ),
        CheckConstraint("progress >= 0 and progress <= 100", name="ck_generation_tasks_progress"),
        Index("ix_generation_tasks_project_id", "project_id"),
        Index("ix_generation_tasks_status", "status"),
        Index("ix_generation_tasks_stage", "stage"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default=TaskStatus.DRAFT.value)
    stage: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=TaskStage.UPLOAD_VALIDATION.value,
    )
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_from_stage: Mapped[str | None] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="generation_tasks")
    param_config: Mapped["ParamConfig | None"] = relationship(back_populates="task")
    artifacts: Mapped[list["Artifact"]] = relationship(back_populates="task")
    assembly_metadata: Mapped["AssemblyMetadata | None"] = relationship(back_populates="task")
    events: Mapped[list["TaskEvent"]] = relationship(back_populates="task")


class ParamConfig(Base):
    __tablename__ = "param_configs"
    __table_args__ = (
        CheckConstraint(
            f"category in ({','.join(repr(value.value) for value in ProjectCategory)})",
            name="ck_param_configs_category",
        ),
        CheckConstraint(
            f"complexity_level in ({','.join(repr(value.value) for value in ComplexityLevel)})",
            name="ck_param_configs_complexity_level",
        ),
        CheckConstraint(
            f"paper_size in ({','.join(repr(value.value) for value in PaperSize)})",
            name="ck_param_configs_paper_size",
        ),
        CheckConstraint(
            f"texture_mode in ({','.join(repr(value.value) for value in TextureMode)})",
            name="ck_param_configs_texture_mode",
        ),
        CheckConstraint(
            f"build_difficulty_mode in ({','.join(repr(value.value) for value in BuildDifficultyMode)})",
            name="ck_param_configs_build_difficulty_mode",
        ),
        CheckConstraint("target_poly_count > 0", name="ck_param_configs_target_poly_count"),
        CheckConstraint("flap_size > 0", name="ck_param_configs_flap_size"),
        CheckConstraint("max_pages > 0", name="ck_param_configs_max_pages"),
        Index("ix_param_configs_task_id", "task_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("generation_tasks.id"), nullable=False, unique=True)
    category: Mapped[str] = enum_column(ProjectCategory)
    complexity_level: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default=ComplexityLevel.BALANCED.value,
    )
    target_poly_count: Mapped[int] = mapped_column(Integer, nullable=False)
    paper_size: Mapped[str] = mapped_column(String(20), nullable=False, default=PaperSize.A4.value)
    texture_mode: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default=TextureMode.PRINT_FRIENDLY.value,
    )
    flap_size: Mapped[int] = mapped_column(Integer, nullable=False)
    max_pages: Mapped[int] = mapped_column(Integer, nullable=False)
    build_difficulty_mode: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default=BuildDifficultyMode.STANDARD.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    task: Mapped[GenerationTask] = relationship(back_populates="param_config")


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        CheckConstraint(
            f"kind in ({','.join(repr(value.value) for value in ArtifactKind)})",
            name="ck_artifacts_kind",
        ),
        Index("ix_artifacts_task_id", "task_id"),
        Index("ix_artifacts_kind", "kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("generation_tasks.id"), nullable=False)
    kind: Mapped[str] = enum_column(ArtifactKind)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer)
    artifact_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    task: Mapped[GenerationTask] = relationship(back_populates="artifacts")


class AssemblyMetadata(TimestampMixin, Base):
    __tablename__ = "assembly_metadata"
    __table_args__ = (
        CheckConstraint("page_count > 0", name="ck_assembly_metadata_page_count"),
        CheckConstraint("part_count > 0", name="ck_assembly_metadata_part_count"),
        CheckConstraint(
            "difficulty_score >= 1 and difficulty_score <= 10",
            name="ck_assembly_metadata_difficulty_score",
        ),
        CheckConstraint(
            "estimated_build_minutes > 0",
            name="ck_assembly_metadata_estimated_build_minutes",
        ),
        Index("ix_assembly_metadata_task_id", "task_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("generation_tasks.id"), nullable=False, unique=True)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    part_count: Mapped[int] = mapped_column(Integer, nullable=False)
    difficulty_score: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_build_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    assembly_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)

    task: Mapped[GenerationTask] = relationship(back_populates="assembly_metadata")


class TaskEvent(Base):
    __tablename__ = "task_events"
    __table_args__ = (
        CheckConstraint(
            f"stage in ({','.join(repr(value.value) for value in TaskStage)})",
            name="ck_task_events_stage",
        ),
        CheckConstraint(
            f"event_type in ({','.join(repr(value.value) for value in TaskEventType)})",
            name="ck_task_events_event_type",
        ),
        Index("ix_task_events_task_id", "task_id"),
        Index("ix_task_events_stage", "stage"),
        Index("ix_task_events_event_type", "event_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("generation_tasks.id"), nullable=False)
    stage: Mapped[str | None] = mapped_column(String(64))
    event_type: Mapped[str] = enum_column(TaskEventType)
    message: Mapped[str | None] = mapped_column(Text)
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    task: Mapped[GenerationTask] = relationship(back_populates="events")
