/**
 * GlobalProviders - Wrapper for all global providers
 *
 * Combines:
 * - SnackbarProvider (notistack) for toast notifications
 * - NotificationsProvider (existing custom notifications)
 * - ErrorBoundary for error catching
 *
 * Usage: Wrap the entire app with this component in main.tsx
 */

import React, { ReactNode } from 'react';
import { SnackbarProvider } from 'notistack';
import { IconButton } from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import ErrorBoundary from './ErrorBoundary';
import NotificationsProvider from './NotificationsProvider';

interface GlobalProvidersProps {
  children: ReactNode;
}

const GlobalProviders: React.FC<GlobalProvidersProps> = ({ children }) => {
  // Create a ref for SnackbarProvider to enable close actions
  const notistackRef = React.createRef<any>();

  const onClickDismiss = (key: string | number) => () => {
    notistackRef.current?.closeSnackbar(key);
  };

  return (
    <ErrorBoundary
      onError={(error, errorInfo) => {
        // Log errors to external service (Sentry, Datadog, etc.)
        if (import.meta.env.PROD) {
          console.error('Production error:', error, errorInfo);
          // TODO: Send to error tracking service
        }
      }}
    >
      <SnackbarProvider
        ref={notistackRef}
        maxSnack={3}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        autoHideDuration={5000}
        preventDuplicate
        action={(snackbarKey) => (
          <IconButton
            size="small"
            aria-label="close"
            color="inherit"
            onClick={onClickDismiss(snackbarKey)}
          >
            <CloseIcon fontSize="small" />
          </IconButton>
        )}
      >
        <NotificationsProvider>{children}</NotificationsProvider>
      </SnackbarProvider>
    </ErrorBoundary>
  );
};

export default GlobalProviders;
