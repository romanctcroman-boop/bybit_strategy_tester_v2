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
  onReady?: () => void;
  onFail?: () => void;
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
  onReady,
  onFail,
}) => {
  const ref = useRef<HTMLDivElement | null>(null);
  const [initialized, setInitialized] = React.useState(false);
  const [failed, setFailed] = React.useState(false);

  useEffect(() => {
    let cancelled = false;
    const scriptId = 'tradingview-widget-script';

    // Render when TradingView is finally ready; retry a few times in case the script exists but isn't initialized yet
    const tryRender = (attempt = 0) => {
      if (cancelled) return;
      try {
        const tv = (window as any).TradingView;
        const widget = tv && tv.widget;
        if (!widget) {
          if (attempt < 30) {
            // retry up to ~6s total
            setTimeout(() => tryRender(attempt + 1), 200);
          }
          return;
        }
        // clear container and render
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
        setInitialized(true);
        try {
          if (typeof onReady === 'function') onReady();
        } catch {}
      } catch {
        // ignore; some environments may block the widget
      }
    };

    const ensureScriptAndRender = () => {
      if ((window as any).TradingView) {
        tryRender();
        return;
      }
      const existing = document.getElementById(scriptId) as HTMLScriptElement | null;
      if (existing) {
        // If the tag exists but TradingView is not ready yet, attach a one-time onload fallback and also start retries
        if (!existing.onload) existing.onload = () => tryRender();
        tryRender();
        return;
      }
      const script = document.createElement('script');
      script.id = scriptId;
      script.src = 'https://s3.tradingview.com/tv.js';
      script.async = true;
      script.onload = () => tryRender();
      document.head.appendChild(script);
    };

    ensureScriptAndRender();

    // Mark failure if still not initialized after timeout
    const failTimer = window.setTimeout(() => {
      if (!cancelled && !initialized) {
        setFailed(true);
        try {
          if (typeof onFail === 'function') onFail();
        } catch {}
      }
    }, 7000);

    return () => {
      cancelled = true;
      window.clearTimeout(failTimer);
    };
  }, [
    symbol,
    interval,
    theme,
    studies,
    timezone,
    locale,
    allowSymbolChange,
    containerId,
    initialized,
    onReady,
    onFail,
  ]);

  return (
    <div style={{ width: '100%', height: '100%', minHeight: 320, position: 'relative' }}>
      <div id={containerId} ref={ref} style={{ width: '100%', height: '100%' }} />
      {failed && !initialized && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 16,
            color: '#999',
            textAlign: 'center',
          }}
        >
          <div>
            <div style={{ marginBottom: 8 }}>Не удалось загрузить TradingView виджет.</div>
            <div style={{ fontSize: 13, lineHeight: 1.6 }}>
              Проверьте в браузере доступ к https://s3.tradingview.com/tv.js, отключите блокировщики
              рекламы для localhost и попробуйте перезагрузить страницу.
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TradingViewWidget;
