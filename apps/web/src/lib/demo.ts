import type { Job, JobInput, JobPage, Status } from "./types";

const names = [
  "Quarterly revenue",
  "Customer directory",
  "Regional orders",
  "Inventory snapshot",
  "Supplier export",
  "October invoices",
  "Account reconciliation",
  "Product catalog",
];
export const demoJobs: Job[] = names.map((name, i) => {
  const created = new Date(Date.UTC(2026, 9, 12 - i, 16, 42));
  const status: Status = [
    "COMPLETED",
    "PROCESSING",
    "COMPLETED",
    "FAILED",
    "QUEUED",
    "COMPLETED",
    "COMPLETED",
    "CANCELLED",
  ][i] as Status;
  return {
    job_id: `c0f00000-0000-4000-8000-${String(i + 1).padStart(12, "0")}`,
    name,
    filename: `${name.toLowerCase().replaceAll(" ", "_")}.csv`,
    size: 12400 + i * 4650,
    status,
    created_at: created.toISOString(),
    updated_at: created.toISOString(),
    attempts: status === "FAILED" ? 5 : 1,
    row_count: status === "COMPLETED" ? 842 + i * 137 : undefined,
    duration_ms: status === "COMPLETED" ? 1380 + i * 216 : undefined,
    error_count: i === 2 ? 14 : 0,
    error_code: status === "FAILED" ? "MISSING_COLUMNS" : undefined,
    required_columns: ["customer"],
    numeric_columns: ["amount"],
    history: [
      { timestamp: created.toISOString(), status: "CREATED" },
      { timestamp: created.toISOString(), status: "UPLOADING" },
      { timestamp: created.toISOString(), status: "QUEUED" },
      ...(status !== "QUEUED" && status !== "CANCELLED"
        ? [{ timestamp: created.toISOString(), status: "PROCESSING" as Status }]
        : []),
      ...(status !== "QUEUED" && status !== "PROCESSING"
        ? [{ timestamp: created.toISOString(), status }]
        : []),
    ],
  };
});
export function demoList(status?: string): JobPage {
  return {
    items: demoJobs.filter((j) => !status || j.status === status),
    cursor: null,
  };
}
export function demoCreate(input: JobInput): Job {
  const job: Job = {
    ...input,
    job_id: crypto.randomUUID(),
    status: "CREATED",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    attempts: 0,
    history: [],
  };
  demoJobs.unshift(job);
  return job;
}
