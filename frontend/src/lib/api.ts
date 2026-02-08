import type {
  Run,
  Artifacts,
  ArtifactsResponse,
  CreateRunRequest,
  CreateRunResponse,
  ApproveRunRequest,
  ExportRequest,
  ExportResponse,
  SourceOption,
} from './types';

// API base URL - can be configured via environment variable
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_VERSION = '/api/v1';

// Generic fetch wrapper with error handling
async function apiFetch<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE}${API_VERSION}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`API Error ${response.status}: ${errorBody}`);
  }

  return response.json();
}

// Create a new run
export async function createRun(
  request: CreateRunRequest
): Promise<CreateRunResponse> {
  return apiFetch<CreateRunResponse>('/runs', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

// Get run by ID
export async function getRun(runId: string): Promise<Run> {
  return apiFetch<Run>(`/runs/${runId}`);
}

// Approve run plan
export async function approveRun(
  runId: string,
  request: ApproveRunRequest
): Promise<{ status: string }> {
  return apiFetch<{ status: string }>(`/runs/${runId}/approve`, {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

// Abort run
export async function abortRun(runId: string): Promise<{ status: string }> {
  return apiFetch<{ status: string }>(`/runs/${runId}/abort`, {
    method: 'POST',
  });
}

// Get run artifacts
export async function getRunArtifacts(runId: string): Promise<Artifacts> {
  const response = await apiFetch<ArtifactsResponse>(`/runs/${runId}/artifacts`);

  // Convert dict-based response to array-based Artifacts
  const tables = response.tables
    ? Object.entries(response.tables).map(([id, data]) => ({
        id,
        title: id,
        columns: data.columns,
        rows: data.rows,
      }))
    : [];

  const charts = response.charts
    ? Object.entries(response.charts).map(([id, data]) => ({
        id,
        title: id,
        data: (data.plotly.data ?? []) as Artifacts['charts'][number]['data'],
        layout: data.plotly.layout as Artifacts['charts'][number]['layout'],
      }))
    : [];

  return {
    tables,
    charts,
    insights: response.insights ?? [],
    datasets: response.datasets ?? [],
    report_md: response.report_md,
  };
}

// Get run history
export async function getRunHistory(limit = 50): Promise<Run[]> {
  const response = await apiFetch<{ items: Run[]; next_cursor: string | null }>(`/runs?limit=${limit}`);
  return response.items;
}

// Export run
export async function exportRun(
  runId: string,
  request: ExportRequest
): Promise<ExportResponse> {
  return apiFetch<ExportResponse>(`/runs/${runId}/export`, {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

// Get available sources
export async function getSources(): Promise<SourceOption[]> {
  try {
    return await apiFetch<SourceOption[]>('/sources');
  } catch {
    // Return default sources if endpoint not available
    return [
      { id: 'data.gov.sg', name: 'Data.gov.sg', recommended: true },
      { id: 'singstat', name: 'SingStat Data', recommended: true },
      { id: 'internal', name: 'IMDA Internal', recommended: false },
    ];
  }
}

// Build WebSocket URL for run events
export function getWebSocketUrl(runId: string): string {
  const wsProtocol = API_BASE.startsWith('https') ? 'wss' : 'ws';
  const wsBase = API_BASE.replace(/^https?/, wsProtocol);
  return `${wsBase}/ws/runs/${runId}`;
}

// Export API base for debugging
export { API_BASE };
