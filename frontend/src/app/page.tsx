'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import QueryBox from '@/components/QueryBox';
import SourcePicker from '@/components/SourcePicker';
import { createRun, getSources } from '@/lib/api';
import type { SourceOption } from '@/lib/types';

export default function Home() {
  const router = useRouter();
  const [sources, setSources] = useState<SourceOption[]>([]);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load available sources on mount
  useEffect(() => {
    getSources().then((data) => {
      setSources(data);
      // Pre-select recommended sources
      const recommended = data.filter((s) => s.recommended).map((s) => s.id);
      setSelectedSources(recommended);
    });
  }, []);

  const handleSubmit = async (query: string) => {
    setIsSubmitting(true);
    setError(null);

    try {
      const result = await createRun({
        query,
        requested_sources: selectedSources.length > 0 ? selectedSources : undefined,
      });
      // Navigate to the run detail page
      router.push(`/runs/${result.run.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create run');
      setIsSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Navigation */}
      <nav className="bg-white/80 backdrop-blur border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <h1 className="font-semibold text-gray-900">
            Agentic Policy Data Analytics Platform
          </h1>
          <Link
            href="/history"
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            View History
          </Link>
        </div>
      </nav>

      <div className="max-w-3xl mx-auto px-4 py-12">
        {/* Header */}
        <div className="text-center mb-12">
          <h2 className="text-4xl font-bold text-gray-900 mb-3">
            Analyze Policy Data
          </h2>
          <p className="text-lg text-gray-600">
            Natural language queries with full transparency and human oversight
          </p>
        </div>

        {/* Query form */}
        <div className="bg-white rounded-xl shadow-lg p-6 space-y-6">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              New Analysis Query
            </h3>
            <QueryBox
              onSubmit={handleSubmit}
              disabled={isSubmitting}
              placeholder="What trends do you see in Singapore's digital adoption rates over the past 5 years? Compare across different demographics."
            />
          </div>

          {/* Source picker */}
          <div>
            <SourcePicker
              sources={sources}
              selectedSources={selectedSources}
              onChange={setSelectedSources}
              disabled={isSubmitting}
            />
          </div>

          {/* Error message */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}
        </div>

        {/* Info cards */}
        <div className="mt-8 grid md:grid-cols-3 gap-4">
          <div className="bg-white/70 backdrop-blur rounded-lg p-4">
            <div className="text-blue-600 mb-2">
              <svg
                className="w-6 h-6"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
            <h4 className="font-medium text-gray-900">Plan Review</h4>
            <p className="text-sm text-gray-600 mt-1">
              Review and approve the analysis plan before execution
            </p>
          </div>

          <div className="bg-white/70 backdrop-blur rounded-lg p-4">
            <div className="text-blue-600 mb-2">
              <svg
                className="w-6 h-6"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                />
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                />
              </svg>
            </div>
            <h4 className="font-medium text-gray-900">Live Monitoring</h4>
            <p className="text-sm text-gray-600 mt-1">
              Watch agent reasoning and actions in real-time
            </p>
          </div>

          <div className="bg-white/70 backdrop-blur rounded-lg p-4">
            <div className="text-blue-600 mb-2">
              <svg
                className="w-6 h-6"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
            </div>
            <h4 className="font-medium text-gray-900">Full Provenance</h4>
            <p className="text-sm text-gray-600 mt-1">
              Complete data lineage and citation tracking
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
