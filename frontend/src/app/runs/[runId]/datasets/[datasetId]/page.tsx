'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { getRunDatasetSnapshot } from '@/lib/api';
import type { RunDatasetSnapshot } from '@/lib/types';

interface RunDatasetPageProps {
  params: {
    runId: string;
    datasetId: string;
  };
}

export default function RunDatasetPage({ params }: RunDatasetPageProps) {
  const { runId, datasetId } = params;
  const [data, setData] = useState<RunDatasetSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    getRunDatasetSnapshot(runId, datasetId)
      .then((snapshot) => {
        if (!mounted) return;
        setData(snapshot);
      })
      .catch((err: unknown) => {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : 'Failed to load dataset snapshot');
      })
      .finally(() => {
        if (!mounted) return;
        setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [runId, datasetId]);

  if (loading) {
    return <div className="p-6 text-gray-600">Loading run dataset...</div>;
  }

  if (error || !data) {
    return (
      <div className="p-6">
        <p className="text-red-700 mb-3">{error || 'Dataset snapshot not found'}</p>
        <Link href={`/runs/${runId}`} className="text-blue-600 hover:text-blue-800 underline">
          Back to run
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-4 sm:p-6">
      <div className="max-w-7xl mx-auto space-y-4">
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h1 className="text-lg font-semibold text-gray-900">{data.dataset_name}</h1>
              <p className="text-sm text-gray-600">Run dataset snapshot for run {runId}</p>
            </div>
            <Link href={`/runs/${runId}`} className="text-sm text-blue-600 hover:text-blue-800 underline">
              Back to run
            </Link>
          </div>
          <div className="mt-3 text-sm text-gray-700">
            Showing {data.rows.length.toLocaleString()} of {data.total_row_count.toLocaleString()} rows
            {data.is_truncated ? ' (truncated)' : ''}
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <div className="overflow-auto max-h-[70vh]">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  {data.columns.map((column) => (
                    <th key={column} className="px-3 py-2 text-left font-medium text-gray-700 border-b">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row, index) => (
                  <tr key={index} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                    {row.map((cell, cellIndex) => (
                      <td key={cellIndex} className="px-3 py-2 border-b border-gray-100 text-gray-900">
                        {cell === null ? <span className="text-gray-400">-</span> : String(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
