from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.observability import build_task_metrics_report

router = APIRouter(tags=["metrics"])


@router.get("/metrics/tasks")
def task_metrics(db: Session = Depends(get_db)) -> dict[str, object]:
    report = build_task_metrics_report(db)
    return {
        "summary": report.summary,
        "stage_durations_ms": report.stage_durations_ms,
        "failure_counts": report.failure_counts,
        "business_metrics": report.business_metrics,
        "alerts": report.alerts,
    }
