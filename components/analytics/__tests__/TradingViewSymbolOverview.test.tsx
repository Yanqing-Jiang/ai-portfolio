import { render, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import { TradingViewSymbolOverview } from '../common/TradingViewSymbolOverview';
import type { StockWidgetConfig } from '../types';

describe('TradingViewSymbolOverview', () => {
  it('embeds TradingView widget with normalized configuration', async () => {
    const config: StockWidgetConfig = {
      symbols: ['NVDA', ['NASDAQ:AMD', 'AMD']],
      chartType: 'candlestick',
      showVolume: false,
      showMA: true,
      autosize: false,
      height: 520,
      locale: 'en',
    };

    render(<TradingViewSymbolOverview config={config} height={460} theme="dark" />);

    await waitFor(() => {
      const script = document.querySelector<HTMLScriptElement>('.tradingview-widget-container__widget script');
      expect(script).not.toBeNull();
    });

    const script = document.querySelector<HTMLScriptElement>('.tradingview-widget-container__widget script');
    expect(script).not.toBeNull();
    if (!script) {
      return;
    }

    expect(script.src).toBe('https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js');

    const payload = JSON.parse(script.innerHTML);
    expect(payload.height).toBe(460);
    expect(payload.width).toBe('100%');
    expect(payload.chartType).toBe('candlesticks');
    expect(payload.colorTheme).toBe('dark');
    expect(payload.symbols).toEqual([['NASDAQ:NVDA', 'NASDAQ:NVDA']]);
    expect(payload.showVolume).toBe(false);
    expect(payload.showMA).toBe(true);
    expect(payload.autosize).toBe(false);
  });
});
