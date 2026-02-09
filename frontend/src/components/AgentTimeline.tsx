'use client';

import type { ReactNode } from 'react';
import type { AgentEvent, EventPhase, AgentType } from '@/lib/types';

interface AgentTimelineProps {
  events: AgentEvent[];
  filters?: {
    agents?: AgentType[];
    phases?: EventPhase[];
  };
}

const phaseConfig: Record<EventPhase, { label: string; color: string; icon: string }> = {
  reason: {
    label: 'Reasoning',
    color: 'text-purple-600 bg-purple-100',
    icon: '🧠',
  },
  action: {
    label: 'Action',
    color: 'text-blue-600 bg-blue-100',
    icon: '⚡',
  },
  observation: {
    label: 'Observation',
    color: 'text-green-600 bg-green-100',
    icon: '👁',
  },
  decision: {
    label: 'Decision',
    color: 'text-orange-600 bg-orange-100',
    icon: '✓',
  },
};

const agentConfig: Record<AgentType, { label: string; color: string }> = {
  coordinator: {
    label: 'Coordinator',
    color: 'bg-indigo-500',
  },
  extraction: {
    label: 'Extraction',
    color: 'bg-teal-500',
  },
  analytics: {
    label: 'Analytics',
    color: 'bg-amber-500',
  },
  report: {
    label: 'Report',
    color: 'bg-rose-500',
  },
};

function formatTime(ts: string): string {
  const date = new Date(ts);
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

/**
 * Check if a string is a valid URL.
 */
function isUrl(value: unknown): value is string {
  if (typeof value !== 'string') return false;
  try {
    const url = new URL(value);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}

/**
 * Known URL field names in payloads that should be rendered as links.
 */
const URL_FIELD_NAMES = new Set([
  'source_uri',
  'portal_url',
  'api_endpoint',
  'url',
  'link',
  'href',
]);

/**
 * Render a payload value, converting URLs to clickable links.
 */
function renderPayloadValue(key: string, value: unknown): ReactNode {
  // Check if this is a URL field or looks like a URL
  if (isUrl(value) || (typeof value === 'string' && URL_FIELD_NAMES.has(key))) {
    if (isUrl(value)) {
      return (
        <a
          href={value}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 hover:text-blue-800 underline break-all"
        >
          {value}
        </a>
      );
    }
  }

  // For objects and arrays, return as JSON
  if (typeof value === 'object' && value !== null) {
    return JSON.stringify(value, null, 2);
  }

  // For primitives, return as string
  return String(value);
}

interface SelectedDatasetPreview {
  id: string;
  title: string;
  source: string;
  score?: number;
}

interface ExecutionStepPreview {
  order: number;
  agent: string;
  action: string;
}

function getRunDatasetPath(event: AgentEvent): string | null {
  if (event.agent !== 'extraction' || event.phase !== 'decision' || !event.payload) {
    return null;
  }

  const directPath = event.payload.run_dataset_url;
  if (typeof directPath === 'string' && directPath.trim().length > 0) {
    return directPath;
  }

  const datasetId = event.payload.dataset_id;
  if (typeof datasetId === 'number' || typeof datasetId === 'string') {
    return `/runs/${event.run_id}/datasets/${datasetId}`;
  }

  return null;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function extractSelectedDatasets(payload?: Record<string, unknown>): SelectedDatasetPreview[] {
  if (!payload) return [];

  const parseSources = (sources: unknown): SelectedDatasetPreview[] => {
    if (!Array.isArray(sources)) return [];
    const items: SelectedDatasetPreview[] = [];

    for (const sourceItem of sources) {
      const sourceRecord = asRecord(sourceItem);
      if (!sourceRecord) continue;

      const sourceName = typeof sourceRecord.name === 'string' ? sourceRecord.name : 'unknown';
      const datasets = sourceRecord.datasets;
      if (!Array.isArray(datasets)) continue;

      for (const datasetItem of datasets) {
        const dataset = asRecord(datasetItem);
        if (!dataset) continue;
        const id = typeof dataset.id === 'string' ? dataset.id : '';
        const title = typeof dataset.title === 'string' ? dataset.title : id;
        const rawScore = dataset.relevance_score ?? dataset.score;
        const score = typeof rawScore === 'number' ? rawScore : undefined;

        if (id || title) {
          items.push({ id: id || title, title: title || id, source: sourceName, score });
        }
      }
    }

    return items;
  };

  const direct = parseSources(payload.sources);
  if (direct.length > 0) {
    return direct;
  }

  const plan = asRecord(payload.plan);
  if (plan) {
    return parseSources(plan.sources);
  }

  return [];
}

function extractExecutionSteps(payload?: Record<string, unknown>): ExecutionStepPreview[] {
  if (!payload) return [];

  const direct = payload.execution_steps;
  if (Array.isArray(direct)) {
    const parsed = direct
      .map((item, idx) => {
        const row = asRecord(item);
        if (!row) return null;
        const agent = typeof row.agent === 'string' ? row.agent : '';
        const action = typeof row.action === 'string' ? row.action : '';
        const order = typeof row.order === 'number' ? row.order : idx + 1;
        if (!agent || !action) return null;
        return { order, agent, action };
      })
      .filter((v): v is ExecutionStepPreview => v !== null);
    if (parsed.length > 0) {
      return parsed;
    }
  }

  // Fallback for older events that include only structured plan payload.
  const plan = asRecord(payload.plan);
  if (!plan) return [];
  const hasSources = Array.isArray(plan.sources) && plan.sources.length > 0;
  const hasExtract = Array.isArray(plan.extract_steps) && plan.extract_steps.length > 0;
  const hasAnalysis = Array.isArray(plan.analysis_steps) && plan.analysis_steps.length > 0;
  if (!hasSources && !hasExtract && !hasAnalysis) return [];

  return [
    { order: 1, agent: 'coordinator', action: 'select_sources' },
    { order: 2, agent: 'extraction', action: 'fetch_datasets' },
    { order: 3, agent: 'analytics', action: 'compute_trends' },
  ];
}

/**
 * Render payload with URL fields as clickable links.
 */
function PayloadDisplay({ payload }: { payload: Record<string, unknown> }) {
  const entries = Object.entries(payload);

  // Check if any values are URLs that should be displayed prominently
  const urlEntries = entries.filter(([_key, value]) => isUrl(value));
  const otherEntries = entries.filter(([_key, value]) => !isUrl(value));

  return (
    <div className="space-y-2">
      {/* Render URL fields prominently */}
      {urlEntries.length > 0 && (
        <div className="space-y-1">
          {urlEntries.map(([key, value]) => (
            <div key={key} className="flex items-center gap-2">
              <span className="text-xs text-gray-500 font-medium">{key}:</span>
              {renderPayloadValue(key, value)}
            </div>
          ))}
        </div>
      )}

      {/* Render other fields as JSON */}
      {otherEntries.length > 0 && (
        <pre className="p-2 bg-gray-50 rounded text-xs overflow-x-auto">
          {JSON.stringify(Object.fromEntries(otherEntries), null, 2)}
        </pre>
      )}
    </div>
  );
}

export default function AgentTimeline({ events, filters }: AgentTimelineProps) {
  const filteredEvents = events.filter((event) => {
    if (filters?.agents?.length && !filters.agents.includes(event.agent)) {
      return false;
    }
    if (filters?.phases?.length && !filters.phases.includes(event.phase)) {
      return false;
    }
    return true;
  });

  if (filteredEvents.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <p>No events to display</p>
        {events.length > 0 && filters && (
          <p className="text-sm mt-1">Try adjusting your filters</p>
        )}
      </div>
    );
  }

  return (
    <div className="relative">
      {/* Timeline line */}
      <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gray-200" />

      <div className="space-y-4">
        {filteredEvents.map((event, index) => {
          const phase = phaseConfig[event.phase];
          const agent = agentConfig[event.agent];
          const agentMeta = agent ?? { label: event.agent, color: 'bg-gray-400' };
          const runDatasetPath = getRunDatasetPath(event);
          const selectedDatasets = extractSelectedDatasets(event.payload);
          const executionSteps = extractExecutionSteps(event.payload);

          return (
            <div key={index} className="relative pl-10">
              {/* Timeline dot */}
              <div
                className={`absolute left-2.5 w-3 h-3 rounded-full ${agentMeta.color} ring-4 ring-white`}
              />

              <div className="bg-white border rounded-lg p-4 shadow-sm">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs font-medium px-2 py-0.5 rounded ${agentMeta.color} text-white`}
                    >
                      {agentMeta.label}
                    </span>
                    <span
                      className={`text-xs font-medium px-2 py-0.5 rounded ${phase.color}`}
                    >
                      {phase.icon} {phase.label}
                    </span>
                  </div>
                  <span className="text-xs text-gray-500">
                    {formatTime(event.ts)}
                  </span>
                </div>
                <p className="text-sm text-gray-700">{event.message}</p>
                {runDatasetPath && (
                  <div className="mt-3">
                    <a
                      href={runDatasetPath}
                      className="inline-flex items-center rounded-md border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100"
                    >
                      View data used in this run
                    </a>
                  </div>
                )}
                {selectedDatasets.length > 0 && (
                  <div className="mt-3 rounded-md border border-gray-200 bg-gray-50 p-3">
                    <div className="text-xs font-medium text-gray-700 mb-2">
                      Selected datasets ({selectedDatasets.length})
                    </div>
                    <div className="space-y-1.5">
                      {selectedDatasets.slice(0, 8).map((dataset) => (
                        <div key={`${dataset.source}-${dataset.id}`} className="text-xs text-gray-700">
                          <span className="font-medium">{dataset.source}</span>: {dataset.title}
                          {typeof dataset.score === 'number' && (
                            <span className="text-gray-500"> (score {dataset.score.toFixed(2)})</span>
                          )}
                        </div>
                      ))}
                      {selectedDatasets.length > 8 && (
                        <div className="text-xs text-gray-500">
                          +{selectedDatasets.length - 8} more
                        </div>
                      )}
                    </div>
                  </div>
                )}
                {executionSteps.length > 0 && (
                  <div className="mt-3 rounded-md border border-gray-200 bg-gray-50 p-3">
                    <div className="text-xs font-medium text-gray-700 mb-2">
                      Execution Steps
                    </div>
                    <div className="space-y-2">
                      {executionSteps.map((step) => (
                        <div key={`${step.order}-${step.agent}-${step.action}`} className="text-xs text-gray-800">
                          <div className="font-semibold">{step.order}</div>
                          <div>{step.agent}</div>
                          <div>{step.action}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {event.payload && Object.keys(event.payload).length > 0 && (
                  <details className="mt-2">
                    <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">
                      View payload
                    </summary>
                    <div className="mt-2">
                      <PayloadDisplay payload={event.payload} />
                    </div>
                  </details>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
