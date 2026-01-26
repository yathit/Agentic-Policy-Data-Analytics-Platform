'use client';

import { useState } from 'react';
import type { Artifacts } from '@/lib/types';
import InsightsPanel from './InsightsPanel';
import ChartsPanel from './ChartsPanel';
import TablesPanel from './TablesPanel';
import ProvenancePanel from './ProvenancePanel';

interface ArtifactsPanelProps {
  artifacts: Artifacts | null;
  loading?: boolean;
}

type Tab = 'insights' | 'charts' | 'tables' | 'provenance';

const tabs: { id: Tab; label: string }[] = [
  { id: 'insights', label: 'Insights' },
  { id: 'charts', label: 'Charts' },
  { id: 'tables', label: 'Tables' },
  { id: 'provenance', label: 'Provenance' },
];

export default function ArtifactsPanel({
  artifacts,
  loading,
}: ArtifactsPanelProps) {
  const [activeTab, setActiveTab] = useState<Tab>('insights');
  const [highlightedDatasetId, setHighlightedDatasetId] = useState<string>();

  const handleCitationClick = (datasetId: string) => {
    setActiveTab('provenance');
    setHighlightedDatasetId(datasetId);
    // Scroll to the dataset after a short delay for tab switch
    setTimeout(() => {
      const el = document.getElementById(`dataset-${datasetId}`);
      el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 100);
  };

  if (loading) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-8">
        <div className="flex items-center justify-center">
          <svg
            className="w-8 h-8 animate-spin text-blue-600"
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
          <span className="ml-3 text-gray-600">Loading artifacts...</span>
        </div>
      </div>
    );
  }

  if (!artifacts) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-8 text-center text-gray-500">
        <p>No artifacts available yet.</p>
      </div>
    );
  }

  // Check if any artifacts are empty (degraded mode)
  const hasInsights = artifacts.insights.length > 0;
  const hasCharts = artifacts.charts.length > 0;
  const hasTables = artifacts.tables.length > 0;
  const isDegradedMode = !hasInsights && (hasCharts || hasTables);

  return (
    <div className="space-y-4">
      {/* Degraded mode warning */}
      {isDegradedMode && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <svg
              className="w-5 h-5 text-yellow-600 shrink-0 mt-0.5"
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
            <div>
              <h4 className="font-medium text-yellow-800">Degraded Mode</h4>
              <p className="text-sm text-yellow-700 mt-1">
                Narrative insights could not be generated. Computed charts and
                tables are still available below.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-4" aria-label="Tabs">
          {tabs.map((tab) => {
            const count =
              tab.id === 'insights'
                ? artifacts.insights.length
                : tab.id === 'charts'
                ? artifacts.charts.length
                : tab.id === 'tables'
                ? artifacts.tables.length
                : artifacts.datasets.length;

            return (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveTab(tab.id);
                  if (tab.id !== 'provenance') {
                    setHighlightedDatasetId(undefined);
                  }
                }}
                className={`px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {tab.label}
                {count > 0 && (
                  <span className="ml-2 bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full text-xs">
                    {count}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab content */}
      <div className="py-4">
        {activeTab === 'insights' && (
          <InsightsPanel
            insights={artifacts.insights}
            onCitationClick={handleCitationClick}
          />
        )}
        {activeTab === 'charts' && <ChartsPanel charts={artifacts.charts} />}
        {activeTab === 'tables' && <TablesPanel tables={artifacts.tables} />}
        {activeTab === 'provenance' && (
          <ProvenancePanel
            datasets={artifacts.datasets}
            highlightedDatasetId={highlightedDatasetId}
          />
        )}
      </div>
    </div>
  );
}
