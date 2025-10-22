import React, { useEffect, useRef } from 'react';

type Theme = 'light' | 'dark';
interface TVWidgetProps {
  symbol?: string;
  interval?: string; // '1', '5', '60', '240', 'D', ...
  theme?: Theme;
  studies?: string[]; // e.g. ['MACD@tv-basicstudies', 'RSI@tv-basicstudies']
  timezone?: string;
  locale?: string;
  allowSymbolChange?: boolean;
  containerId?: string;
}

const TradingViewWidget: React.FC<TVWidgetProps> = ({
  symbol = 'BITSTAMP:BTCUSD',
  interval = '60',
  theme = 'light',
  studies = [],
  timezone = 'Etc/UTC',
  locale = 'en',
  allowSymbolChange = true,
  containerId = 'tv_chart',
}) => {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const scriptId = 'tradingview-widget-script';
    if ((window as any).TradingView) {
      // If already loaded, render widget
      tryRender();
      return;
    }

    if (document.getElementById(scriptId)) {
      tryRender();
      return;
    }

    const script = document.createElement('script');
    script.id = scriptId;
    script.src = 'https://s3.tradingview.com/tv.js';
    script.async = true;
    script.onload = () => tryRender();
    document.head.appendChild(script);

    function tryRender() {
      try {
        const widget = (window as any).TradingView && (window as any).TradingView.widget;
        if (!widget) return;
        // remove existing children
        if (ref.current) ref.current.innerHTML = '';
        widget({
          container_id: containerId,
          autosize: true,
          symbol,
          interval,
          timezone,
          theme,
          style: '1',
          locale,
          enable_publishing: false,
          allow_symbol_change: allowSymbolChange,
          details: true,
          studies,
        });
      } catch (e) {
        // fail silently; widget can't be rendered in some environments
        // console.warn('TradingView widget render failed', e);
      }
    }

    return () => {
      // no-op cleanup
    };
  }, [symbol, interval, theme, JSON.stringify(studies), timezone, locale, allowSymbolChange, containerId]);

  return <div id={containerId} ref={ref} style={{ width: '100%', height: 500 }} />;
};

export default TradingViewWidget;
