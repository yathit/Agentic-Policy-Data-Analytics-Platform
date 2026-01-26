'use client';

import { useState } from 'react';
import type { TableData } from '@/lib/types';

interface TablesPanelProps {
  tables: TableData[];
}

export default function TablesPanel({ tables }: TablesPanelProps) {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  if (tables.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <p>No tables generated yet.</p>
      </div>
    );
  }

  const copyToClipboard = async (table: TableData) => {
    const header = table.columns.join(',');
    const rows = table.rows.map((row) =>
      row.map((cell) => (cell === null ? '' : String(cell))).join(',')
    );
    const csv = [header, ...rows].join('\n');

    try {
      await navigator.clipboard.writeText(csv);
      setCopiedId(table.id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
    }
  };

  return (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold text-gray-900">Data Tables</h3>
      <div className="space-y-6">
        {tables.map((table) => (
          <div
            key={table.id}
            className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden"
          >
            {/* Table header */}
            <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b">
              <h4 className="font-medium text-gray-900">{table.title}</h4>
              <button
                onClick={() => copyToClipboard(table)}
                className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1"
              >
                {copiedId === table.id ? (
                  <>
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                    Copied!
                  </>
                ) : (
                  <>
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                      />
                    </svg>
                    Copy CSV
                  </>
                )}
              </button>
            </div>

            {/* Table content */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50">
                    {table.columns.map((col, idx) => (
                      <th
                        key={idx}
                        className="px-4 py-2 text-left font-medium text-gray-700 border-b"
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {table.rows.map((row, rowIdx) => (
                    <tr
                      key={rowIdx}
                      className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}
                    >
                      {row.map((cell, cellIdx) => (
                        <td
                          key={cellIdx}
                          className="px-4 py-2 text-gray-900 border-b border-gray-100"
                        >
                          {cell === null ? (
                            <span className="text-gray-400">-</span>
                          ) : typeof cell === 'number' ? (
                            cell.toLocaleString()
                          ) : (
                            cell
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Row count */}
            <div className="px-4 py-2 bg-gray-50 border-t text-xs text-gray-500">
              {table.rows.length} row{table.rows.length !== 1 ? 's' : ''}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
