import React, { Component, ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';
import App from './App';

// Simple error boundary to reveal runtime errors inside the Simple Browser
class ErrorBoundary extends Component<{ children: ReactNode }, { error?: any }> {
	state = { error: undefined as any };
	static getDerivedStateFromError(error: any) {
		return { error };
	}
	componentDidCatch(error: any, info: any) {
		// also log to an on-page console for environments without dev overlay
		const box = document.getElementById('debug-log');
		if (box) {
			box.style.display = 'block';
			box.textContent = `Runtime error: ${error?.message || error}\n${info?.componentStack || ''}`;
		}
	}
	render() {
		if (this.state.error) {
			return (
				<div style={{ padding: 16 }}>
					<h2>Runtime error</h2>
					<pre style={{ whiteSpace: 'pre-wrap' }}>{String(this.state.error?.message || this.state.error)}</pre>
				</div>
			);
		}
		return this.props.children;
	}
}

// Attach global error listeners to print into a debug pre element
function attachGlobalErrorHooks() {
	const ensureBox = () => {
		let el = document.getElementById('debug-log');
		if (!el) {
			el = document.createElement('pre');
			el.id = 'debug-log';
			el.style.cssText = 'display:none;position:fixed;bottom:0;left:0;right:0;max-height:40vh;overflow:auto;background:#111;color:#f55;padding:8px;margin:0;z-index:9999;';
			document.body.appendChild(el);
		}
		return el as HTMLElement;
	};
	const box = ensureBox();
	const log = (msg: string) => {
		box.style.display = 'block';
		box.textContent = (box.textContent || '') + '\n' + msg;
	};
	window.addEventListener('error', (e) => log('error: ' + (e.error?.message || e.message)));
	window.addEventListener('unhandledrejection', (e: any) => log('unhandledrejection: ' + (e.reason?.message || String(e.reason))));
}

attachGlobalErrorHooks();

const rootEl = document.getElementById('root');
if (rootEl) {
	// render a quick visual heartbeat so we see that React mounts
	rootEl.setAttribute('data-boot', '1');
	rootEl.innerHTML = '<div style="padding:8px;font:14px sans-serif;color:#444">Booting UI...</div>';
}

const root = createRoot(rootEl!);

try {
	root.render(
		<ErrorBoundary>
			<App />
		</ErrorBoundary>
	);
} catch (e: any) {
	const box = document.getElementById('debug-log');
	if (box) {
		box.style.display = 'block';
		box.textContent = 'Failed to render App: ' + (e?.message || String(e));
	}
	if (rootEl) rootEl.innerHTML = '<div style="padding:8px;color:#b00020">Failed to render App: ' + (e?.message || String(e)) + '</div>';
}
