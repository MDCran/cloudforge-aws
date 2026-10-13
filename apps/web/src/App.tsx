import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  Activity,
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronRight,
  CircleHelp,
  Clock3,
  Cloud,
  Database,
  FileJson,
  FileSpreadsheet,
  FolderOpen,
  GitBranch,
  Github,
  History,
  Layers3,
  LayoutDashboard,
  LoaderCircle,
  Moon,
  Plus,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  Sun,
  UploadCloud,
  XCircle,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { toast } from "sonner";
import { Button } from "./components/ui/button";
import { api } from "./lib/api";
import { manager, mode, signOut } from "./lib/auth";
import { statuses, type Job, type Status } from "./lib/types";

type Page =
  | "overview"
  | "jobs"
  | "upload"
  | "history"
  | "files"
  | "health"
  | "monitoring"
  | "settings"
  | "detail";
const navigation = [
  { page: "overview", label: "Overview", icon: LayoutDashboard },
  { page: "jobs", label: "Processing jobs", icon: Layers3 },
  { page: "upload", label: "New job", icon: UploadCloud },
  { page: "history", label: "Processing history", icon: History },
  { page: "files", label: "Files & results", icon: FolderOpen },
  { page: "health", label: "System health", icon: Activity },
  { page: "monitoring", label: "Monitoring", icon: GitBranch },
  { page: "settings", label: "Settings", icon: Settings2 },
] as const;
const cancellable = new Set<Status>(["CREATED", "UPLOADING", "QUEUED"]);
const label = (status: string) =>
  status.charAt(0) + status.slice(1).toLowerCase();
const date = (value: string) =>
  new Date(value).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
const bytes = (value: number) =>
  value < 1024 * 1024
    ? `${(value / 1024).toFixed(1)} KB`
    : `${(value / 1024 / 1024).toFixed(1)} MB`;
let callback:
  | ReturnType<NonNullable<typeof manager>["signinRedirectCallback"]>
  | undefined;

function StatusBadge({ status }: { status: Status }) {
  return (
    <span className={`status status-${status.toLowerCase()}`}>
      <span />
      {label(status)}
    </span>
  );
}
function ErrorBox({ error }: { error: Error | null }) {
  return error ? (
    <div role="alert" className="error-box">
      <XCircle size={18} />
      {error.message}
    </div>
  ) : null;
}
function Empty({ title, description }: { title: string; description: string }) {
  return (
    <div className="empty">
      <FolderOpen size={30} />
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}

export function App() {
  const [page, setPage] = useState<Page>("overview");
  const [selected, setSelected] = useState<string>("");
  const [filter, setFilter] = useState("");
  const [search, setSearch] = useState("");
  const [dark, setDark] = useState(
    localStorage.getItem("cloudforge-theme") === "dark",
  );
  const [authenticated, setAuthenticated] = useState(mode !== "aws");
  const [authError, setAuthError] = useState<Error | null>(null);
  const queryClient = useQueryClient();
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("cloudforge-theme", dark ? "dark" : "light");
  }, [dark]);
  useEffect(() => {
    if (mode !== "aws") return;
    if (!manager) {
      setAuthError(
        new Error(
          "Configure the Cognito environment settings to connect to AWS.",
        ),
      );
      return;
    }
    let active = true;
    const init = async () => {
      try {
        if (location.pathname === "/callback") {
          callback ??= manager!.signinRedirectCallback();
          await callback;
          window.history.replaceState({}, "", "/");
        }
        const user = await manager!.getUser();
        if (active) setAuthenticated(Boolean(user && !user.expired));
      } catch (e) {
        if (active)
          setAuthError(e instanceof Error ? e : new Error("Sign-in failed"));
      }
    };
    void init();
    return () => {
      active = false;
    };
  }, []);
  const jobsQuery = useInfiniteQuery({
    queryKey: ["jobs", filter],
    initialPageParam: "",
    queryFn: ({ pageParam }) =>
      api.jobs(filter || undefined, pageParam || undefined),
    getNextPageParam: (last) => last.cursor || undefined,
    enabled: authenticated,
    refetchInterval: mode === "demo" ? false : 5000,
  });
  const jobs = useMemo(
    () => jobsQuery.data?.pages.flatMap((p) => p.items) || [],
    [jobsQuery.data],
  );
  const shown = jobs.filter((j) =>
    `${j.name} ${j.filename} ${j.job_id}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  const detail = useQuery({
    queryKey: ["job", selected],
    queryFn: () => api.job(selected),
    enabled: authenticated && !!selected && page === "detail",
    refetchInterval: mode === "demo" ? false : 3000,
  });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 30000,
  });
  const metrics = useQuery({
    queryKey: ["metrics"],
    queryFn: api.metrics,
    enabled: authenticated && (page === "health" || page === "monitoring"),
    refetchInterval: 10000,
  });
  const cancel = useMutation({
    mutationFn: api.cancel,
    onSuccess: () => {
      toast.success("Job cancelled");
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["job"] });
    },
    onError: (error: Error) => toast.error(error.message),
  });
  const open = (job: Job) => {
    setSelected(job.job_id);
    setPage("detail");
  };
  const download = async (job: Job) => {
    try {
      const url = await api.result(job.job_id);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${job.name}-report.json`;
      anchor.rel = "noopener";
      anchor.click();
      if (url.startsWith("blob:"))
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Download failed");
    }
  };
  const title =
    page === "detail"
      ? "Job details"
      : navigation.find((n) => n.page === page)?.label || "Overview";
  const complete = jobs.filter((j) => j.status === "COMPLETED");
  const active = jobs.filter((j) =>
    ["QUEUED", "PROCESSING", "UPLOADING"].includes(j.status),
  );
  const failed = jobs.filter((j) => j.status === "FAILED");
  const trend = useMemo(() => {
    const buckets = new Map<
      string,
      { day: string; completed: number; failed: number }
    >();
    jobs
      .toSorted((a, b) => a.created_at.localeCompare(b.created_at))
      .forEach((job) => {
        const day = job.created_at.slice(0, 10);
        const bucket = buckets.get(day) || { day, completed: 0, failed: 0 };
        if (job.status === "COMPLETED") bucket.completed++;
        if (job.status === "FAILED") bucket.failed++;
        buckets.set(day, bucket);
      });
    return [...buckets.values()].slice(-14);
  }, [jobs]);
  const table = (items: Job[]) => (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Job name</th>
            <th>Status</th>
            <th>Rows processed</th>
            <th>Created</th>
            <th aria-label="Actions" />
          </tr>
        </thead>
        <tbody>
          {items.map((job) => (
            <tr key={job.job_id}>
              <td>
                <button className="job-name" onClick={() => open(job)}>
                  <span className="file-icon">
                    <FileSpreadsheet size={19} />
                  </span>
                  <span>
                    <strong>{job.name}</strong>
                    <small>{job.filename}</small>
                  </span>
                </button>
              </td>
              <td>
                <StatusBadge status={job.status} />
              </td>
              <td className="number">
                {job.row_count?.toLocaleString() || "—"}
              </td>
              <td className="muted nowrap">{date(job.created_at)}</td>
              <td>
                <button
                  className="icon-link"
                  aria-label={`View ${job.name}`}
                  onClick={() => open(job)}
                >
                  <ArrowUpRight size={18} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
  return (
    <div className="workspace">
      <a className="skip-link" href="#content">
        Skip to content
      </a>
      <aside className="sidebar">
        <a className="brand" href="#" onClick={() => setPage("overview")}>
          <span className="brand-mark">
            <Layers3 size={22} />
          </span>
          cloudforge<span className="brand-dot">.</span>
        </a>
        <div className="workspace-switch">
          <span className="workspace-cloud">
            <Cloud size={19} />
          </span>
          <div>
            <strong>AWS workspace</strong>
            <small>Serverless infrastructure</small>
          </div>
          <span className="env-pill">
            {mode === "aws" ? import.meta.env.VITE_ENVIRONMENT || "dev" : mode}
          </span>
        </div>
        <p className="nav-caption">WORKSPACE</p>
        <nav aria-label="Main navigation">
          {navigation.map(({ page: navPage, label: navLabel, icon: Icon }) => (
            <button
              key={navPage}
              className={`nav-item ${page === navPage || (page === "detail" && navPage === "jobs") ? "active" : ""}`}
              onClick={() => {
                setPage(navPage);
                setFilter("");
                setSearch("");
              }}
            >
              <Icon size={19} />
              {navLabel}
              {navPage === "jobs" && (
                <span className="nav-count">{jobs.length}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="architecture-note">
            <ShieldCheck size={19} />
            <strong>Built for reliable work</strong>
            <p>
              Private storage. Scoped access.
              <br />
              Recoverable processing.
            </p>
            <a
              href="https://github.com/MDCran/cloudforge-aws/blob/main/ARCHITECTURE.md"
              target="_blank"
              rel="noreferrer"
            >
              Explore the architecture <ArrowUpRight size={14} />
            </a>
          </div>
          <a
            className="docs-link"
            href="https://github.com/MDCran/cloudforge-aws"
            target="_blank"
            rel="noreferrer"
          >
            <CircleHelp size={18} />
            Documentation <ArrowUpRight size={15} />
          </a>
          <div className="profile">
            <span className="avatar">
              <Cloud size={18} />
            </span>
            <div>
              <strong>
                {mode === "aws" ? "Cloud workspace" : "Portfolio workspace"}
              </strong>
              <small>
                {mode === "demo"
                  ? "Synthetic demonstration"
                  : mode === "local"
                    ? "Local simulator"
                    : "Cognito authentication"}
              </small>
            </div>
          </div>
        </div>
      </aside>
      <div className="main-column">
        <header className="topbar">
          <div className="breadcrumb">
            <Cloud size={16} />
            <ChevronRight size={14} />
            <span>Workspace</span>
            <ChevronRight size={14} />
            <strong>{title}</strong>
          </div>
          <div className="topbar-actions">
            <a
              href="https://github.com/MDCran/cloudforge-aws"
              aria-label="GitHub repository"
              target="_blank"
              rel="noreferrer"
            >
              <Github size={19} />
            </a>
            <button
              onClick={() => setDark(!dark)}
              aria-label={dark ? "Use light theme" : "Use dark theme"}
            >
              {dark ? <Sun size={19} /> : <Moon size={19} />}
            </button>
            <span className="topbar-status">
              <span />
              {health.isError
                ? "API unreachable"
                : health.data
                  ? mode === "demo"
                    ? "Demo workspace"
                    : "API reachable"
                  : "Checking API"}
            </span>
          </div>
        </header>
        {mode !== "aws" && (
          <div className="mode-banner">
            <span className="mode-tag">{mode.toUpperCase()}</span>
            {mode === "demo"
              ? "You’re exploring synthetic sample data. No AWS resources are connected."
              : "Local simulation · in-memory AWS services · data resets when the API restarts."}
            <a
              href="https://github.com/MDCran/cloudforge-aws/blob/main/DEPLOYMENT.md"
              target="_blank"
              rel="noreferrer"
            >
              Connect AWS <ArrowUpRight size={13} />
            </a>
          </div>
        )}
        <main id="content">
          <div className="page-heading">
            <div>
              <p className="eyebrow">
                CLOUDFORGE /{" "}
                {page === "overview" ? "OPERATIONS" : title.toUpperCase()}
              </p>
              <h1>{page === "overview" ? "Platform overview" : title}</h1>
              <p>
                {page === "overview"
                  ? "Track your workloads. Understand your data. Keep things moving."
                  : page === "upload"
                    ? "Turn a CSV file into a structured validation report."
                    : "A closer look at your processing workspace."}
              </p>
            </div>
            <div className="heading-actions">
              <Button
                variant="outline"
                onClick={() => {
                  void queryClient.invalidateQueries();
                  toast.success("Workspace refreshed");
                }}
              >
                <RefreshCw size={16} />
                Refresh
              </Button>
              <Button onClick={() => setPage("upload")}>
                <Plus size={17} />
                New job
              </Button>
            </div>
          </div>
          <ErrorBox error={authError} />
          {!authenticated && mode === "aws" ? (
            <div className="panel sign-in">
              <ShieldCheck size={36} />
              <h2>Sign in to your workspace</h2>
              <p>
                Use your CloudForge Cognito account to manage processing jobs.
              </p>
              <Button
                disabled={!manager}
                onClick={() => void manager?.signinRedirect()}
              >
                Sign in securely <ArrowRight size={16} />
              </Button>
            </div>
          ) : (
            <>
              <ErrorBox error={jobsQuery.error} />
              {jobsQuery.isPending ? (
                <div aria-label="Loading jobs" className="skeleton-grid">
                  {[1, 2, 3, 4].map((i) => (
                    <div key={i} className="skeleton" />
                  ))}
                </div>
              ) : (
                <>
                  {page === "overview" && (
                    <>
                      <div className="stat-grid">
                        {[
                          {
                            title: "Total jobs",
                            value: jobs.length.toLocaleString(),
                            detail: "In the loaded job set",
                            icon: Layers3,
                          },
                          {
                            title: "Completed",
                            value: complete.length.toLocaleString(),
                            detail: "Reports ready to download",
                            icon: Check,
                          },
                          {
                            title: "In progress",
                            value: active.length.toLocaleString(),
                            detail: "Uploading, queued or running",
                            icon: Clock3,
                          },
                          {
                            title: "Needs attention",
                            value: failed.length.toLocaleString(),
                            detail: "Failed processing jobs",
                            icon: XCircle,
                          },
                        ].map(
                          (
                            {
                              title: statTitle,
                              value,
                              detail: statDetail,
                              icon: Icon,
                            },
                            i,
                          ) => (
                            <div className="stat-card" key={statTitle}>
                              <div className="stat-top">
                                {statTitle}
                                <span className={`stat-icon stat-icon-${i}`}>
                                  <Icon size={18} />
                                </span>
                              </div>
                              <div className="stat-value">{value}</div>
                              <p>
                                <span className={`stat-dot stat-dot-${i}`} />
                                {statDetail}
                              </p>
                            </div>
                          ),
                        )}
                      </div>
                      <div className="overview-grid">
                        <section className="panel">
                          <div className="panel-header">
                            <div>
                              <h2>
                                Processing activity{" "}
                                <span className="small-badge">
                                  {mode === "demo"
                                    ? "Sample data"
                                    : "Loaded jobs"}
                                </span>
                              </h2>
                              <p>
                                Current outcomes, grouped by job creation date
                              </p>
                            </div>
                            <Activity size={19} className="muted" />
                          </div>
                          <div className="chart-legend">
                            <span>
                              <i className="legend-complete" />
                              Completed
                            </span>
                            <span>
                              <i className="legend-failed" />
                              Failed
                            </span>
                          </div>
                          <div
                            className="chart"
                            role="img"
                            aria-label={`Job outcomes: ${complete.length} completed and ${failed.length} failed in loaded jobs`}
                          >
                            <ResponsiveContainer width="100%" height="100%">
                              <AreaChart
                                data={trend}
                                margin={{
                                  top: 10,
                                  right: 20,
                                  left: -15,
                                  bottom: 0,
                                }}
                              >
                                <defs>
                                  <linearGradient
                                    id="fill"
                                    x1="0"
                                    y1="0"
                                    x2="0"
                                    y2="1"
                                  >
                                    <stop
                                      offset="0%"
                                      stopColor="#5e81ac"
                                      stopOpacity={0.25}
                                    />
                                    <stop
                                      offset="100%"
                                      stopColor="#5e81ac"
                                      stopOpacity={0}
                                    />
                                  </linearGradient>
                                </defs>
                                <CartesianGrid
                                  vertical={false}
                                  strokeDasharray="3 4"
                                  stroke="var(--line)"
                                />
                                <XAxis
                                  dataKey="day"
                                  tick={{ fontSize: 11, fill: "var(--muted)" }}
                                  axisLine={false}
                                  tickLine={false}
                                />
                                <YAxis
                                  allowDecimals={false}
                                  tick={{ fontSize: 11, fill: "var(--muted)" }}
                                  axisLine={false}
                                  tickLine={false}
                                />
                                <Tooltip
                                  contentStyle={{
                                    background: "var(--surface)",
                                    border: "1px solid var(--line)",
                                    borderRadius: 10,
                                  }}
                                />
                                <Area
                                  type="monotone"
                                  dataKey="completed"
                                  stroke="#5e81ac"
                                  fill="url(#fill)"
                                  strokeWidth={2.5}
                                  dot={{ r: 4, fill: "#5e81ac" }}
                                />
                                <Area
                                  type="monotone"
                                  dataKey="failed"
                                  stroke="#bf616a"
                                  fill="transparent"
                                  strokeWidth={2}
                                  dot={{ r: 3, fill: "#bf616a" }}
                                />
                              </AreaChart>
                            </ResponsiveContainer>
                          </div>
                        </section>
                        <section className="pipeline-card">
                          <div className="pipeline-icon">
                            <GitBranch size={25} />
                          </div>
                          <p className="eyebrow">EVENT-DRIVEN BY DESIGN</p>
                          <h2>
                            Small services.
                            <br />
                            Reliable pipelines.
                          </h2>
                          <p>
                            Files move through a decoupled processing pipeline,
                            with retries and a dead-letter queue.
                          </p>
                          <div className="pipeline-steps">
                            {[
                              "S3 upload",
                              "EventBridge",
                              "SQS queue",
                              "Lambda worker",
                            ].map((s, i) => (
                              <div key={s}>
                                <span>{String(i + 1).padStart(2, "0")}</span>
                                {s}
                                <Check size={13} />
                              </div>
                            ))}
                          </div>
                          <button onClick={() => setPage("monitoring")}>
                            Inspect monitoring <ArrowRight size={16} />
                          </button>
                        </section>
                      </div>
                      <section className="panel">
                        <div className="panel-header">
                          <div>
                            <h2>
                              Recent jobs{" "}
                              <span className="small-badge">{jobs.length}</span>
                            </h2>
                            <p>
                              Your latest processing workloads and their status.
                            </p>
                          </div>
                          <button
                            className="text-link"
                            onClick={() => setPage("jobs")}
                          >
                            View all jobs <ArrowRight size={15} />
                          </button>
                        </div>
                        {jobs.length ? (
                          table(jobs.slice(0, 5))
                        ) : (
                          <Empty
                            title="Your first report starts here"
                            description="Create a job and upload a CSV to begin processing."
                          />
                        )}
                        <div className="panel-footer">
                          <span>
                            {mode === "demo"
                              ? "Synthetic demonstration data"
                              : `Showing ${Math.min(jobs.length, 5)} of ${jobs.length} loaded jobs`}
                          </span>
                          <span>
                            <Database size={13} />
                            Owner-scoped records
                          </span>
                        </div>
                      </section>
                    </>
                  )}
                  {(page === "jobs" ||
                    page === "files" ||
                    page === "history") && (
                    <section className="panel">
                      <div className="panel-header">
                        <div>
                          <h2>
                            {page === "files"
                              ? "Uploaded files & reports"
                              : page === "history"
                                ? "Job processing history"
                                : "All processing jobs"}
                          </h2>
                          <p>
                            {page === "history"
                              ? "Open a job to inspect its state transitions and attempts."
                              : "Search the loaded jobs or filter by processing state."}
                          </p>
                        </div>
                        <span className="small-badge">
                          {jobs.length} loaded
                        </span>
                      </div>
                      <div className="table-toolbar">
                        <label className="search">
                          <Search size={17} />
                          <input
                            aria-label="Search jobs"
                            placeholder="Search job name, file or ID…"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                          />
                        </label>
                        <select
                          aria-label="Filter jobs by status"
                          value={filter}
                          onChange={(e) => setFilter(e.target.value)}
                        >
                          <option value="">All statuses</option>
                          {statuses.map((s) => (
                            <option key={s} value={s}>
                              {label(s)}
                            </option>
                          ))}
                        </select>
                      </div>
                      {shown.length ? (
                        page === "files" ? (
                          <div className="files-grid">
                            {shown.map((job) => (
                              <article className="file-card" key={job.job_id}>
                                <FileSpreadsheet size={30} />
                                <h3>{job.filename}</h3>
                                <p>
                                  {bytes(job.size)} · {job.name}
                                </p>
                                <StatusBadge status={job.status} />
                                <div>
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => open(job)}
                                  >
                                    Details
                                  </Button>
                                  <Button
                                    size="sm"
                                    disabled={job.status !== "COMPLETED"}
                                    onClick={() => void download(job)}
                                  >
                                    <ArrowDownToLine size={14} />
                                    Report
                                  </Button>
                                </div>
                              </article>
                            ))}
                          </div>
                        ) : (
                          table(shown)
                        )
                      ) : (
                        <Empty
                          title="No matching jobs"
                          description="Adjust your filters or create a new processing job."
                        />
                      )}
                      <div className="panel-footer">
                        <span>Search covers the loaded records.</span>
                        {jobsQuery.hasNextPage && (
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={jobsQuery.isFetchingNextPage}
                            onClick={() => void jobsQuery.fetchNextPage()}
                          >
                            Load more jobs
                          </Button>
                        )}
                      </div>
                    </section>
                  )}
                  {page === "upload" && <Upload onCreated={open} />}
                  {page === "detail" && (
                    <>
                      <Button variant="ghost" onClick={() => setPage("jobs")}>
                        <ArrowLeft size={16} />
                        Back to jobs
                      </Button>
                      <ErrorBox error={detail.error} />
                      {detail.data && (
                        <div className="detail-grid">
                          <section className="panel detail-panel">
                            <div className="panel-header">
                              <div>
                                <h2>{detail.data.name}</h2>
                                <p className="mono">{detail.data.job_id}</p>
                              </div>
                              <StatusBadge status={detail.data.status} />
                            </div>
                            <dl className="detail-list">
                              <div>
                                <dt>Source file</dt>
                                <dd>{detail.data.filename}</dd>
                              </div>
                              <div>
                                <dt>File size</dt>
                                <dd>{bytes(detail.data.size)}</dd>
                              </div>
                              <div>
                                <dt>Processing attempts</dt>
                                <dd>{detail.data.attempts}</dd>
                              </div>
                              <div>
                                <dt>Rows processed</dt>
                                <dd>
                                  {detail.data.row_count?.toLocaleString() ||
                                    "—"}
                                </dd>
                              </div>
                              <div>
                                <dt>Validation errors</dt>
                                <dd>{detail.data.error_count ?? "—"}</dd>
                              </div>
                              <div>
                                <dt>Processing time</dt>
                                <dd>
                                  {detail.data.duration_ms
                                    ? `${(detail.data.duration_ms / 1000).toFixed(2)} seconds`
                                    : "—"}
                                </dd>
                              </div>
                              <div>
                                <dt>Error code</dt>
                                <dd>{detail.data.error_code || "—"}</dd>
                              </div>
                            </dl>
                            <div className="detail-actions">
                              <Button
                                disabled={detail.data.status !== "COMPLETED"}
                                onClick={() => void download(detail.data!)}
                              >
                                <FileJson size={16} />
                                Download JSON report
                              </Button>
                              <Button
                                variant="outline"
                                disabled={
                                  !cancellable.has(detail.data.status) ||
                                  cancel.isPending
                                }
                                onClick={() => cancel.mutate(selected)}
                              >
                                Cancel job
                              </Button>
                            </div>
                            <p className="fine-print">
                              Cancellation is available before processing
                              begins. Running work cannot be stopped.
                            </p>
                          </section>
                          <section className="panel">
                            <div className="panel-header">
                              <div>
                                <h2>Processing history</h2>
                                <p>Latest 100 recorded state changes</p>
                              </div>
                              <History size={20} />
                            </div>
                            <ol className="timeline">
                              {detail.data.history
                                ?.toReversed()
                                .map((event, i) => (
                                  <li key={`${event.timestamp}-${i}`}>
                                    <span className="timeline-marker" />
                                    <strong>{label(event.status)}</strong>
                                    <small>
                                      {date(event.timestamp)}
                                      {event.attempt
                                        ? ` · Attempt ${event.attempt}`
                                        : ""}
                                    </small>
                                  </li>
                                ))}
                            </ol>
                          </section>
                        </div>
                      )}
                    </>
                  )}
                  {(page === "health" || page === "monitoring") && (
                    <>
                      <div className="health-grid">
                        <section className="panel health-card">
                          <Activity size={25} />
                          <h2>API liveness</h2>
                          <strong
                            className={
                              health.isError ? "danger-text" : "success-text"
                            }
                          >
                            {health.data?.status ||
                              (health.isError ? "Unreachable" : "Checking…")}
                          </strong>
                          <p>
                            Liveness confirms API reachability. It does not
                            certify the entire processing pipeline.
                          </p>
                        </section>
                        <section className="panel health-card">
                          <ShieldCheck size={25} />
                          <h2>Processing guarantees</h2>
                          <strong>At-least-once delivery</strong>
                          <p>
                            Conditional state updates and expiring leases
                            prevent conflicting workers from publishing results.
                          </p>
                        </section>
                      </div>
                      <ErrorBox error={metrics.error} />
                      {metrics.data && (
                        <section className="panel">
                          <div className="panel-header">
                            <div>
                              <h2>Queue & job summary</h2>
                              <p>
                                {metrics.data.telemetry_source} ·{" "}
                                {metrics.data.scope.replaceAll("_", " ")}
                              </p>
                            </div>
                            <span className="small-badge">Operator access</span>
                          </div>
                          <dl className="detail-list">
                            <div>
                              <dt>
                                Waiting messages ({metrics.data.queue_scope})
                              </dt>
                              <dd>
                                {metrics.data.queue.ApproximateNumberOfMessages}
                              </dd>
                            </div>
                            <div>
                              <dt>In-flight messages</dt>
                              <dd>
                                {
                                  metrics.data.queue
                                    .ApproximateNumberOfMessagesNotVisible
                                }
                              </dd>
                            </div>
                            <div>
                              <dt>Jobs in owner sample</dt>
                              <dd>
                                {metrics.data.sample_size}
                                {metrics.data.has_more
                                  ? " (more available)"
                                  : ""}
                              </dd>
                            </div>
                          </dl>
                        </section>
                      )}
                      <section className="panel monitoring-panel">
                        <Cloud size={30} />
                        <div>
                          <h2>CloudWatch is the telemetry source of record</h2>
                          <p>
                            The deployed dashboard tracks HTTP errors, function
                            duration, queue backlog, processing outcomes, and
                            dead-letter messages. SNS delivers configured
                            alarms.
                          </p>
                          <Button variant="outline" asChild>
                            <a
                              href={`https://${import.meta.env.VITE_AWS_REGION || "us-east-1"}.console.aws.amazon.com/cloudwatch/home?region=${import.meta.env.VITE_AWS_REGION || "us-east-1"}#dashboards:name=cloudforge-${import.meta.env.VITE_ENVIRONMENT || "dev"}`}
                              target="_blank"
                              rel="noreferrer"
                            >
                              Open AWS CloudWatch <ArrowUpRight size={15} />
                            </a>
                          </Button>
                        </div>
                      </section>
                    </>
                  )}
                  {page === "settings" && (
                    <section className="panel">
                      <div className="panel-header">
                        <div>
                          <h2>Workspace configuration</h2>
                          <p>
                            Connection settings are configured at build time.
                          </p>
                        </div>
                        <Settings2 size={20} />
                      </div>
                      <dl className="detail-list">
                        <div>
                          <dt>Data mode</dt>
                          <dd className="mode-tag">{mode.toUpperCase()}</dd>
                        </div>
                        <div>
                          <dt>API endpoint</dt>
                          <dd className="mono">
                            {import.meta.env.VITE_API_URL ||
                              "http://localhost:8000"}
                          </dd>
                        </div>
                        <div>
                          <dt>Upload limit</dt>
                          <dd>10 MB / 100,000 rows</dd>
                        </div>
                        <div>
                          <dt>Upload & download URLs</dt>
                          <dd>5-minute expiration</dd>
                        </div>
                        <div>
                          <dt>Authentication</dt>
                          <dd>
                            {mode === "aws"
                              ? "Cognito · Authorization Code + PKCE"
                              : "Simulation only"}
                          </dd>
                        </div>
                        <div>
                          <dt>Theme</dt>
                          <dd>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => setDark(!dark)}
                            >
                              {dark ? "Switch to light" : "Switch to dark"}
                            </Button>
                          </dd>
                        </div>
                      </dl>
                      {mode === "aws" && (
                        <div className="detail-actions">
                          <Button
                            variant="outline"
                            onClick={() => void signOut()}
                          >
                            Sign out
                          </Button>
                        </div>
                      )}
                    </section>
                  )}
                </>
              )}
            </>
          )}
          <footer className="main-footer">
            <span>
              CloudForge <span className="muted">/</span> Serverless
              infrastructure platform
            </span>
            <span>
              <GitBranch size={13} />
              Terraform managed
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}

function Upload({ onCreated }: { onCreated: (job: Job) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [required, setRequired] = useState("");
  const [numeric, setNumeric] = useState("");
  const key = useRef(crypto.randomUUID());
  const queryClient = useQueryClient();
  const submit = useMutation({
    mutationFn: async () => {
      if (!file || !name.trim())
        throw new Error("Choose a CSV and give the job a name.");
      if (
        file.size > 10 * 1024 * 1024 ||
        file.size === 0 ||
        !file.name.toLowerCase().endsWith(".csv")
      )
        throw new Error("Choose a nonempty CSV no larger than 10 MB.");
      const split = (value: string) =>
        value
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean);
      return api.submit(
        {
          name: name.trim(),
          filename: file.name,
          size: file.size,
          required_columns: split(required),
          numeric_columns: split(numeric),
        },
        file,
        key.current,
      );
    },
    onSuccess: (job) => {
      toast.success(
        mode === "demo"
          ? "Synthetic job added to the demo queue"
          : "File uploaded. Processing will begin shortly.",
      );
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
      onCreated(job);
    },
    onError: (error: Error) => toast.error(error.message),
  });
  const changed = () => {
    key.current = crypto.randomUUID();
  };
  const send = (event: FormEvent) => {
    event.preventDefault();
    submit.mutate();
  };
  return (
    <div className="upload-grid">
      <form className="panel upload-form" onSubmit={send}>
        <div className="panel-header">
          <div>
            <h2>Create a processing job</h2>
            <p>
              Validate records, detect duplicates, and summarize numeric data.
            </p>
          </div>
          <FileSpreadsheet size={22} />
        </div>
        <div className="form-body">
          <label className="field">
            Job name
            <input
              required
              maxLength={100}
              placeholder="e.g. October revenue validation"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                changed();
              }}
              disabled={submit.isPending}
            />
          </label>
          <label className="upload-drop">
            <UploadCloud size={30} />
            <strong>{file ? file.name : "Choose a CSV file"}</strong>
            <span>
              {file
                ? bytes(file.size)
                : "UTF-8 CSV · up to 10 MB · 100,000 records"}
            </span>
            <input
              aria-label="CSV file"
              type="file"
              accept=".csv,text/csv"
              disabled={submit.isPending}
              onChange={(e) => {
                setFile(e.target.files?.[0] || null);
                changed();
              }}
            />
          </label>
          <label className="field">
            Required columns <span className="muted">(optional)</span>
            <input
              placeholder="customer, order_id"
              value={required}
              onChange={(e) => {
                setRequired(e.target.value);
                changed();
              }}
              disabled={submit.isPending}
            />
            <small>Comma-separated columns that must contain a value.</small>
          </label>
          <label className="field">
            Numeric columns <span className="muted">(optional)</span>
            <input
              placeholder="amount, quantity"
              value={numeric}
              onChange={(e) => {
                setNumeric(e.target.value);
                changed();
              }}
              disabled={submit.isPending}
            />
            <small>Values in these columns must be finite numbers.</small>
          </label>
          <ErrorBox error={submit.error} />
          <Button type="submit" disabled={submit.isPending}>
            {submit.isPending ? (
              <LoaderCircle size={17} className="spin" />
            ) : (
              <UploadCloud size={17} />
            )}{" "}
            {submit.isPending ? "Uploading…" : "Create job & upload"}
          </Button>
        </div>
      </form>
      <div>
        <section className="panel report-preview">
          <div className="report-icon">
            <FileJson size={25} />
          </div>
          <h2>What’s in your report</h2>
          <p>
            A structured JSON summary, ready to inspect or use in another
            workflow.
          </p>
          {[
            "Row and column counts",
            "Missing-value summaries",
            "Required-field validation",
            "Duplicate row detection",
            "Numeric min, max and mean",
            "Up to 100 validation error samples",
          ].map((item) => (
            <div className="report-feature" key={item}>
              <Check size={16} />
              {item}
            </div>
          ))}
        </section>
        <div className="upload-note">
          <ShieldCheck size={20} />
          <p>
            Files stay private. Upload URLs expire after five minutes and
            restrict the exact object key and file size.
          </p>
        </div>
      </div>
    </div>
  );
}
