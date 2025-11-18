import React from 'react';

type Theme = 'light' | 'dark';
interface Props {
  symbol?: string; // e.g. BINANCE:BTCUSDT
  interval?: string; // '1','5','15','60','240','D','W'
  theme?: Theme;
  timezone?: string; // 'Etc/UTC'
  locale?: string; // 'en'
}

// Minimal, robust TradingView embed via iframe. This avoids loading tv.js on our origin.
const TradingViewIframe: React.FC<Props> = ({
  symbol = 'BINANCE:BTCUSDT',
  interval = '60',
  theme = 'dark',
  timezone = 'Etc/UTC',
  locale = 'en',
}) => {
  // TradingView accepts these query params for widgetembed; keep it minimal for compatibility
  const params = new URLSearchParams({
    symbol,
    interval,
    theme: theme === 'dark' ? 'Dark' : 'Light',
    style: '1', // bars = 1 (same as default candle style for widgetembed)
    hide_side_toolbar: '0',
    hide_top_toolbar: '0',
    allow_symbol_change: '1',
    saveimage: '0',
    studies: '',
    timezone,
    locale,
    // A few UX flags
    withdateranges: '1',
    hideideas: '1',
  });

  const src = `https://s.tradingview.com/widgetembed/?${params.toString()}`;
  const key = `${symbol}:${interval}:${theme}:${timezone}:${locale}`;

  return (
    <iframe
      key={key}
      title={`TradingView ${symbol}`}
      src={src}
      style={{ width: '100%', height: '100%', border: '0' }}
      allow="clipboard-write; fullscreen; autoplay"
      referrerPolicy="no-referrer-when-downgrade"
      sandbox="allow-same-origin allow-forms allow-popups allow-scripts allow-presentation"
    />
  );
};

export default TradingViewIframe;
