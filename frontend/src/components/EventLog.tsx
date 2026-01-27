'use client';

import { useState } from 'react';
import type { AgentEvent, AgentType, EventPhase } from '@/lib/types';
import AgentTimeline from './AgentTimeline';

interface EventLogProps {
  events: AgentEvent[];
}

const agentOptions: { value: AgentType; label: string }[] = [
  { value: 'coordinator', label: 'Coordinator' },
  { value: 'extraction', label: 'Extraction' },
  { value: 'analytics', label: 'Analytics' },
];

const phaseOptions: { value: EventPhase; label: string }[] = [
  { value: 'reason', label: 'Reasoning' },
  { value: 'action', label: 'Action' },
  { value: 'observation', label: 'Observation' },
  { value: 'decision', label: 'Decision' },
];

export default function EventLog({ events }: EventLogProps) {
  const [selectedAgents, setSelectedAgents] = useState<AgentType[]>([]);
  const [selectedPhases, setSelectedPhases] = useState<EventPhase[]>([]);

  const toggleAgent = (agent: AgentType) => {
    if (selectedAgents.includes(agent)) {
      setSelectedAgents(selectedAgents.filter((a) => a !== agent));
    } else {
      setSelectedAgents([...selectedAgents, agent]);
    }
  };

  const togglePhase = (phase: EventPhase) => {
    if (selectedPhases.includes(phase)) {
      setSelectedPhases(selectedPhases.filter((p) => p !== phase));
    } else {
      setSelectedPhases([...selectedPhases, phase]);
    }
  };

  const clearFilters = () => {
    setSelectedAgents([]);
    setSelectedPhases([]);
  };

  const hasFilters = selectedAgents.length > 0 || selectedPhases.length > 0;

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="bg-gray-50 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-gray-700">Filters</h3>
          {hasFilters && (
            <button
              onClick={clearFilters}
              className="text-xs text-blue-600 hover:text-blue-800"
            >
              Clear all
            </button>
          )}
        </div>

        <div className="space-y-3">
          {/* Agent filters */}
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Agent</label>
            <div className="flex flex-wrap gap-2">
              {agentOptions.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => toggleAgent(opt.value)}
                  className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                    selectedAgents.includes(opt.value)
                      ? 'bg-blue-100 border-blue-300 text-blue-700'
                      : 'bg-white border-gray-200 text-gray-600 hover:border-gray-300'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Phase filters */}
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Phase</label>
            <div className="flex flex-wrap gap-2">
              {phaseOptions.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => togglePhase(opt.value)}
                  className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                    selectedPhases.includes(opt.value)
                      ? 'bg-blue-100 border-blue-300 text-blue-700'
                      : 'bg-white border-gray-200 text-gray-600 hover:border-gray-300'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Event count */}
      <div className="text-sm text-gray-600">
        Showing {events.length} event{events.length !== 1 ? 's' : ''}
        {hasFilters && ' (filtered)'}
      </div>

      {/* Timeline */}
      <div className="max-h-[600px] overflow-y-auto pr-2">
        <AgentTimeline
          events={events}
          filters={{
            agents: selectedAgents.length > 0 ? selectedAgents : undefined,
            phases: selectedPhases.length > 0 ? selectedPhases : undefined,
          }}
        />
      </div>
    </div>
  );
}
