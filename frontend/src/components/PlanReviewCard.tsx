'use client';

import { useState } from 'react';
import type { Plan } from '@/lib/types';

interface PlanReviewCardProps {
  plan: Plan;
  onApprove: (edits?: { time_range?: { start: string; end: string }; sources?: string[] }) => void;
  onAbort: () => void;
  loading?: boolean;
}

export default function PlanReviewCard({
  plan,
  onApprove,
  onAbort,
  loading = false,
}: PlanReviewCardProps) {
  const [showEditMode, setShowEditMode] = useState(false);
  const [editedSources, setEditedSources] = useState<string[]>(
    plan.constraints.allowed_sources
  );
  const [editedTimeRange, setEditedTimeRange] = useState(
    plan.constraints.time_range || { start: '', end: '' }
  );

  const handleApprove = () => {
    if (showEditMode) {
      onApprove({
        sources: editedSources,
        time_range: editedTimeRange.start && editedTimeRange.end ? editedTimeRange : undefined,
      });
    } else {
      onApprove();
    }
  };

  const toggleSource = (source: string) => {
    if (editedSources.includes(source)) {
      setEditedSources(editedSources.filter((s) => s !== source));
    } else {
      setEditedSources([...editedSources, source]);
    }
  };

  return (
    <div className="bg-white border border-yellow-200 rounded-lg shadow-sm overflow-hidden">
      <div className="bg-yellow-50 px-6 py-4 border-b border-yellow-200">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-yellow-800">
            Plan Review Required
          </h2>
          <span className="text-sm text-yellow-600">
            {plan.steps.length} steps planned
          </span>
        </div>
        <p className="text-sm text-yellow-700 mt-1">
          Review the execution plan before proceeding. You can edit constraints or abort.
        </p>
      </div>

      <div className="p-6 space-y-6">
        {/* Plan Steps */}
        <div>
          <h3 className="font-medium text-gray-900 mb-3">Execution Steps</h3>
          <ol className="space-y-3">
            {plan.steps.map((step, index) => (
              <li
                key={index}
                className="flex gap-3 p-3 bg-gray-50 rounded-lg"
              >
                <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-sm font-medium">
                  {index + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-medium px-2 py-0.5 bg-purple-100 text-purple-700 rounded">
                      {step.agent}
                    </span>
                    <span className="font-medium text-gray-900">
                      {step.action}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600">
                    {step.expected_output}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </div>

        {/* Constraints */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-medium text-gray-900">Constraints</h3>
            <button
              type="button"
              onClick={() => setShowEditMode(!showEditMode)}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              {showEditMode ? 'Cancel Edit' : 'Edit'}
            </button>
          </div>

          {showEditMode ? (
            <div className="space-y-4 p-4 bg-blue-50 rounded-lg">
              {/* Source editing */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Allowed Sources
                </label>
                <div className="flex flex-wrap gap-2">
                  {plan.constraints.allowed_sources.map((source) => (
                    <label
                      key={source}
                      className="inline-flex items-center gap-2 px-3 py-1.5 bg-white border rounded cursor-pointer hover:bg-gray-50"
                    >
                      <input
                        type="checkbox"
                        checked={editedSources.includes(source)}
                        onChange={() => toggleSource(source)}
                        className="w-4 h-4 text-blue-600 rounded"
                      />
                      <span className="text-sm">{source}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Time range editing */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Time Range (optional)
                </label>
                <div className="flex gap-4">
                  <input
                    type="date"
                    value={editedTimeRange.start}
                    onChange={(e) =>
                      setEditedTimeRange({ ...editedTimeRange, start: e.target.value })
                    }
                    className="px-3 py-2 border rounded text-sm"
                    placeholder="Start date"
                  />
                  <span className="self-center text-gray-500">to</span>
                  <input
                    type="date"
                    value={editedTimeRange.end}
                    onChange={(e) =>
                      setEditedTimeRange({ ...editedTimeRange, end: e.target.value })
                    }
                    className="px-3 py-2 border rounded text-sm"
                    placeholder="End date"
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="p-4 bg-gray-50 rounded-lg">
              <div className="flex flex-wrap gap-2 mb-2">
                {plan.constraints.allowed_sources.map((source) => (
                  <span
                    key={source}
                    className="text-xs px-2 py-1 bg-gray-200 text-gray-700 rounded"
                  >
                    {source}
                  </span>
                ))}
              </div>
              {plan.constraints.time_range && (
                <p className="text-sm text-gray-600">
                  Time range: {plan.constraints.time_range.start} to{' '}
                  {plan.constraints.time_range.end}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex gap-3 pt-4 border-t">
          <button
            onClick={handleApprove}
            disabled={loading}
            className="flex-1 px-4 py-2.5 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Approving...' : 'Approve & Run'}
          </button>
          <button
            onClick={onAbort}
            disabled={loading}
            className="px-4 py-2.5 bg-red-100 text-red-700 font-medium rounded-lg hover:bg-red-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Abort
          </button>
        </div>
      </div>
    </div>
  );
}
