'use client';

import { useState } from 'react';
import type { SourceOption } from '@/lib/types';

interface SourcePickerProps {
  sources: SourceOption[];
  selectedSources: string[];
  onChange: (sources: string[]) => void;
  disabled?: boolean;
}

export default function SourcePicker({
  sources,
  selectedSources,
  onChange,
  disabled = false,
}: SourcePickerProps) {
  const [expanded, setExpanded] = useState(false);

  const toggleSource = (sourceId: string) => {
    if (disabled) return;

    if (selectedSources.includes(sourceId)) {
      onChange(selectedSources.filter((id) => id !== sourceId));
    } else {
      onChange([...selectedSources, sourceId]);
    }
  };

  const selectAll = () => {
    if (disabled) return;
    onChange(sources.map((s) => s.id));
  };

  const selectRecommended = () => {
    if (disabled) return;
    onChange(sources.filter((s) => s.recommended).map((s) => s.id));
  };

  if (sources.length === 0) {
    return (
      <div className="animate-pulse bg-gray-100 rounded-lg p-4 h-16" />
    );
  }

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center justify-between bg-gray-50 hover:bg-gray-100 transition-colors"
      >
        <span className="font-medium text-gray-700">
          Data Sources ({selectedSources.length} selected)
        </span>
        <svg
          className={`w-5 h-5 text-gray-500 transition-transform ${
            expanded ? 'rotate-180' : ''
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {expanded && (
        <div className="p-4 space-y-3 bg-white">
          <div className="flex gap-2 mb-3">
            <button
              type="button"
              onClick={selectRecommended}
              disabled={disabled}
              className="text-sm px-3 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200 disabled:opacity-50"
            >
              Recommended
            </button>
            <button
              type="button"
              onClick={selectAll}
              disabled={disabled}
              className="text-sm px-3 py-1 bg-gray-100 text-gray-700 rounded hover:bg-gray-200 disabled:opacity-50"
            >
              Select All
            </button>
          </div>

          {sources.map((source) => (
            <label
              key={source.id}
              className={`flex items-start gap-3 p-2 rounded cursor-pointer hover:bg-gray-50 ${
                disabled ? 'opacity-50 cursor-not-allowed' : ''
              }`}
            >
              <input
                type="checkbox"
                checked={selectedSources.includes(source.id)}
                onChange={() => toggleSource(source.id)}
                disabled={disabled}
                className="mt-1 w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
              />
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-medium text-gray-900">
                    {source.name}
                  </span>
                  {source.recommended && (
                    <span className="text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded-full">
                      Recommended
                    </span>
                  )}
                </div>
                {source.description && (
                  <p className="text-sm text-gray-500">{source.description}</p>
                )}
              </div>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
