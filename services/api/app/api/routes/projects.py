import uuid
from io import BytesIO

from fastapi import APIRouter, Depends, File, UploadFile, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.errors import ApiError
from app.config import get_settings
from app.db.models import GenerationTask, ParamConfig, Project, SourceImage, TaskEvent, User
from app.domain.enums import ErrorCode, ProjectStatus, TaskEventType, TaskStage, TaskStatus
from app.schemas.projects import (
    CreateProjectRequest,
    CreateTaskRequest,
    ImageResponse,
    ProjectListResponse,
    ProjectResponse,
    TaskCreatedResponse,
)
from app.services.task_dispatch import enqueue_generation_task
from app.services.storage_paths import source_image_key

router = APIRouter(tags=["projects"])

_DEV_USER_EMAIL = "local-user@papercraft.dev"
_SUPPORTED_UPLOAD_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _get_or_create_dev_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.email == _DEV_USER_EMAIL))
    if user is not None:
        return user

    user = User(email=_DEV_USER_EMAIL, display_name="Local User")
    db.add(user)
    db.flush()
    return user


def _get_project_or_404(db: Session, project_id: uuid.UUID) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise ApiError(
            ErrorCode.PROJECT_NOT_FOUND,
            "Project was not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"project_id": str(project_id)},
        )
    return project


def _project_response(project: Project, *, image_count: int = 0, task_count: int = 0) -> ProjectResponse:
    return ProjectResponse(
        project_id=project.id,
        title=project.title,
        category=project.category,
        status=project.status,
        latest_task_id=project.latest_task_id,
        image_count=image_count,
        task_count=task_count,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: CreateProjectRequest, db: Session = Depends(get_db)) -> ProjectResponse:
    user = _get_or_create_dev_user(db)
    project = Project(
        user_id=user.id,
        title=payload.title,
        category=payload.category.value,
        status=ProjectStatus.DRAFT.value,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return _project_response(project)


@router.get("/projects", response_model=ProjectListResponse)
def list_projects(db: Session = Depends(get_db)) -> ProjectListResponse:
    projects = db.scalars(select(Project).order_by(Project.created_at.desc(), Project.id.desc())).all()
    responses = []
    for project in projects:
        image_count = db.scalar(select(func.count()).select_from(SourceImage).where(SourceImage.project_id == project.id))
        task_count = db.scalar(
            select(func.count()).select_from(GenerationTask).where(GenerationTask.project_id == project.id)
        )
        responses.append(_project_response(project, image_count=image_count or 0, task_count=task_count or 0))
    return ProjectListResponse(projects=responses)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: uuid.UUID, db: Session = Depends(get_db)) -> ProjectResponse:
    project = _get_project_or_404(db, project_id)
    image_count = db.scalar(select(func.count()).select_from(SourceImage).where(SourceImage.project_id == project.id))
    task_count = db.scalar(select(func.count()).select_from(GenerationTask).where(GenerationTask.project_id == project.id))
    return _project_response(project, image_count=image_count or 0, task_count=task_count or 0)


@router.post("/projects/{project_id}/images", response_model=ImageResponse, status_code=status.HTTP_201_CREATED)
async def upload_project_image(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ImageResponse:
    project = _get_project_or_404(db, project_id)
    settings = get_settings()

    image_count = db.scalar(select(func.count()).select_from(SourceImage).where(SourceImage.project_id == project.id)) or 0
    if image_count >= settings.max_upload_images:
        raise ApiError(
            ErrorCode.UPLOAD_TOO_MANY_IMAGES,
            "Project already has the maximum number of source images.",
            details={"max_upload_images": settings.max_upload_images},
        )

    if file.content_type not in _SUPPORTED_UPLOAD_TYPES:
        raise ApiError(
            ErrorCode.UPLOAD_UNSUPPORTED_TYPE,
            "Uploaded image type is not supported.",
            details={"supported_types": sorted(_SUPPORTED_UPLOAD_TYPES)},
        )

    contents = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(contents) > max_bytes:
        raise ApiError(
            ErrorCode.UPLOAD_FILE_TOO_LARGE,
            "Uploaded image exceeds the configured size limit.",
            details={"max_upload_mb": settings.max_upload_mb},
        )

    try:
        with Image.open(BytesIO(contents)) as image:
            width, height = image.size
            image.verify()
    except (UnidentifiedImageError, OSError):
        raise ApiError(ErrorCode.UPLOAD_IMAGE_INVALID, "Uploaded image could not be decoded.")

    image_id = uuid.uuid4()
    storage_key = source_image_key(project.id, image_id, file.filename or "upload")
    source_image = SourceImage(
        id=image_id,
        project_id=project.id,
        storage_key=storage_key,
        mime_type=file.content_type,
        width=width,
        height=height,
        file_size=len(contents),
        sort_order=image_count,
    )
    db.add(source_image)
    db.commit()
    db.refresh(source_image)

    return ImageResponse(
        image_id=source_image.id,
        project_id=source_image.project_id,
        storage_key=source_image.storage_key,
        mime_type=source_image.mime_type,
        width=source_image.width,
        height=source_image.height,
        file_size=source_image.file_size,
        sort_order=source_image.sort_order,
        created_at=source_image.created_at,
    )


@router.post("/projects/{project_id}/tasks", response_model=TaskCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_project_task(
    project_id: uuid.UUID,
    payload: CreateTaskRequest,
    db: Session = Depends(get_db),
) -> TaskCreatedResponse:
    project = _get_project_or_404(db, project_id)

    task = GenerationTask(
        project_id=project.id,
        status=TaskStatus.QUEUED.value,
        stage=TaskStage.UPLOAD_VALIDATION.value,
        progress=0,
    )
    db.add(task)
    db.flush()

    param_config = ParamConfig(
        task_id=task.id,
        category=project.category,
        complexity_level=payload.complexity_level.value,
        target_poly_count=payload.target_poly_count,
        paper_size=payload.paper_size.value,
        texture_mode=payload.texture_mode.value,
        flap_size=payload.flap_size,
        max_pages=payload.max_pages,
        build_difficulty_mode=payload.build_difficulty_mode.value,
    )
    db.add(param_config)
    db.add(
        TaskEvent(
            task_id=task.id,
            stage=TaskStage.UPLOAD_VALIDATION.value,
            event_type=TaskEventType.QUEUED.value,
            message="Task queued for generation.",
            event_metadata={},
        )
    )
    project.status = ProjectStatus.ACTIVE.value
    project.latest_task_id = task.id
    db.commit()
    db.refresh(task)
    enqueue_generation_task(task.id)

    return TaskCreatedResponse(
        task_id=task.id,
        project_id=task.project_id,
        initial_status=TaskStatus.QUEUED,
        status=task.status,
        stage=task.stage,
        progress=task.progress,
    )
