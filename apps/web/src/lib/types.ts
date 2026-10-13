export const statuses = [
  "CREATED",
  "UPLOADING",
  "QUEUED",
  "PROCESSING",
  "COMPLETED",
  "FAILED",
  "CANCELLED",
] as const;
export type Status = (typeof statuses)[number];
export interface JobEvent {
  timestamp: string;
  status: Status;
  attempt?: number;
}
export interface Job {
  job_id: string;
  name: string;
  filename: string;
  size: number;
  status: Status;
  created_at: string;
  updated_at: string;
  attempts: number;
  row_count?: number;
  duration_ms?: number;
  error_count?: number;
  error_code?: string;
  history?: JobEvent[];
  required_columns: string[];
  numeric_columns: string[];
}
export interface JobInput {
  name: string;
  filename: string;
  size: number;
  required_columns: string[];
  numeric_columns: string[];
}
export interface JobPage {
  items: Job[];
  cursor: string | null;
}
export interface Metrics {
  counts: Partial<Record<Status, number>>;
  sample_size: number;
  scope: string;
  queue: Record<string, string>;
  telemetry_source: string;
  queue_scope: string;
  has_more: boolean;
}
