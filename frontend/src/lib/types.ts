// Run status types
export type RunStatus =
  | 'queued'
  | 'needs_approval'
  | 'awaiting_approval'
  | 'running'
  | 'completed'
  | 'failed'
  | 'aborted';

// Run object
export interface Run {
  id: string;
  query: string;
  status: RunStatus;
  created_at: string;
  started_at?: string;
  finished_at?: string;
  selected_sources?: string[];
  error_summary?: string;
  plan?: Plan;
}

// Plan step
export interface PlanStep {
  id: string;
  agent: string;
  action: string;
  inputs: Record<string, unknown>;
  requires_approval?: boolean;
  expected_output?: string;
}

// Source rationale
export interface SourceRationale {
  source: string;
  why: string;
}

// Plan object
export interface Plan {
  id: string;
  version: number;
  steps: PlanStep[];
  source_rationale?: SourceRationale[];
  constraints?: {
    allowed_sources?: string[];
    time_range?: {
      start: string;
      end: string;
    };
  };
}

// Event phases (ReAct pattern)
export type EventPhase = 'reason' | 'action' | 'observation' | 'decision';

// Agent types
export type AgentType = 'coordinator' | 'extraction' | 'analytics' | 'report';

// Event object
export interface AgentEvent {
  run_id: string;
  agent: AgentType;
  phase: EventPhase;
  message: string;
  payload?: Record<string, unknown>;
  ts: string;
}

// Insight object
export interface Insight {
  id: string;
  headline: string;
  evidence: {
    value: string | number;
    pointer?: string;
  }[];
  confidence: 'high' | 'medium' | 'low';
  citations: {
    dataset_id: string;
    columns?: string[];
    time_range?: string;
  }[];
}

// Chart data type (compatible with Plotly)
export interface PlotlyData {
  type?: string;
  x?: (string | number)[];
  y?: (string | number)[];
  name?: string;
  [key: string]: unknown;
}

// Chart layout type (compatible with Plotly)
export interface PlotlyLayout {
  title?: string | { text: string };
  xaxis?: { title?: string };
  yaxis?: { title?: string };
  [key: string]: unknown;
}

// Chart spec (Plotly)
export interface ChartSpec {
  id: string;
  title: string;
  data: PlotlyData[];
  layout?: Partial<PlotlyLayout>;
}

// Table data
export interface TableData {
  id: string;
  title: string;
  columns: string[];
  rows: (string | number | null)[][];
}

// Dataset info for provenance
export interface DatasetInfo {
  id: string;
  name: string;
  uri: string;
  retrieved_at: string;
  record_count?: number;
}

// API Artifacts response (what the backend returns)
export interface ArtifactsResponse {
  tables?: Record<string, { columns: string[]; rows: (string | number | null)[][] }>;
  charts?: Record<string, { plotly: Record<string, unknown> }>;
  insights?: Insight[];
  datasets?: DatasetInfo[];
  report_md?: string;
}

// Artifacts object (normalized for UI consumption)
export interface Artifacts {
  tables: TableData[];
  charts: ChartSpec[];
  insights: Insight[];
  datasets: DatasetInfo[];
  report_md?: string;
  report_pdf?: string;
}

// API request/response types
export interface CreateRunRequest {
  query: string;
  requested_sources?: string[];
}

export interface CreateRunResponse {
  run: Run;
  plan: Plan;
}

export interface ApproveRunRequest {
  plan_id: string;
  approved: boolean;
  edits?: {
    time_range?: {
      start: string;
      end: string;
    };
    sources?: string[];
    top_n?: number;
  };
}

export interface ExportRequest {
  format: 'md' | 'pdf';
}

export interface ExportResponse {
  url: string;
}

// Source option for the UI
export interface SourceOption {
  id: string;
  name: string;
  description?: string;
  recommended?: boolean;
}
