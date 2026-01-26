'use client';

import type { DatasetInfo } from '@/lib/types';

interface ProvenancePanelProps {
  datasets: DatasetInfo[];
  highlightedDatasetId?: string;
}

export default function ProvenancePanel({
  datasets,
  highlightedDatasetId,
}: ProvenancePanelProps) {
  if (datasets.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <p>No data provenance information available.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-900">Data Provenance</h3>
      <p className="text-sm text-gray-600">
        Sources and datasets used in this analysis
      </p>

      <div className="space-y-3">
        {datasets.map((dataset) => (
          <div
            key={dataset.id}
            id={`dataset-${dataset.id}`}
            className={`bg-white border rounded-lg p-4 transition-all ${
              highlightedDatasetId === dataset.id
                ? 'border-blue-500 ring-2 ring-blue-200'
                : 'border-gray-200'
            }`}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h4 className="font-medium text-gray-900">{dataset.name}</h4>
                <p className="text-xs text-gray-500 mt-1">ID: {dataset.id}</p>
              </div>
              {dataset.record_count !== undefined && (
                <span className="text-xs bg-gray-100 px-2 py-1 rounded text-gray-600">
                  {dataset.record_count.toLocaleString()} records
                </span>
              )}
            </div>

            <div className="mt-3 space-y-2 text-sm">
              {/* URI */}
              <div className="flex items-start gap-2">
                <span className="text-gray-500 shrink-0">Source:</span>
                <code className="text-xs bg-gray-50 px-2 py-1 rounded break-all">
                  {dataset.uri}
                </code>
              </div>

              {/* Timestamp */}
              <div className="flex items-center gap-2">
                <span className="text-gray-500">Retrieved:</span>
                <span className="text-gray-700">
                  {new Date(dataset.retrieved_at).toLocaleString()}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
