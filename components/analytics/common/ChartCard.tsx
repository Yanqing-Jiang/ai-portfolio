import React, { useState, useRef } from 'react';
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
  const chartRef = useRef<any>(null);

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
    const instance = chartRef.current;
    if (instance) {
      const current = instance.getOption();
      const legend = current.legend && current.legend[0];
      if (legend && legend.data) {
        const selectedMap: any = legend.selected || {};
        
        // Hide all series first
        legend.data.forEach((name: string) => selectedMap[name] = false);
        
        // Show series based on selection
        legend.data.forEach((name: string) => {
          const nameLower = name.toLowerCase();
          const selectedLower = selectedMetric.toLowerCase();
          
          // Handle different series name patterns
          if (name.endsWith(' - ' + selectedMetric)) {
            // Standard pattern: "Company - Metric"
            selectedMap[name] = true;
          } else if (selectedLower === 'yoy growth' && nameLower.includes('yoy growth')) {
            // Revenue growth pattern: show both company and industry average
            selectedMap[name] = true;
          } else if (selectedLower === 'company' && nameLower.includes(' - yoy growth') && !nameLower.includes('industry')) {
            // Show only company data for revenue growth
            selectedMap[name] = true;
          } else if (selectedLower === 'industry average' && nameLower.includes('industry average')) {
            // Show only industry average data
            selectedMap[name] = true;
          } else if (selectedLower.includes('margin change') && nameLower.includes('margin change')) {
            // Margin growth pattern: show both company and industry average
            selectedMap[name] = true;
          } else if (selectedLower === 'company' && nameLower.includes(' - ') && nameLower.includes('margin change') && !nameLower.includes('industry')) {
            // Show only company data for margin growth
            selectedMap[name] = true;
          } else if (selectedLower === 'industry average' && nameLower.includes('industry average') && nameLower.includes('margin change')) {
            // Show only industry average data for margin growth
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
              chartRef.current = instance;
              // Small delay to ensure proper initialization
              setTimeout(() => instance.resize(), 100);
            }}
          />
        </ChartErrorBoundary>
      </div>
    </div>
  );
};