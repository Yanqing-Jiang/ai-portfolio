import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { StockWidgetConfig } from '../types';

interface TradingViewSymbolOverviewProps {
  config: StockWidgetConfig;
  height?: number;
  theme?: 'light' | 'dark';
}

const DEFAULT_HEIGHT = 420;

export const TradingViewSymbolOverview: React.FC<TradingViewSymbolOverviewProps> = ({
  config,
  height,
  theme,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const normalizedSymbols = useMemo(() => {
    return (config?.symbols ?? []).map((entry) => {
      if (Array.isArray(entry)) {
        const [label, value] = entry as [string | undefined, string | undefined];
        const resolvedLabel = label || value || '';
        const resolvedValue = value || label || '';
        const tradingValue = resolvedValue && resolvedValue.includes(':') ? resolvedValue : `NASDAQ:${resolvedValue.toUpperCase()}`;
        return {
          label: resolvedLabel || tradingValue,
          tradingPair: [resolvedLabel || tradingValue, tradingValue] as [string, string],
        };
      }
      const rawSymbol = String(entry || '').trim();
      const hasExchange = rawSymbol.includes(':');
      const tradingValue = hasExchange ? rawSymbol.toUpperCase() : `NASDAQ:${rawSymbol.toUpperCase()}`;
      return {
        label: hasExchange ? rawSymbol.split(':')[1] || rawSymbol : rawSymbol.toUpperCase(),
        tradingPair: [tradingValue, tradingValue] as [string, string],
      };
    });
  }, [config?.symbols]);

  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    setActiveIndex(0);
  }, [normalizedSymbols.length]);

  const hasMultipleSymbols = normalizedSymbols.length > 1;
  const activeEntry = normalizedSymbols[activeIndex] ?? normalizedSymbols[0];
  const tradingViewSymbols = hasMultipleSymbols
    ? (activeEntry ? [activeEntry.tradingPair] : [])
    : normalizedSymbols.map((item) => item.tradingPair);

  useEffect(() => {
    if (!containerRef.current || !tradingViewSymbols.length) {
      return;
    }

    containerRef.current.innerHTML = '';

    const script = document.createElement('script');
    script.type = 'text/javascript';
    script.async = true;
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js';

    // Optional theme overrides can be wired via the `theme` prop when design requests additional palettes.
    const configuredChartType = config.chartType?.toLowerCase();
    const normalizedChartType = configuredChartType
      ? configuredChartType === 'candlestick'
        ? 'candlesticks'
        : configuredChartType
      : 'candlesticks';

    const widgetConfig = {
      symbols: tradingViewSymbols,
      chartOnly: false,
      width: '100%',
      height: height ?? config.height ?? DEFAULT_HEIGHT,
      locale: config.locale ?? 'en',
      colorTheme: theme ?? config.colorTheme ?? 'dark',
      showFloatingTooltip: false,
      autosize: config.autosize ?? true,
      showVolume: config.showVolume ?? true,
      showMA: config.showMA ?? false,
      chartType: normalizedChartType,
    };

    script.innerHTML = JSON.stringify(widgetConfig);
    containerRef.current.appendChild(script);

    return () => {
      if (containerRef.current) {
        containerRef.current.innerHTML = '';
      }
    };
  }, [
    tradingViewSymbols,
    config.locale,
    config.height,
    config.colorTheme,
    config.chartType,
    config.showVolume,
    config.showMA,
    config.autosize,
    height,
    theme,
  ]);

  const handlePrev = useCallback(() => {
    if (!hasMultipleSymbols) return;
    setActiveIndex((prev) => (prev - 1 + normalizedSymbols.length) % normalizedSymbols.length);
  }, [hasMultipleSymbols, normalizedSymbols.length]);

  const handleNext = useCallback(() => {
    if (!hasMultipleSymbols) return;
    setActiveIndex((prev) => (prev + 1) % normalizedSymbols.length);
  }, [hasMultipleSymbols, normalizedSymbols.length]);

  const activeLabel = activeEntry?.label ?? '';

  return (
    <div className="tradingview-widget-container w-full rounded-xl border border-gray-700/70 bg-gray-900/50">
      {hasMultipleSymbols ? (
        <div className="flex items-center justify-between gap-3 border-b border-gray-700/70 bg-gray-900/70 px-3 py-2">
          <button
            type="button"
            onClick={handlePrev}
            className="rounded-md border border-gray-600/70 px-2 py-1 text-xs font-medium text-gray-200 transition hover:border-gray-400 hover:text-white"
          >
            ‹ Prev
          </button>
          <div className="text-sm font-semibold uppercase tracking-wide text-gray-100">
            {activeLabel}
          </div>
          <button
            type="button"
            onClick={handleNext}
            className="rounded-md border border-gray-600/70 px-2 py-1 text-xs font-medium text-gray-200 transition hover:border-gray-400 hover:text-white"
          >
            Next ›
          </button>
        </div>
      ) : null}
      <div
        ref={containerRef}
        className="tradingview-widget-container__widget w-full"
        style={{ minHeight: height ?? config.height ?? DEFAULT_HEIGHT }}
      />
      <div className="tradingview-widget-copyright text-[10px] text-gray-500 px-3 py-2">
        <span>
          Quotes powered by{' '}
          <a
            href="https://www.tradingview.com"
            rel="noopener noreferrer"
            target="_blank"
            className="text-blue-400 hover:text-blue-300"
          >
            TradingView
          </a>
        </span>
      </div>
    </div>
  );
};

export default TradingViewSymbolOverview;
