'use client';

import type { Insight } from '@/lib/types';

interface InsightsPanelProps {
  insights: Insight[];
  onCitationClick?: (datasetId: string) => void;
}

const confidenceColors: Record<string, string> = {
  high: 'bg-green-100 text-green-800 border-green-200',
  medium: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  low: 'bg-red-100 text-red-800 border-red-200',
};

export default function InsightsPanel({
  insights,
  onCitationClick,
}: InsightsPanelProps) {
  if (insights.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <p>No insights generated yet.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-900">Key Insights</h3>
      <div className="space-y-4">
        {insights.map((insight) => (
          <div
            key={insight.id}
            className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm"
          >
            {/* Headline */}
            <div className="flex items-start justify-between gap-4 mb-3">
              <h4 className="font-medium text-gray-900">{insight.headline}</h4>
              <span
                className={`text-xs px-2 py-1 rounded-full border ${
                  confidenceColors[insight.confidence]
                }`}
              >
                {insight.confidence} confidence
              </span>
            </div>

            {/* Evidence */}
            {insight.evidence.length > 0 && (
              <div className="mb-3">
                <p className="text-xs text-gray-500 mb-1">Evidence</p>
                <div className="flex flex-wrap gap-2">
                  {insight.evidence.map((ev, idx) => (
                    <span
                      key={idx}
                      className="text-sm bg-gray-100 px-2 py-1 rounded"
                      title={ev.pointer}
                    >
                      {typeof ev.value === 'number'
                        ? ev.value.toLocaleString()
                        : ev.value}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Citations */}
            {insight.citations.length > 0 && (
              <div>
                <p className="text-xs text-gray-500 mb-1">Sources</p>
                <div className="flex flex-wrap gap-2">
                  {insight.citations.map((citation, idx) => (
                    <button
                      key={idx}
                      onClick={() => onCitationClick?.(citation.dataset_id)}
                      className="text-xs text-blue-600 hover:text-blue-800 hover:underline"
                    >
                      {citation.dataset_id}
                      {citation.columns && ` (${citation.columns.join(', ')})`}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
