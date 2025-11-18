"""
Prometheus Exporter
===================

HTTP server that exposes /metrics endpoint for Prometheus scraping.
"""

import logging
from typing import Optional
from prometheus_client import start_http_server, REGISTRY, CollectorRegistry
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import threading

# Flask is optional - only needed for FlaskMetricsExporter
try:
    from flask import Flask, Response
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    Flask = None
    Response = None

logger = logging.getLogger(__name__)


class PrometheusExporter:
    """
    Prometheus metrics exporter.
    
    Provides HTTP endpoint for metrics scraping.
    """
    
    def __init__(self, port: int = 9090, host: str = '0.0.0.0'):
        """
        Initialize Prometheus exporter.
        
        Args:
            port: Port to listen on (default: 9090)
            host: Host to bind to (default: 0.0.0.0)
        """
        self.port = port
        self.host = host
        self.server_thread: Optional[threading.Thread] = None
        self.is_running = False
        
    def start(self):
        """Start metrics HTTP server."""
        if self.is_running:
            logger.warning(f"Prometheus exporter already running on port {self.port}")
            return
        
        try:
            # Start Prometheus HTTP server in separate thread
            self.server_thread = threading.Thread(
                target=self._run_server,
                daemon=True
            )
            self.server_thread.start()
            self.is_running = True
            
            logger.info(f"✅ Prometheus metrics server started on http://{self.host}:{self.port}/metrics")
            
        except Exception as e:
            logger.error(f"Failed to start Prometheus exporter: {e}")
            raise
    
    def _run_server(self):
        """Run HTTP server (internal method)."""
        start_http_server(self.port, addr=self.host)
    
    def stop(self):
        """Stop metrics server."""
        self.is_running = False
        logger.info("Prometheus metrics server stopped")


class FlaskMetricsExporter:
    """
    Flask-based metrics exporter.
    
    Alternative to standalone HTTP server, integrates with existing Flask app.
    Requires Flask to be installed.
    """
    
    def __init__(self, app: Optional['Flask'] = None, path: str = '/metrics'):
        """
        Initialize Flask metrics exporter.
        
        Args:
            app: Flask application instance
            path: URL path for metrics endpoint (default: /metrics)
        
        Raises:
            ImportError: If Flask is not installed
        """
        if not FLASK_AVAILABLE:
            raise ImportError(
                "Flask is required for FlaskMetricsExporter. "
                "Install it with: pip install flask"
            )
        
        self.app = app
        self.path = path
        
        if app:
            self.init_app(app)
    
    def init_app(self, app: 'Flask'):
        """
        Initialize metrics endpoint on Flask app.
        
        Args:
            app: Flask application instance
        """
        if not FLASK_AVAILABLE:
            raise ImportError("Flask is not installed")
        
        self.app = app
        
        @app.route(self.path)
        def metrics():
            """Metrics endpoint handler."""
            return Response(
                generate_latest(REGISTRY),
                mimetype=CONTENT_TYPE_LATEST
            )
        
        logger.info(f"✅ Prometheus metrics endpoint registered at {self.path}")


# ============================================================
# Helper Functions
# ============================================================

def start_metrics_server(port: int = 9090, host: str = '0.0.0.0') -> PrometheusExporter:
    """
    Convenience function to start metrics server.
    
    Args:
        port: Port to listen on
        host: Host to bind to
    
    Returns:
        PrometheusExporter instance
    """
    exporter = PrometheusExporter(port=port, host=host)
    exporter.start()
    return exporter


def register_flask_metrics(app: 'Flask', path: str = '/metrics') -> FlaskMetricsExporter:
    """
    Convenience function to register metrics on Flask app.
    
    Args:
        app: Flask application instance
        path: URL path for metrics endpoint
    
    Returns:
        FlaskMetricsExporter instance
    
    Raises:
        ImportError: If Flask is not installed
    """
    if not FLASK_AVAILABLE:
        raise ImportError(
            "Flask is required for Flask metrics integration. "
            "Install it with: pip install flask"
        )
    
    exporter = FlaskMetricsExporter(app=app, path=path)
    return exporter
