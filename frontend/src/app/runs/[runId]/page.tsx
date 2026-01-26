'use client';

import { useEffect, useState, useCallback, use } from 'react';
import Link from 'next/link';
import { getRun, getRunPlan, getRunArtifacts, approveRun, abortRun } from '@/lib/api';
import { WebSocketClient } from '@/lib/ws';
import type { Run, Plan, Artifacts, AgentEvent } from '@/lib/types';
import RunStatusBadge from '@/components/RunStatusBadge';
import PlanReviewCard from '@/components/PlanReviewCard';
import EventLog from '@/components/EventLog';
import ArtifactsPanel from '@/components/ArtifactsPanel';
import ExportButtons from '@/components/ExportButtons';

interface RunDetailPageProps {
  params: Promise<{ runId: string }>;
}

export default function RunDetailPage({ params }: RunDetailPageProps) {
  const { runId } = use(params);

  const [run, setRun] = useState<Run | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [artifacts, setArtifacts] = useState<Artifacts | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Fetch run data
  const fetchRunData = useCallback(async () => {
    try {
      const runData = await getRun(runId);
      setRun(runData);

      // Fetch plan if available
      if (['needs_approval', 'running', 'completed', 'failed'].includes(runData.status)) {
        try {
          const planData = await getRunPlan(runId);
          setPlan(planData);
        } catch {
          // Plan might not be available yet
        }
      }

      // Fetch artifacts if run has progressed
      if (['running', 'completed', 'failed'].includes(runData.status)) {
        try {
          const artifactsData = await getRunArtifacts(runId);
          setArtifacts(artifactsData);
        } catch {
          // Artifacts might not be available yet
        }
      }

      setLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load run');
      setLoading(false);
    }
  }, [runId]);

  // Initial load
  useEffect(() => {
    fetchRunData();
  }, [fetchRunData]);

  // WebSocket connection for live events
  useEffect(() => {
    if (!run || run.status !== 'running') return;

    const ws = new WebSocketClient(runId, {
      onEvent: (event) => {
        setEvents((prev) => [...prev, event]);
      },
      onStatusChange: (status) => {
        if (status === 'connected') {
          console.log('WebSocket connected');
        }
      },
      onError: (err) => {
        console.error('WebSocket error:', err);
      },
    });

    ws.connect();

    // Periodically refresh artifacts during running state
    const artifactInterval = setInterval(async () => {
      try {
        const artifactsData = await getRunArtifacts(runId);
        setArtifacts(artifactsData);
      } catch {
        // Ignore errors during periodic refresh
      }
    }, 5000);

    // Poll for run status changes
    const statusInterval = setInterval(async () => {
      try {
        const runData = await getRun(runId);
        setRun(runData);
        if (runData.status !== 'running') {
          // Run completed, do final artifact fetch
          const artifactsData = await getRunArtifacts(runId);
          setArtifacts(artifactsData);
        }
      } catch {
        // Ignore errors during polling
      }
    }, 3000);

    return () => {
      ws.disconnect();
      clearInterval(artifactInterval);
      clearInterval(statusInterval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run?.status, runId]);

  // Handle plan approval
  const handleApprove = async (edits?: { time_range?: { start: string; end: string }; sources?: string[] }) => {
    setActionLoading(true);
    try {
      await approveRun(runId, edits ? { edits } : undefined);
      await fetchRunData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to approve run');
    } finally {
      setActionLoading(false);
    }
  };

  // Handle run abort
  const handleAbort = async () => {
    setActionLoading(true);
    try {
      await abortRun(runId);
      await fetchRunData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to abort run');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <svg
            className="w-12 h-12 animate-spin text-blue-600 mx-auto"
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
          <p className="mt-4 text-gray-600">Loading run details...</p>
        </div>
      </div>
    );
  }

  if (error || !run) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="text-red-500 mb-4">
            <svg
              className="w-12 h-12 mx-auto"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Error</h2>
          <p className="text-gray-600 mb-4">{error || 'Run not found'}</p>
          <Link
            href="/"
            className="text-blue-600 hover:text-blue-800 underline"
          >
            Return to Home
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link
                href="/"
                className="text-gray-500 hover:text-gray-700"
              >
                <svg
                  className="w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M10 19l-7-7m0 0l7-7m-7 7h18"
                  />
                </svg>
              </Link>
              <div>
                <h1 className="text-xl font-semibold text-gray-900">
                  Run Details
                </h1>
                <p className="text-sm text-gray-500">ID: {runId}</p>
              </div>
            </div>
            <RunStatusBadge status={run.status} />
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Query display */}
        <div className="bg-white rounded-lg border border-gray-200 p-4 mb-6">
          <h2 className="text-sm font-medium text-gray-500 mb-2">Query</h2>
          <p className="text-gray-900">{run.query}</p>
          {run.selected_sources.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {run.selected_sources.map((source) => (
                <span
                  key={source}
                  className="text-xs bg-gray-100 px-2 py-1 rounded"
                >
                  {source}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Error summary */}
        {run.error_summary && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <h3 className="font-medium text-red-800 mb-1">Error</h3>
            <p className="text-sm text-red-700">{run.error_summary}</p>
          </div>
        )}

        {/* Plan Review (for needs_approval status) */}
        {run.status === 'needs_approval' && plan && (
          <div className="mb-6">
            <PlanReviewCard
              plan={plan}
              onApprove={handleApprove}
              onAbort={handleAbort}
              loading={actionLoading}
            />
          </div>
        )}

        {/* Main content grid */}
        <div className="grid lg:grid-cols-2 gap-6">
          {/* Left column: Event log / Timeline */}
          <div className="space-y-6">
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900">
                  Agent Activity
                </h2>
                {run.status === 'running' && (
                  <span className="flex items-center gap-2 text-sm text-green-600">
                    <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                    Live
                  </span>
                )}
              </div>
              <EventLog events={events} />
            </div>

            {/* Plan display (when not in approval state) */}
            {plan && run.status !== 'needs_approval' && (
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <h2 className="text-lg font-semibold text-gray-900 mb-4">
                  Execution Plan
                </h2>
                <div className="space-y-3">
                  {plan.steps.map((step, idx) => (
                    <div
                      key={idx}
                      className="flex gap-3 text-sm"
                    >
                      <span className="w-6 h-6 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-xs font-medium shrink-0">
                        {idx + 1}
                      </span>
                      <div>
                        <span className="font-medium text-gray-900">
                          {step.agent}:
                        </span>{' '}
                        <span className="text-gray-700">{step.action}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right column: Artifacts */}
          <div className="space-y-6">
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900">Results</h2>
                {run.status === 'completed' && (
                  <ExportButtons runId={runId} />
                )}
              </div>
              <ArtifactsPanel
                artifacts={artifacts}
                loading={run.status === 'running' && !artifacts}
              />
            </div>
          </div>
        </div>

        {/* Timestamps */}
        <div className="mt-6 bg-white rounded-lg border border-gray-200 p-4">
          <h2 className="text-sm font-medium text-gray-500 mb-3">Timeline</h2>
          <div className="flex flex-wrap gap-6 text-sm">
            <div>
              <span className="text-gray-500">Created:</span>{' '}
              <span className="text-gray-900">
                {new Date(run.created_at).toLocaleString()}
              </span>
            </div>
            {run.started_at && (
              <div>
                <span className="text-gray-500">Started:</span>{' '}
                <span className="text-gray-900">
                  {new Date(run.started_at).toLocaleString()}
                </span>
              </div>
            )}
            {run.finished_at && (
              <div>
                <span className="text-gray-500">Finished:</span>{' '}
                <span className="text-gray-900">
                  {new Date(run.finished_at).toLocaleString()}
                </span>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
