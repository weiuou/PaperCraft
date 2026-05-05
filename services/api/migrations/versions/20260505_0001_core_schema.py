"""create core platform schema

Revision ID: 20260505_0001
Revises:
Create Date: 2026-05-05
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260505_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("plan_type", sa.String(length=40), nullable=False, server_default="free"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
        sa.Column("cover_image_url", sa.Text(), nullable=True),
        sa.Column("latest_task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("category in ('pet','bust','simple_object')", name="ck_projects_category"),
        sa.CheckConstraint("status in ('draft','active','archived','deleted')", name="ck_projects_status"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_status", "projects", ["status"])
    op.create_index("ix_projects_user_id", "projects", ["user_id"])

    op.create_table(
        "source_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "sort_order", name="uq_source_images_project_sort_order"),
    )
    op.create_index("ix_source_images_project_id", "source_images", ["project_id"])

    op.create_table(
        "generation_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
        sa.Column("stage", sa.String(length=64), nullable=False, server_default="upload_validation"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retry_from_stage", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status in ('draft','queued','in_progress','completed','failed','canceled')",
            name="ck_generation_tasks_status",
        ),
        sa.CheckConstraint(
            "stage in ('upload_validation','preprocessing','model_generating','paperability_optimizing','decimating','unfolding','exporting','completed')",
            name="ck_generation_tasks_stage",
        ),
        sa.CheckConstraint("progress >= 0 and progress <= 100", name="ck_generation_tasks_progress"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generation_tasks_project_id", "generation_tasks", ["project_id"])
    op.create_index("ix_generation_tasks_stage", "generation_tasks", ["stage"])
    op.create_index("ix_generation_tasks_status", "generation_tasks", ["status"])

    op.create_table(
        "param_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("complexity_level", sa.String(length=40), nullable=False, server_default="balanced"),
        sa.Column("target_poly_count", sa.Integer(), nullable=False),
        sa.Column("paper_size", sa.String(length=20), nullable=False, server_default="a4"),
        sa.Column("texture_mode", sa.String(length=40), nullable=False, server_default="print_friendly"),
        sa.Column("flap_size", sa.Integer(), nullable=False),
        sa.Column("max_pages", sa.Integer(), nullable=False),
        sa.Column("build_difficulty_mode", sa.String(length=40), nullable=False, server_default="standard"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("category in ('pet','bust','simple_object')", name="ck_param_configs_category"),
        sa.CheckConstraint("complexity_level in ('simple','balanced','detailed')", name="ck_param_configs_complexity_level"),
        sa.CheckConstraint("paper_size in ('a4','a3')", name="ck_param_configs_paper_size"),
        sa.CheckConstraint("texture_mode in ('plain','source_texture','print_friendly')", name="ck_param_configs_texture_mode"),
        sa.CheckConstraint("build_difficulty_mode in ('easy','standard','advanced')", name="ck_param_configs_build_difficulty_mode"),
        sa.CheckConstraint("target_poly_count > 0", name="ck_param_configs_target_poly_count"),
        sa.CheckConstraint("flap_size > 0", name="ck_param_configs_flap_size"),
        sa.CheckConstraint("max_pages > 0", name="ck_param_configs_max_pages"),
        sa.ForeignKeyConstraint(["task_id"], ["generation_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id"),
    )
    op.create_index("ix_param_configs_task_id", "param_configs", ["task_id"])

    op.create_table(
        "artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "kind in ('source_image','preprocess_mask','preprocess_crop','base_mesh','repaired_mesh','low_poly_mesh','net_json','net_svg','preview_image','preview_model','export_pdf')",
            name="ck_artifacts_kind",
        ),
        sa.ForeignKeyConstraint(["task_id"], ["generation_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_artifacts_kind", "artifacts", ["kind"])
    op.create_index("ix_artifacts_task_id", "artifacts", ["task_id"])

    op.create_table(
        "assembly_metadata",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("part_count", sa.Integer(), nullable=False),
        sa.Column("difficulty_score", sa.Integer(), nullable=False),
        sa.Column("estimated_build_minutes", sa.Integer(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("page_count > 0", name="ck_assembly_metadata_page_count"),
        sa.CheckConstraint("part_count > 0", name="ck_assembly_metadata_part_count"),
        sa.CheckConstraint("difficulty_score >= 1 and difficulty_score <= 10", name="ck_assembly_metadata_difficulty_score"),
        sa.CheckConstraint("estimated_build_minutes > 0", name="ck_assembly_metadata_estimated_build_minutes"),
        sa.ForeignKeyConstraint(["task_id"], ["generation_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id"),
    )
    op.create_index("ix_assembly_metadata_task_id", "assembly_metadata", ["task_id"])

    op.create_table(
        "task_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "stage in ('upload_validation','preprocessing','model_generating','paperability_optimizing','decimating','unfolding','exporting','completed')",
            name="ck_task_events_stage",
        ),
        sa.CheckConstraint(
            "event_type in ('created','queued','stage_started','stage_completed','progress_updated','failed','retry_requested','canceled','completed')",
            name="ck_task_events_event_type",
        ),
        sa.ForeignKeyConstraint(["task_id"], ["generation_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_events_event_type", "task_events", ["event_type"])
    op.create_index("ix_task_events_stage", "task_events", ["stage"])
    op.create_index("ix_task_events_task_id", "task_events", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_task_events_task_id", table_name="task_events")
    op.drop_index("ix_task_events_stage", table_name="task_events")
    op.drop_index("ix_task_events_event_type", table_name="task_events")
    op.drop_table("task_events")
    op.drop_index("ix_assembly_metadata_task_id", table_name="assembly_metadata")
    op.drop_table("assembly_metadata")
    op.drop_index("ix_artifacts_task_id", table_name="artifacts")
    op.drop_index("ix_artifacts_kind", table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_index("ix_param_configs_task_id", table_name="param_configs")
    op.drop_table("param_configs")
    op.drop_index("ix_generation_tasks_status", table_name="generation_tasks")
    op.drop_index("ix_generation_tasks_stage", table_name="generation_tasks")
    op.drop_index("ix_generation_tasks_project_id", table_name="generation_tasks")
    op.drop_table("generation_tasks")
    op.drop_index("ix_source_images_project_id", table_name="source_images")
    op.drop_table("source_images")
    op.drop_index("ix_projects_user_id", table_name="projects")
    op.drop_index("ix_projects_status", table_name="projects")
    op.drop_table("projects")
    op.drop_table("users")
