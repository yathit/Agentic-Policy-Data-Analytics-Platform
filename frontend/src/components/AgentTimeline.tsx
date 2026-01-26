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
};

function formatTime(ts: string): string {
  const date = new Date(ts);
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
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

          return (
            <div key={index} className="relative pl-10">
              {/* Timeline dot */}
              <div
                className={`absolute left-2.5 w-3 h-3 rounded-full ${agent.color} ring-4 ring-white`}
              />

              <div className="bg-white border rounded-lg p-4 shadow-sm">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs font-medium px-2 py-0.5 rounded ${agent.color} text-white`}
                    >
                      {agent.label}
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
                    <pre className="mt-2 p-2 bg-gray-50 rounded text-xs overflow-x-auto">
                      {JSON.stringify(event.payload, null, 2)}
                    </pre>
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
