import React, { useState } from 'react';
import EChartsReact from 'echarts-for-react';
import { ChartCardProps } from '../types';
import { ChartErrorBoundary } from './ChartErrorBoundary';
import { withLightTheme } from '../utils';
import { downloadCsv, extractDataFromChartSpec } from '../utils';

export const ChartCard: React.FC<ChartCardProps> = ({
  chartSpec,
  dataSample,
  useAltChart = false,
  height = 'h-[280px] sm:h-[360px] md:h-[440px] lg:h-[520px]',
  onError,
  enableDropdown = false,
  enableCsvDownload = false
}) => {
  const [chartRetryCount, setChartRetryCount] = useState(0);

  const handleChartError = (error: any) => {
    console.log('[ChartCard] Chart error boundary triggered:', error);
    if (chartRetryCount >= 1) {
      onError?.(error);
    } else {
      setChartRetryCount(prev => prev + 1);
      setTimeout(() => {
        // Force re-render by triggering parent update
        onError?.(error);
      }, 200);
    }
  };

  const handleMetricChange = (selectedMetric: string) => {
    const instance = (window as any)._echarts_instance_;
    if (instance) {
      const current = instance.getOption();
      const legend = current.legend && current.legend[0];
      if (legend && legend.data) {
        const selectedMap: any = legend.selected || {};
        
        // Metric grouping: show all companies for the selected metric
        legend.data.forEach((name: string) => selectedMap[name] = false);
        legend.data.forEach((name: string) => {
          // Show series that end with the selected metric name
          if (name.endsWith(' - ' + selectedMetric)) {
            selectedMap[name] = true;
          }
        });
        
        instance.setOption({ legend: [{ selected: selectedMap }] });
      }
    }
  };

  const handleCsvDownload = () => {
    const data = extractDataFromChartSpec(chartSpec);
    downloadCsv(data, 'analytics_data.csv');
  };

  if (!chartSpec || useAltChart) {
    return null;
  }

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl p-4 sm:p-6 md:p-8">
      <h2 className="text-lg sm:text-xl md:text-2xl font-semibold text-white mb-4 sm:mb-6">Interactive Visualization</h2>
      <div className={`${height} bg-white rounded-lg p-2 sm:p-3`}>
        {/* Controls row */}
        {(enableDropdown || enableCsvDownload) && (
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-4 mb-3 sm:mb-2">
            {enableDropdown && (
              <div className="flex items-center gap-2 text-gray-700 text-sm sm:text-base">
                <label className="font-medium">Series:</label>
                <select
                  className="bg-gray-100 border border-gray-300 rounded px-2 sm:px-3 py-1 sm:py-1.5 text-sm sm:text-base min-h-[32px] sm:min-h-[36px]"
                  onChange={(e) => handleMetricChange(e.target.value)}
                  defaultValue={((chartSpec.meta?.defaultColumns || []).map((c: string) => c.replace(/_/g, ' ').replace(/\b\w/g, (m: string) => m.toUpperCase())))[0]}
                >
                  {/* Always show metrics */}
                  {(chartSpec.meta?.includedColumns || []).map((c: string) => {
                    const label = c.replace(/_/g, ' ').replace(/\b\w/g, (m: string) => m.toUpperCase());
                    return <option key={c} value={label}>{label}</option>;
                  })}
                </select>
              </div>
            )}
            {enableCsvDownload && (
              <button
                className="px-3 py-1.5 bg-gray-100 border border-gray-300 rounded text-gray-700 text-sm hover:bg-gray-200"
                onClick={handleCsvDownload}
              >
                Download CSV
              </button>
            )}
          </div>
        )}
        
        <ChartErrorBoundary 
          key={`chart-${chartRetryCount}-${JSON.stringify(chartSpec)?.substring(0,50)}`} 
          onError={handleChartError}
        >
          <EChartsReact 
            option={withLightTheme(chartSpec)} 
            style={{ 
              height: enableDropdown || enableCsvDownload ? 'calc(100% - 36px)' : 'calc(100% - 4px)', 
              width: '100%' 
            }} 
            opts={{ renderer: 'canvas', devicePixelRatio: window.devicePixelRatio || 1 }} 
            onChartReady={(instance) => { 
              (window as any)._echarts_instance_ = instance;
              // Small delay to ensure proper initialization
              setTimeout(() => instance.resize(), 100);
            }}
          />
        </ChartErrorBoundary>
      </div>
    </div>
  );
};