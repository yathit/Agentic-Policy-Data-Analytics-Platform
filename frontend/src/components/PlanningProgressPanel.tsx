'use client';

import { useMemo } from 'react';
import type { AgentEvent } from '@/lib/types';

interface PlanningProgressPanelProps {
  events: AgentEvent[];
  startedAt?: string;
}

interface PlanningStage {
  key: string;
  label: string;
  description: string;
}

const PLANNING_STAGES: PlanningStage[] = [
  { key: 'planning_started', label: 'Starting', description: 'Initializing plan generation' },
  { key: 'intent_parsing_started', label: 'Parsing Intent', description: 'Understanding your query' },
  { key: 'intent_parsing_completed', label: 'Intent Parsed', description: 'Query understood' },
  { key: 'discovery_started', label: 'Discovering Datasets', description: 'Searching data sources' },
  { key: 'discovery_completed', label: 'Discovery Complete', description: 'Found candidate datasets' },
  { key: 'ranking_started', label: 'Ranking Datasets', description: 'Evaluating relevance' },
  { key: 'ranking_completed', label: 'Ranking Complete', description: 'Selected best datasets' },
  { key: 'plan_assembly_started', label: 'Assembling Plan', description: 'Building execution steps' },
  { key: 'plan_ready', label: 'Plan Ready', description: 'Awaiting your approval' },
];

export default function PlanningProgressPanel({
  events,
  startedAt,
}: PlanningProgressPanelProps) {
  // Extract planning progress from events
  const { currentStage, progressPercent, latestMessage, elapsedSeconds, sourcesInfo } = useMemo(() => {
    let stage = 'planning_started';
    let progress = 0;
    let message = 'Starting plan generation...';
    let sourcesCompleted = 0;
    let sourcesTotal = 0;
    let candidatesSeen = 0;

    // Find the latest planning event
    for (const event of events) {
      const payload = event.payload || {};
      if (payload.stage) {
        stage = payload.stage as string;
        message = event.message;
      }
      if (typeof payload.progress_percent === 'number') {
        progress = payload.progress_percent as number;
      }
      if (typeof payload.sources_completed === 'number') {
        sourcesCompleted = payload.sources_completed as number;
      }
      if (typeof payload.sources_total === 'number') {
        sourcesTotal = payload.sources_total as number;
      }
      if (typeof payload.candidates_seen === 'number') {
        candidatesSeen = payload.candidates_seen as number;
      }
    }

    // Calculate elapsed time
    let elapsed = 0;
    if (startedAt) {
      elapsed = Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000);
    }

    return {
      currentStage: stage,
      progressPercent: progress,
      latestMessage: message,
      elapsedSeconds: elapsed,
      sourcesInfo: { completed: sourcesCompleted, total: sourcesTotal, candidates: candidatesSeen },
    };
  }, [events, startedAt]);

  // Find current stage index
  const currentStageIndex = PLANNING_STAGES.findIndex((s) => s.key === currentStage);
  const activeStageIndex = currentStageIndex >= 0 ? currentStageIndex : 0;

  return (
    <div className="bg-white rounded-lg border border-indigo-200 p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-indigo-100 rounded-full flex items-center justify-center">
            <svg
              className="w-5 h-5 text-indigo-600 animate-spin"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Building Your Plan</h2>
            <p className="text-sm text-gray-500">{latestMessage}</p>
          </div>
        </div>
        <div className="text-right">
          <span className="text-2xl font-bold text-indigo-600">{progressPercent}%</span>
          {elapsedSeconds > 0 && (
            <p className="text-xs text-gray-500">{elapsedSeconds}s elapsed</p>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="w-full bg-gray-200 rounded-full h-2 mb-6">
        <div
          className="bg-indigo-600 h-2 rounded-full transition-all duration-500"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      {/* Stage indicators */}
      <div className="space-y-2">
        {PLANNING_STAGES.slice(0, 5).map((stage, idx) => {
          const isCompleted = idx < activeStageIndex;
          const isActive = idx === activeStageIndex;
          const isPending = idx > activeStageIndex;

          // Skip some stages for cleaner UI
          if (stage.key === 'intent_parsing_completed' || stage.key === 'ranking_completed') {
            return null;
          }

          return (
            <div
              key={stage.key}
              className={`flex items-center gap-3 text-sm ${
                isPending ? 'text-gray-400' : 'text-gray-700'
              }`}
            >
              {isCompleted && (
                <span className="w-5 h-5 bg-green-100 text-green-600 rounded-full flex items-center justify-center">
                  <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                    <path
                      fillRule="evenodd"
                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                      clipRule="evenodd"
                    />
                  </svg>
                </span>
              )}
              {isActive && (
                <span className="w-5 h-5 bg-indigo-100 text-indigo-600 rounded-full flex items-center justify-center">
                  <span className="w-2 h-2 bg-indigo-600 rounded-full animate-pulse" />
                </span>
              )}
              {isPending && (
                <span className="w-5 h-5 bg-gray-100 text-gray-400 rounded-full flex items-center justify-center">
                  <span className="w-2 h-2 bg-gray-300 rounded-full" />
                </span>
              )}
              <span className={isActive ? 'font-medium' : ''}>{stage.label}</span>
              {isActive && stage.key.includes('discovery') && sourcesInfo.total > 0 && (
                <span className="text-xs text-gray-500">
                  ({sourcesInfo.completed}/{sourcesInfo.total} sources)
                </span>
              )}
              {isActive && sourcesInfo.candidates > 0 && (
                <span className="text-xs text-gray-500">
                  ({sourcesInfo.candidates} datasets found)
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Skeleton placeholders for plan */}
      <div className="mt-6 pt-4 border-t border-gray-100">
        <p className="text-xs text-gray-400 mb-3">Plan preview will appear here</p>
        <div className="space-y-2">
          <div className="h-4 bg-gray-100 rounded animate-pulse w-3/4" />
          <div className="h-4 bg-gray-100 rounded animate-pulse w-1/2" />
          <div className="h-4 bg-gray-100 rounded animate-pulse w-2/3" />
        </div>
      </div>
    </div>
  );
}
