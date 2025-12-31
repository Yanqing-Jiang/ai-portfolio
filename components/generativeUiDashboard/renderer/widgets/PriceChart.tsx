/**
 * PriceChart Widget
 *
 * TradingView-powered candlestick chart for stock price visualization.
 */

import React, { useEffect, useRef } from 'react';
import type { A2UIRendererProps } from '../Registry';
import { resolveString, resolveBoolean } from '../../a2ui/DataBinder';
import type { PriceChartProps } from '../../a2ui/types';

// TradingView script URL
const TRADINGVIEW_SCRIPT_URL = 'https://s3.tradingview.com/tv.js';

export function PriceChart({
    componentId,
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement {
    const chartProps = props as unknown as PriceChartProps;
    const containerRef = useRef<HTMLDivElement>(null);
    const widgetRef = useRef<unknown>(null);

    const ticker = resolveString(chartProps.ticker, dataModel, 'NVDA');
    const interval = resolveString(chartProps.interval, dataModel, '1D');
    const showVolume = resolveBoolean(chartProps.showVolume, dataModel, true);

    // Map interval to TradingView format
    const getInterval = (int: string): string => {
        const map: Record<string, string> = {
            '1D': 'D',
            '1W': 'W',
            '1M': 'M',
            '3M': '3M',
            '6M': '6M',
            '1Y': '12M',
            '5Y': '60M',
        };
        return map[int] || 'D';
    };

    useEffect(() => {
        // Load TradingView script
        const loadScript = (): Promise<void> => {
            return new Promise((resolve, reject) => {
                const win = window as any;
                if (win.TradingView) {
                    resolve();
                    return;
                }

                const script = document.createElement('script');
                script.src = TRADINGVIEW_SCRIPT_URL;
                script.async = true;
                script.onload = () => resolve();
                script.onerror = reject;
                document.head.appendChild(script);
            });
        };

        const initWidget = async () => {
            if (!containerRef.current) return;

            try {
                await loadScript();

                // Clear previous widget
                if (containerRef.current) {
                    containerRef.current.innerHTML = '';
                }

                // Create new widget
                const TradingView = (window as any).TradingView;

                widgetRef.current = new TradingView.widget({
                    autosize: true,
                    symbol: ticker,
                    interval: getInterval(interval),
                    timezone: 'Etc/UTC',
                    theme: 'dark',
                    style: '1', // Candlestick
                    locale: 'en',
                    toolbar_bg: '#1e293b',
                    enable_publishing: false,
                    hide_top_toolbar: false,
                    hide_legend: false,
                    save_image: false,
                    container_id: containerRef.current.id,
                    studies: showVolume ? ['Volume@tv-basicstudies'] : [],
                });
            } catch (error) {
                console.error('Failed to load TradingView widget:', error);
            }
        };

        initWidget();
    }, [ticker, interval, showVolume]);

    const containerId = `tradingview_${componentId}`;

    return (
        <div
            className="a2ui-price-chart"
            data-component-id={componentId}
            style={{
                width: '100%',
                aspectRatio: '16 / 9',
                maxHeight: '450px',
                backgroundColor: 'rgba(15, 23, 42, 0.5)',
                borderRadius: '12px',
                overflow: 'hidden',
                border: '1px solid rgba(148, 163, 184, 0.1)',
            }}
        >
            <div
                id={containerId}
                ref={containerRef}
                style={{ width: '100%', height: '100%' }}
            />
        </div>
    );
}
