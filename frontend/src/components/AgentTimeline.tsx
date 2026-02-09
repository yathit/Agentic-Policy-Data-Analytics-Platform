'use client';

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
function renderPayloadValue(key: string, value: unknown): React.ReactNode {
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
