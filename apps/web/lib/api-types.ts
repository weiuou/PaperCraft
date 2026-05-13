export type ProjectCategory = "pet" | "bust" | "simple_object";
export type ComplexityLevel = "simple" | "balanced" | "detailed";
export type PaperSize = "a4" | "a3";
export type TextureMode = "plain" | "source_texture" | "print_friendly";
export type BuildDifficultyMode = "easy" | "standard" | "advanced";
export type TaskStatus = "draft" | "queued" | "in_progress" | "completed" | "failed" | "canceled";
export type TaskStage =
  | "upload_validation"
  | "preprocessing"
  | "model_generating"
  | "paperability_optimizing"
  | "decimating"
  | "unfolding"
  | "exporting"
  | "completed";

export type ProjectResponse = {
  project_id: string;
  title: string;
  category: ProjectCategory;
  status: "draft" | "active" | "archived" | "deleted";
  latest_task_id: string | null;
  image_count: number;
  task_count: number;
  created_at: string;
  updated_at: string;
};

export type ImageResponse = {
  image_id: string;
  project_id: string;
  storage_key: string;
  mime_type: string;
  width: number;
  height: number;
  file_size: number;
  sort_order: number;
  created_at: string;
};

export type TaskCreatedResponse = {
  task_id: string;
  project_id: string;
  initial_status: TaskStatus;
  status: TaskStatus;
  stage: TaskStage;
  progress: number;
};

export type CreateTaskRequest = {
  complexity_level: ComplexityLevel;
  target_poly_count: number;
  paper_size: PaperSize;
  texture_mode: TextureMode;
  flap_size: number;
  max_pages: number;
  build_difficulty_mode: BuildDifficultyMode;
  mock_failure_stage?: TaskStage | null;
};

export type ArtifactResponse = {
  artifact_id: string;
  kind: "source_image" | "preprocess_mask" | "preprocess_crop" | "base_mesh" | "repaired_mesh" | "low_poly_mesh" | "net_json" | "net_svg" | "preview_image" | "preview_model" | "export_pdf";
  storage_key: string;
  download_url: string;
  mime_type: string;
  file_size: number | null;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type TaskStatusResponse = {
  task_id: string;
  project_id: string;
  status: TaskStatus;
  stage: TaskStage;
  progress: number;
  error_code: string | null;
  error_message: string | null;
  next_actions: string[];
  artifacts: ArtifactResponse[];
  assembly_metadata: {
    page_count: number;
    part_count: number;
    difficulty_score: number;
    estimated_build_minutes: number;
    metadata: Record<string, unknown>;
  } | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ProjectTaskHistoryResponse = {
  tasks: TaskStatusResponse[];
};

export type ApiErrorResponse = {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
};
