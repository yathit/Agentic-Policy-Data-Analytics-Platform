'use client';

import type { AgentEvent, AgentType } from '@/lib/types';

interface AgentActivityStatusProps {
  events: AgentEvent[];
  runStatus: string;
  wsStatus: 'connecting' | 'connected' | 'disconnected' | 'error';
}

const agentConfig: Record<AgentType, { label: string; color: string; bgColor: string }> = {
  coordinator: {
    label: 'Coordinator',
    color: 'text-indigo-700',
    bgColor: 'bg-indigo-100',
  },
  extraction: {
    label: 'Extraction',
    color: 'text-teal-700',
    bgColor: 'bg-teal-100',
  },
  analytics: {
    label: 'Analytics',
    color: 'text-amber-700',
    bgColor: 'bg-amber-100',
  },
  report: {
    label: 'Report',
    color: 'text-rose-700',
    bgColor: 'bg-rose-100',
  },
};

export default function AgentActivityStatus({
  events,
  runStatus,
  wsStatus,
}: AgentActivityStatusProps) {
  const isRunning = runStatus === 'running' || runStatus === 'queued';
  const latestEvent = events.length > 0 ? events[events.length - 1] : null;
  const activeAgent = latestEvent?.agent as AgentType | undefined;
  const agentMeta = activeAgent ? agentConfig[activeAgent] : null;

  if (!isRunning && runStatus !== 'awaiting_approval') {
    return null;
  }

  return (
    <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-4 mb-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Animated pulse indicator */}
          {isRunning && (
            <div className="relative">
              <span className="flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-blue-500"></span>
              </span>
            </div>
          )}

          <div>
            <div className="flex items-center gap-2">
              <span className="font-medium text-gray-900">
                {runStatus === 'queued' && 'Waiting to start...'}
                {runStatus === 'running' && 'Processing'}
                {runStatus === 'awaiting_approval' && 'Awaiting your approval'}
              </span>

              {/* Current agent badge */}
              {isRunning && agentMeta && (
                <span className={`text-xs font-medium px-2 py-0.5 rounded ${agentMeta.bgColor} ${agentMeta.color}`}>
                  {agentMeta.label}
                </span>
              )}
            </div>

            {/* Latest action */}
            {isRunning && latestEvent && (
              <p className="text-sm text-gray-600 mt-1">
                {latestEvent.message}
              </p>
            )}
          </div>
        </div>

        {/* Connection status */}
        <div className="flex items-center gap-2 text-xs">
          {wsStatus === 'connected' && (
            <span className="flex items-center gap-1 text-green-600">
              <span className="w-2 h-2 bg-green-500 rounded-full"></span>
              Live
            </span>
          )}
          {wsStatus === 'connecting' && (
            <span className="flex items-center gap-1 text-yellow-600">
              <span className="w-2 h-2 bg-yellow-500 rounded-full animate-pulse"></span>
              Connecting
            </span>
          )}
          {wsStatus === 'disconnected' && (
            <span className="flex items-center gap-1 text-gray-500">
              <span className="w-2 h-2 bg-gray-400 rounded-full"></span>
              Polling
            </span>
          )}
          {wsStatus === 'error' && (
            <span className="flex items-center gap-1 text-red-500">
              <span className="w-2 h-2 bg-red-500 rounded-full"></span>
              Error
            </span>
          )}
        </div>
      </div>

      {/* Progress steps for running status */}
      {isRunning && (
        <div className="mt-4 flex items-center gap-2">
          {(['coordinator', 'extraction', 'analytics', 'report'] as AgentType[]).map((agent, idx) => {
            const config = agentConfig[agent];
            const agentEvents = events.filter(e => e.agent === agent);
            const hasStarted = agentEvents.length > 0;
            const isActive = activeAgent === agent;
            const isComplete = hasStarted && !isActive && events.some(
              (e, i) => e.agent === agent && events.slice(i + 1).some(later => later.agent !== agent)
            );

            return (
              <div key={agent} className="flex items-center">
                <div
                  className={`
                    flex items-center justify-center w-8 h-8 rounded-full text-xs font-medium
                    transition-all duration-300
                    ${isActive ? `${config.bgColor} ${config.color} ring-2 ring-offset-2 ring-blue-400` : ''}
                    ${isComplete ? 'bg-green-100 text-green-700' : ''}
                    ${!hasStarted && !isActive ? 'bg-gray-100 text-gray-400' : ''}
                  `}
                >
                  {isComplete ? '✓' : idx + 1}
                </div>
                {idx < 3 && (
                  <div className={`w-8 h-0.5 ${hasStarted ? 'bg-blue-300' : 'bg-gray-200'}`} />
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
