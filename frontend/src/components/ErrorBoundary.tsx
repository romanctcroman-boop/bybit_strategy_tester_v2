/**
 * ErrorBoundary - Global error boundary component
 *
 * Catches JavaScript errors in child component tree and displays fallback UI.
 * Based on Perplexity AI recommendations for production React 18 apps.
 *
 * Features:
 * - TypeScript interfaces for type safety
 * - Custom fallback UI support
 * - Error logging callback (for Sentry, Datadog, etc.)
 * - Detailed error info in development mode
 */

import React, { Component, ErrorInfo, ReactNode } from 'react';
import { Alert, AlertTitle, Box, Button, Paper, Typography } from '@mui/material';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import RefreshIcon from '@mui/icons-material/Refresh';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: (error: Error, errorInfo: ErrorInfo) => ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  resetKeys?: unknown[]; // Dependencies that trigger reset
}

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
  errorInfo?: ErrorInfo;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ errorInfo });

    // Call optional error handler (for logging to external services)
    this.props.onError?.(error, errorInfo);

    // Log to console in development
    if (import.meta.env.DEV) {
      console.error('ErrorBoundary caught an error:', error, errorInfo);
    }
  }

  componentDidUpdate(prevProps: ErrorBoundaryProps) {
    // Reset error state when resetKeys change
    if (this.state.hasError && prevProps.resetKeys !== this.props.resetKeys) {
      this.setState({ hasError: false, error: undefined, errorInfo: undefined });
    }
  }

  handleReset = () => {
    this.setState({ hasError: false, error: undefined, errorInfo: undefined });
  };

  render() {
    if (this.state.hasError && this.state.error) {
      // Use custom fallback if provided
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.state.errorInfo!);
      }

      // Default fallback UI
      return (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: 400,
            p: 3,
          }}
        >
          <Paper
            elevation={3}
            sx={{
              maxWidth: 600,
              width: '100%',
              p: 4,
              textAlign: 'center',
            }}
          >
            <ErrorOutlineIcon
              sx={{
                fontSize: 64,
                color: 'error.main',
                mb: 2,
              }}
            />

            <Typography variant="h5" gutterBottom>
              Что-то пошло не так
            </Typography>

            <Alert severity="error" sx={{ mt: 2, mb: 3, textAlign: 'left' }}>
              <AlertTitle>Ошибка приложения</AlertTitle>
              <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                {this.state.error.message}
              </Typography>
            </Alert>

            {import.meta.env.DEV && this.state.errorInfo && (
              <Box
                sx={{
                  mt: 2,
                  p: 2,
                  bgcolor: 'grey.100',
                  borderRadius: 1,
                  textAlign: 'left',
                  maxHeight: 200,
                  overflow: 'auto',
                }}
              >
                <Typography variant="caption" component="pre" sx={{ fontSize: 10 }}>
                  {this.state.errorInfo.componentStack}
                </Typography>
              </Box>
            )}

            <Button
              variant="contained"
              color="primary"
              startIcon={<RefreshIcon />}
              onClick={this.handleReset}
              sx={{ mt: 3 }}
            >
              Попробовать снова
            </Button>
          </Paper>
        </Box>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
