"use client";

import {
  AlertCircle,
  Box,
  CheckCircle2,
  Download,
  FileJson,
  FileText,
  History,
  Layers,
  Loader2,
  Play,
  RefreshCw,
  RotateCcw,
  Square,
  Upload,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import type {
  ApiErrorResponse,
  ArtifactResponse,
  BuildDifficultyMode,
  ComplexityLevel,
  CreateTaskRequest,
  ImageResponse,
  PaperSize,
  ProjectCategory,
  ProjectTaskHistoryResponse,
  ProjectResponse,
  TaskCreatedResponse,
  TaskStage,
  TaskStatusResponse,
  TextureMode,
} from "../lib/api-types";

const categories: Array<{ label: string; value: ProjectCategory }> = [
  { label: "Pet", value: "pet" },
  { label: "Bust", value: "bust" },
  { label: "Object", value: "simple_object" },
];

const stages: Array<{ label: string; value: TaskStage }> = [
  { label: "Upload", value: "upload_validation" },
  { label: "Prep", value: "preprocessing" },
  { label: "Model", value: "model_generating" },
  { label: "Paperability", value: "paperability_optimizing" },
  { label: "Decimate", value: "decimating" },
  { label: "Unfold", value: "unfolding" },
  { label: "Export", value: "exporting" },
  { label: "Done", value: "completed" },
];

const mockFailureStages: Array<{ label: string; value: TaskStage | "none" }> = [
  { label: "No mock failure", value: "none" },
  { label: "Preprocessing fails", value: "preprocessing" },
  { label: "Model generation fails", value: "model_generating" },
  { label: "Paperability fails", value: "paperability_optimizing" },
  { label: "Decimation fails", value: "decimating" },
  { label: "Unfolding fails", value: "unfolding" },
  { label: "Export fails", value: "exporting" },
];

type DraftParams = {
  complexity_level: ComplexityLevel;
  target_poly_count: number;
  paper_size: PaperSize;
  texture_mode: TextureMode;
  flap_size: number;
  max_pages: number;
  build_difficulty_mode: BuildDifficultyMode;
};

type PaperNetPreview = {
  mock: boolean;
  artifact_id: string;
  pages: Array<{
    page: number;
    paper_size: string;
    parts: Array<{
      id: string;
      label: string;
      fold_lines: number;
      glue_flaps: number;
    }>;
  }>;
};

const defaultParams: DraftParams = {
  complexity_level: "balanced",
  target_poly_count: 300,
  paper_size: "a4",
  texture_mode: "print_friendly",
  flap_size: 5,
  max_pages: 12,
  build_difficulty_mode: "standard",
};

export default function StudioPage() {
  const [title, setTitle] = useState("Paper Cat Demo");
  const [category, setCategory] = useState<ProjectCategory>("pet");
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [params, setParams] = useState<DraftParams>(defaultParams);
  const [project, setProject] = useState<ProjectResponse | null>(null);
  const [image, setImage] = useState<ImageResponse | null>(null);
  const [task, setTask] = useState<TaskStatusResponse | null>(null);
  const [taskHistory, setTaskHistory] = useState<TaskStatusResponse[]>([]);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [netPreview, setNetPreview] = useState<PaperNetPreview | null>(null);
  const [netPreviewError, setNetPreviewError] = useState<string | null>(null);
  const [selectedNetPageIndex, setSelectedNetPageIndex] = useState(0);
  const [mockFailureStage, setMockFailureStage] = useState<TaskStage | "none">("none");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    fetch("/api/backend-health")
      .then((response) => response.json() as Promise<{ online: boolean }>)
      .then((payload) => setApiOnline(payload.online))
      .catch(() => setApiOnline(false));
  }, []);

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  useEffect(() => {
    if (!task || task.status === "completed" || task.status === "failed" || task.status === "canceled") {
      return;
    }
    const poll = window.setInterval(() => {
      void loadTask(task.task_id);
    }, 1500);
    return () => window.clearInterval(poll);
  }, [task?.task_id, task?.status]);

  const artifactsByKind = useMemo(() => {
    return Object.groupBy(task?.artifacts ?? [], (artifact) => artifact.kind);
  }, [task?.artifacts]);

  const netArtifact = artifactsByKind.net_json?.[0];

  const canCancel = task?.status === "queued" || task?.status === "in_progress";
  const canRetry = task?.status === "failed" || task?.status === "canceled";
  const canRegenerate = project !== null && image !== null && !canCancel;

  useEffect(() => {
    if (!netArtifact) {
      setNetPreview(null);
      setNetPreviewError(null);
      setSelectedNetPageIndex(0);
      return;
    }

    let ignore = false;
    fetch(toFrontendDownloadUrl(netArtifact.download_url))
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Net preview request failed with ${response.status}`);
        }
        return response.json() as Promise<PaperNetPreview>;
      })
      .then((payload) => {
        if (!ignore) {
          setNetPreview(payload);
          setNetPreviewError(null);
          setSelectedNetPageIndex(0);
        }
      })
      .catch((caught) => {
        if (!ignore) {
          setNetPreview(null);
          setNetPreviewError(caught instanceof Error ? caught.message : "Net preview could not be loaded.");
        }
      });

    return () => {
      ignore = true;
    };
  }, [netArtifact?.download_url]);

  async function loadTask(taskId: string, options: { syncHistory?: boolean } = {}) {
    const nextTask = await requestJson<TaskStatusResponse>(`/backend/tasks/${taskId}`);
    setTask(nextTask);
    if (options.syncHistory !== false && project) {
      await loadProjectTasks(project.project_id);
    }
  }

  async function loadProjectTasks(projectId: string) {
    const history = await requestJson<ProjectTaskHistoryResponse>(`/backend/projects/${projectId}/tasks`);
    setTaskHistory(history.tasks);
    return history.tasks;
  }

  function taskPayload(): CreateTaskRequest {
    return {
      ...params,
      mock_failure_stage: mockFailureStage === "none" ? null : mockFailureStage,
    };
  }

  async function submitFlow(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!file) {
      setError("Choose one source image before starting a generation task.");
      return;
    }

    setBusy(true);
    try {
      const createdProject = await requestJson<ProjectResponse>("/backend/projects", {
        method: "POST",
        body: JSON.stringify({ title, category }),
      });
      setProject(createdProject);
      setTaskHistory([]);

      const formData = new FormData();
      formData.append("file", file);
      const uploadedImage = await requestJson<ImageResponse>(`/backend/projects/${createdProject.project_id}/images`, {
        method: "POST",
        body: formData,
      });
      setImage(uploadedImage);

      const createdTask = await requestJson<TaskCreatedResponse>(`/backend/projects/${createdProject.project_id}/tasks`, {
        method: "POST",
        body: JSON.stringify(taskPayload()),
      });
      await loadTask(createdTask.task_id, { syncHistory: false });
      await loadProjectTasks(createdProject.project_id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The generation flow failed.");
    } finally {
      setBusy(false);
    }
  }

  async function regenerateTask() {
    if (!project) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const createdTask = await requestJson<TaskCreatedResponse>(`/backend/projects/${project.project_id}/tasks`, {
        method: "POST",
        body: JSON.stringify(taskPayload()),
      });
      await loadTask(createdTask.task_id, { syncHistory: false });
      await loadProjectTasks(project.project_id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Regeneration failed.");
    } finally {
      setBusy(false);
    }
  }

  async function cancelTask() {
    if (!task) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const canceledTask = await requestJson<TaskStatusResponse>(`/backend/tasks/${task.task_id}/cancel`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      setTask(canceledTask);
      if (project) {
        await loadProjectTasks(project.project_id);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Cancellation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function retryTask() {
    if (!task) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const retriedTask = await requestJson<TaskStatusResponse>(`/backend/tasks/${task.task_id}/retry`, {
        method: "POST",
        body: JSON.stringify({ stage: task.stage === "completed" ? "preprocessing" : task.stage }),
      });
      setTask(retriedTask);
      if (project) {
        await loadProjectTasks(project.project_id);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Retry failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="studio-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">AI PaperCraft Studio</p>
          <h1>M2 demo workbench</h1>
        </div>
        <div className={apiOnline ? "status-pill is-online" : "status-pill"}>
          <span />
          {apiOnline === null ? "Checking API" : apiOnline ? "API online" : "API offline"}
        </div>
      </header>

      <div className="workspace">
        <form className="control-panel" onSubmit={submitFlow}>
          <section className="panel-section">
            <div className="section-title">
              <Upload size={18} />
              <h2>Source</h2>
            </div>
            <label className="field">
              <span>Project title</span>
              <input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={160} required />
            </label>

            <div className="segmented" aria-label="Category">
              {categories.map((item) => (
                <button
                  className={category === item.value ? "is-active" : ""}
                  key={item.value}
                  type="button"
                  onClick={() => setCategory(item.value)}
                >
                  {item.label}
                </button>
              ))}
            </div>

            <div className="upload-target">
              <input
                accept="image/png,image/jpeg,image/webp"
                ref={fileInputRef}
                type="file"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
              {previewUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img alt="" src={previewUrl} />
              ) : (
                <div className="upload-empty">
                  <Upload size={22} />
                  JPG, PNG, WebP
                </div>
              )}
              <button className="choose-file-button" type="button" onClick={() => fileInputRef.current?.click()}>
                <Upload size={17} />
                Choose image
              </button>
              <p className="selected-file">{file ? file.name : "No image selected"}</p>
            </div>
          </section>

          <section className="panel-section">
            <div className="section-title">
              <Layers size={18} />
              <h2>Parameters</h2>
            </div>
            <div className="two-col">
              <label className="field">
                <span>Complexity</span>
                <select
                  value={params.complexity_level}
                  onChange={(event) => setParams({ ...params, complexity_level: event.target.value as ComplexityLevel })}
                >
                  <option value="simple">Simple</option>
                  <option value="balanced">Balanced</option>
                  <option value="detailed">Detailed</option>
                </select>
              </label>
              <label className="field">
                <span>Paper</span>
                <select
                  value={params.paper_size}
                  onChange={(event) => setParams({ ...params, paper_size: event.target.value as PaperSize })}
                >
                  <option value="a4">A4</option>
                  <option value="a3">A3</option>
                </select>
              </label>
              <label className="field">
                <span>Poly target</span>
                <input
                  min={1}
                  type="number"
                  value={params.target_poly_count}
                  onChange={(event) => setParams({ ...params, target_poly_count: Number(event.target.value) })}
                />
              </label>
              <label className="field">
                <span>Max pages</span>
                <input
                  min={1}
                  type="number"
                  value={params.max_pages}
                  onChange={(event) => setParams({ ...params, max_pages: Number(event.target.value) })}
                />
              </label>
              <label className="field">
                <span>Texture</span>
                <select
                  value={params.texture_mode}
                  onChange={(event) => setParams({ ...params, texture_mode: event.target.value as TextureMode })}
                >
                  <option value="plain">Plain</option>
                  <option value="source_texture">Source</option>
                  <option value="print_friendly">Print friendly</option>
                </select>
              </label>
              <label className="field">
                <span>Difficulty</span>
                <select
                  value={params.build_difficulty_mode}
                  onChange={(event) =>
                    setParams({ ...params, build_difficulty_mode: event.target.value as BuildDifficultyMode })
                  }
                >
                  <option value="easy">Easy</option>
                  <option value="standard">Standard</option>
                  <option value="advanced">Advanced</option>
                </select>
              </label>
            </div>
            <label className="field">
              <span>Flap size: {params.flap_size} mm</span>
              <input
                min={1}
                max={16}
                type="range"
                value={params.flap_size}
                onChange={(event) => setParams({ ...params, flap_size: Number(event.target.value) })}
              />
            </label>
            <label className="field">
              <span>Mock outcome</span>
              <select
                value={mockFailureStage}
                onChange={(event) => setMockFailureStage(event.target.value as TaskStage | "none")}
              >
                {mockFailureStages.map((stage) => (
                  <option key={stage.value} value={stage.value}>
                    {stage.label}
                  </option>
                ))}
              </select>
            </label>
          </section>

          <button className="primary-action" disabled={busy} type="submit">
            {busy ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
            Start generation
          </button>
          <div className="action-row">
            <button className="secondary-action" disabled={!canRegenerate || busy} type="button" onClick={regenerateTask}>
              <RotateCcw size={17} />
              Regenerate
            </button>
            <button className="secondary-action muted-action" disabled={!canCancel || busy} type="button" onClick={cancelTask}>
              <Square size={15} />
              Cancel
            </button>
            <button className="secondary-action muted-action" disabled={!canRetry || busy} type="button" onClick={retryTask}>
              <RefreshCw size={17} />
              Retry
            </button>
          </div>
          {error ? (
            <div className="error-strip">
              <AlertCircle size={17} />
              <span>{error}</span>
            </div>
          ) : null}
        </form>

        <section className="stage-panel">
          <div className="stage-header">
            <div>
              <p className="eyebrow">Run state</p>
              <h2>{task ? formatStatus(task.status) : "Ready"}</h2>
            </div>
            <button
              className="icon-button"
              disabled={!task}
              title="Refresh task"
              type="button"
              onClick={() => task && void loadTask(task.task_id)}
            >
              <RefreshCw size={18} />
            </button>
          </div>

          <div className="progress-track" aria-label="Generation progress">
            <span style={{ width: `${task?.progress ?? 0}%` }} />
          </div>
          <div className="stage-grid">
            {stages.map((stage, index) => {
              const currentIndex = task ? stages.findIndex((item) => item.value === task.stage) : -1;
              const isDone = task?.status === "completed" || index < currentIndex;
              const isCurrent = task?.stage === stage.value && task.status !== "completed";
              return (
                <div className={isDone ? "stage-step is-done" : isCurrent ? "stage-step is-current" : "stage-step"} key={stage.value}>
                  {isDone ? <CheckCircle2 size={15} /> : <span />}
                  <strong>{stage.label}</strong>
                </div>
              );
            })}
          </div>

          <div className="summary-row">
            <Metric label="Project" value={project?.title ?? "-"} />
            <Metric label="Images" value={image ? `${image.width} x ${image.height}` : "-"} />
            <Metric label="Progress" value={`${task?.progress ?? 0}%`} />
            <Metric label="Task" value={task ? shortId(task.task_id) : "-"} />
          </div>

          <div className="history-panel">
            <div className="section-title">
              <History size={18} />
              <h2>Task history</h2>
            </div>
            <div className="history-list">
              {taskHistory.length > 0 ? (
                taskHistory.map((historyTask) => (
                  <button
                    className={task?.task_id === historyTask.task_id ? "history-item is-active" : "history-item"}
                    key={historyTask.task_id}
                    type="button"
                    onClick={() => setTask(historyTask)}
                  >
                    <strong>{shortId(historyTask.task_id)}</strong>
                    <span>{formatStatus(historyTask.status)}</span>
                    <span>{historyTask.progress}%</span>
                  </button>
                ))
              ) : (
                <p className="empty-copy">Task runs will appear after the first generation starts.</p>
              )}
            </div>
          </div>

          <div className="workbench">
            <PreviewPane
              artifact={artifactsByKind.preview_model?.[0]}
              icon={<Box size={20} />}
              title="3D preview"
              variant="model"
            />
            <NetPreviewPane
              artifact={artifactsByKind.net_json?.[0]}
              error={netPreviewError}
              onPageChange={setSelectedNetPageIndex}
              pageIndex={selectedNetPageIndex}
              preview={netPreview}
            />
            <div className="export-pane">
              <div className="section-title">
                <FileText size={18} />
                <h2>Export</h2>
              </div>
              {task?.assembly_metadata ? (
                <div className="assembly-grid">
                  <Metric label="Pages" value={String(task.assembly_metadata.page_count)} />
                  <Metric label="Parts" value={String(task.assembly_metadata.part_count)} />
                  <Metric label="Difficulty" value={`${task.assembly_metadata.difficulty_score}/10`} />
                  <Metric label="Build" value={`${task.assembly_metadata.estimated_build_minutes} min`} />
                </div>
              ) : (
                <p className="empty-copy">Assembly metadata appears after the mock export stage.</p>
              )}
              <ArtifactLink artifact={artifactsByKind.export_pdf?.[0]} label="Download PDF" />
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

function NetPreviewPane({
  artifact,
  error,
  onPageChange,
  pageIndex,
  preview,
}: {
  artifact?: ArtifactResponse;
  error: string | null;
  onPageChange: (pageIndex: number) => void;
  pageIndex: number;
  preview: PaperNetPreview | null;
}) {
  const page = preview?.pages[pageIndex] ?? preview?.pages[0];
  return (
    <div className="preview-pane net">
      <div className="section-title">
        <FileJson size={20} />
        <h2>Paper net</h2>
      </div>
      <div className="net-preview-surface">
        {page ? (
          <>
            <div className="page-tabs" aria-label="Paper net pages">
              {preview?.pages.map((netPage, index) => (
                <button
                  className={index === pageIndex ? "is-active" : ""}
                  key={netPage.page}
                  type="button"
                  onClick={() => onPageChange(index)}
                >
                  Page {netPage.page}
                </button>
              ))}
            </div>
            <div className="paper-sheet">
              <div className="sheet-header">
                <strong>Page {page.page}</strong>
                <span>{page.paper_size.toUpperCase()}</span>
              </div>
              <div className="paper-parts">
                {page.parts.map((part, index) => (
                  <div className={`paper-part part-${index + 1}`} key={part.id}>
                    <span>{part.label}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="part-list">
              {page.parts.map((part) => (
                <div className="part-row" key={part.id}>
                  <strong>{part.label}</strong>
                  <span>{part.fold_lines} folds</span>
                  <span>{part.glue_flaps} flaps</span>
                </div>
              ))}
            </div>
          </>
        ) : error ? (
          <p className="empty-copy">{error}</p>
        ) : artifact ? (
          <p className="empty-copy">Loading paper-net preview.</p>
        ) : (
          <p className="empty-copy">Waiting for a completed mock task.</p>
        )}
      </div>
      <ArtifactLink artifact={artifact} label="Open net JSON" />
    </div>
  );
}

function PreviewPane({
  artifact,
  icon,
  title,
  variant,
}: {
  artifact?: ArtifactResponse;
  icon: React.ReactNode;
  title: string;
  variant: "model" | "net";
}) {
  return (
    <div className={`preview-pane ${variant}`}>
      <div className="section-title">
        {icon}
        <h2>{title}</h2>
      </div>
      <div className="preview-surface">
        {artifact ? (
          <>
            <span className="artifact-kind">{artifact.kind.replace("_", " ")}</span>
            <strong>{artifact.mime_type}</strong>
            <small>{formatBytes(artifact.file_size)}</small>
          </>
        ) : (
          <p className="empty-copy">Waiting for a completed mock task.</p>
        )}
      </div>
      <ArtifactLink artifact={artifact} label={variant === "net" ? "Open net JSON" : "Download preview"} />
    </div>
  );
}

function ArtifactLink({ artifact, label }: { artifact?: ArtifactResponse; label: string }) {
  if (!artifact) {
    return (
      <button className="secondary-action" disabled type="button">
        <Download size={17} />
        {label}
      </button>
    );
  }
  return (
    <a className="secondary-action" href={toFrontendDownloadUrl(artifact.download_url)}>
      <Download size={17} />
      {label}
    </a>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const headers = init?.body instanceof FormData ? undefined : { "Content-Type": "application/json" };
  const response = await fetch(url, { ...init, headers });
  if (!response.ok) {
    let message = `Request failed with ${response.status}`;
    try {
      const payload = (await response.json()) as ApiErrorResponse;
      message = `${payload.error.code}: ${payload.error.message}`;
    } catch {
      // Keep the HTTP status message when the response is not JSON.
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

function toFrontendDownloadUrl(downloadUrl: string) {
  return downloadUrl.replace(/^\/api\//, "/backend/");
}

function shortId(id: string) {
  return id.slice(0, 8);
}

function formatStatus(status: TaskStatusResponse["status"]) {
  return status.replace("_", " ");
}

function formatBytes(bytes: number | null) {
  if (!bytes) {
    return "size pending";
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  return `${Math.round(bytes / 1024)} KB`;
}
