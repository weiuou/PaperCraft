from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AssemblyMetadata, GenerationTask, TaskEvent
from app.domain.enums import TaskEventType, TaskStatus


@dataclass(frozen=True)
class TaskMetricsReport:
    summary: dict[str, Any]
    stage_durations_ms: dict[str, dict[str, float | int]]
    failure_counts: dict[str, int]
    business_metrics: dict[str, float | int | None]
    alerts: list[dict[str, str]]


def build_task_metrics_report(db: Session) -> TaskMetricsReport:
    tasks = db.scalars(select(GenerationTask)).all()
    events = db.scalars(select(TaskEvent)).all()
    assemblies = db.scalars(select(AssemblyMetadata)).all()

    status_counts = Counter(task.status for task in tasks)
    total_tasks = len(tasks)
    completed_tasks = status_counts[TaskStatus.COMPLETED.value]
    failed_tasks = status_counts[TaskStatus.FAILED.value]

    stage_durations: dict[str, list[float]] = defaultdict(list)
    failure_counts: Counter[str] = Counter()
    for event in events:
        if event.event_type == TaskEventType.STAGE_COMPLETED.value:
            duration = event.event_metadata.get("duration_ms")
            if isinstance(duration, int | float) and event.stage:
                stage_durations[event.stage].append(float(duration))
        if event.event_type == TaskEventType.FAILED.value:
            failure_counts[str(event.stage or "unknown")] += 1

    page_counts = [assembly.page_count for assembly in assemblies]
    part_counts = [assembly.part_count for assembly in assemblies]
    report = TaskMetricsReport(
        summary={
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "canceled_tasks": status_counts[TaskStatus.CANCELED.value],
            "in_progress_tasks": status_counts[TaskStatus.IN_PROGRESS.value],
            "queued_tasks": status_counts[TaskStatus.QUEUED.value],
            "completion_rate": _rate(completed_tasks, total_tasks),
            "failure_rate": _rate(failed_tasks, total_tasks),
        },
        stage_durations_ms={
            stage: {
                "count": len(values),
                "avg": round(sum(values) / len(values), 2),
                "max": round(max(values), 2),
            }
            for stage, values in sorted(stage_durations.items())
            if values
        },
        failure_counts=dict(sorted(failure_counts.items())),
        business_metrics={
            "export_rate": _rate(len(assemblies), total_tasks),
            "average_page_count": _average(page_counts),
            "average_part_count": _average(part_counts),
        },
        alerts=_alerts(total_tasks=total_tasks, completed_tasks=completed_tasks, failed_tasks=failed_tasks),
    )
    return report


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _average(values: list[int]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _alerts(*, total_tasks: int, completed_tasks: int, failed_tasks: int) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []
    if total_tasks == 0:
        alerts.append({"level": "info", "code": "NO_TASKS", "message": "No generation tasks have been recorded yet."})
        return alerts
    if _rate(completed_tasks, total_tasks) < 0.6:
        alerts.append(
            {
                "level": "warning",
                "code": "LOW_COMPLETION_RATE",
                "message": "Task completion rate is below the MVP acceptance target.",
            }
        )
    if failed_tasks >= 3 and _rate(failed_tasks, total_tasks) >= 0.25:
        alerts.append(
            {
                "level": "warning",
                "code": "HIGH_FAILURE_RATE",
                "message": "Failure rate is high enough to require pipeline investigation.",
            }
        )
    return alerts
