'use client';

import dynamic from 'next/dynamic';
import type { ChartSpec } from '@/lib/types';
import type { PlotParams } from 'react-plotly.js';

// Dynamically import Plotly to avoid SSR issues
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

interface ChartsPanelProps {
  charts: ChartSpec[];
}

export default function ChartsPanel({ charts }: ChartsPanelProps) {
  if (charts.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <p>No charts generated yet.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold text-gray-900">Charts</h3>
      <div className="grid gap-6">
        {charts.map((chart) => {
          // Cast data to the expected Plotly format
          const plotData = chart.data as unknown as PlotParams['data'];
          const plotLayout = {
            autosize: true,
            margin: { l: 50, r: 30, t: 30, b: 50 },
            ...chart.layout,
          } as PlotParams['layout'];

          return (
            <div
              key={chart.id}
              className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm"
            >
              {chart.title && (
                <h4 className="font-medium text-gray-900 mb-4">{chart.title}</h4>
              )}
              <div className="w-full overflow-hidden">
                <Plot
                  data={plotData}
                  layout={plotLayout}
                  config={{
                    responsive: true,
                    displayModeBar: true,
                    displaylogo: false,
                  }}
                  style={{ width: '100%', height: '400px' }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
