import React, { useEffect, useRef } from 'react';
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

  useEffect(() => {
    if (!containerRef.current || !config?.symbols?.length) {
      return;
    }

    containerRef.current.innerHTML = '';

    const script = document.createElement('script');
    script.type = 'text/javascript';
    script.async = true;
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js';

    const symbols = config.symbols.map((symbol) => {
      if (Array.isArray(symbol)) {
        return symbol;
      }
      const upper = symbol.includes(':') ? symbol : `NASDAQ:${symbol.toUpperCase()}`;
      return [upper, upper];
    });

    // Optional theme overrides can be wired via the `theme` prop when design requests additional palettes.
    const configuredChartType = config.chartType?.toLowerCase();
    const normalizedChartType = configuredChartType
      ? configuredChartType === 'candlestick'
        ? 'candlesticks'
        : configuredChartType
      : 'candlesticks';

    const widgetConfig = {
      symbols,
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
  }, [config.symbols, config.locale, config.height, config.colorTheme, config.chartType, config.showVolume, config.showMA, config.autosize, height, theme]);

  return (
    <div className="tradingview-widget-container rounded-xl border border-gray-700/70 bg-gray-900/50">
      <div ref={containerRef} className="tradingview-widget-container__widget" style={{ minHeight: height ?? config.height ?? DEFAULT_HEIGHT }} />
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
