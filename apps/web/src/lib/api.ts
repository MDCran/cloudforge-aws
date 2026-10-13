import { mode, token } from "./auth";
import { demoCreate, demoJobs, demoList } from "./demo";
import type { Job, JobInput, JobPage, Metrics } from "./types";
const base = import.meta.env.VITE_API_URL || "http://localhost:8000";
export async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const access = await token();
  const response = await fetch(`${base}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(access ? { Authorization: `Bearer ${access}` } : {}),
      ...init.headers,
    },
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      data.error?.message || `Request failed (${response.status})`,
    );
  return data as T;
}
export const api = {
  jobs: (status?: string, cursor?: string): Promise<JobPage> =>
    mode === "demo"
      ? Promise.resolve(demoList(status))
      : request(
          `/v1/jobs?${new URLSearchParams({ ...(status ? { status } : {}), ...(cursor ? { cursor } : {}), limit: "100" })}`,
        ),
  job: (id: string): Promise<Job> =>
    mode === "demo"
      ? Promise.resolve({ ...demoJobs.find((j) => j.job_id === id)! })
      : request(`/v1/jobs/${id}`),
  cancel: async (id: string): Promise<Job> => {
    if (mode !== "demo")
      return request(`/v1/jobs/${id}/cancel`, { method: "POST" });
    const job = demoJobs.find((j) => j.job_id === id)!;
    if (!["CREATED", "UPLOADING", "QUEUED"].includes(job.status))
      throw new Error("This job cannot be cancelled");
    job.status = "CANCELLED";
    return { ...job };
  },
  submit: async (input: JobInput, file: File, key: string): Promise<Job> => {
    if (mode === "demo") {
      const job = demoCreate(input);
      job.status = "QUEUED";
      return { ...job };
    }
    const job = await request<Job>("/v1/jobs", {
      method: "POST",
      body: JSON.stringify(input),
      headers: { "Idempotency-Key": key },
    });
    const upload = await request<{
      url: string;
      fields: Record<string, string>;
    }>("/v1/uploads/presign", {
      method: "POST",
      body: JSON.stringify({ job_id: job.job_id }),
    });
    const form = new FormData();
    Object.entries(upload.fields).forEach(([k, v]) => form.append(k, v));
    form.append("file", file);
    const result = await fetch(upload.url, { method: "POST", body: form });
    if (!result.ok)
      throw new Error(
        "Upload failed. Retry with the same file to reuse this job.",
      );
    return job;
  },
  result: async (id: string): Promise<string> => {
    if (mode !== "demo")
      return (await request<{ url: string }>(`/v1/jobs/${id}/result`)).url;
    const job = demoJobs.find((j) => j.job_id === id)!;
    const blob = new Blob(
      [
        JSON.stringify(
          {
            synthetic: true,
            schema_version: 1,
            row_count: job.row_count,
            validation_error_count: job.error_count,
          },
          null,
          2,
        ),
      ],
      { type: "application/json" },
    );
    return URL.createObjectURL(blob);
  },
  health: (): Promise<{ status: string; service: string }> =>
    mode === "demo"
      ? Promise.resolve({ status: "simulated", service: "cloudforge" })
      : request("/health"),
  metrics: (): Promise<Metrics> =>
    mode === "demo"
      ? Promise.resolve({
          counts: Object.fromEntries(
            ["COMPLETED", "FAILED", "QUEUED", "PROCESSING"].map((s) => [
              s,
              demoJobs.filter((j) => j.status === s).length,
            ]),
          ),
          sample_size: demoJobs.length,
          scope: "synthetic_dataset",
          queue: {
            ApproximateNumberOfMessages: "1",
            ApproximateNumberOfMessagesNotVisible: "1",
          },
          telemetry_source: "Synthetic demo",
          queue_scope: "synthetic",
          has_more: false,
        })
      : request("/v1/metrics/summary"),
};
