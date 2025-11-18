import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Box, CircularProgress, Typography } from '@mui/material';
import { useAuth } from '../contexts/AuthContext';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredScopes?: string[];
}

export default function ProtectedRoute({ children, requiredScopes }: ProtectedRouteProps) {
  const { isAuthenticated, loading, user } = useAuth();
  const location = useLocation();

  // Show loading spinner while checking auth
  if (loading) {
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          gap: 2,
        }}
      >
        <CircularProgress size={48} />
        <Typography variant="body2" color="text.secondary">
          Checking authentication...
        </Typography>
      </Box>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Check required scopes if specified
  if (requiredScopes && requiredScopes.length > 0) {
    const userScopes = user?.scopes || [];
    const hasRequiredScopes = requiredScopes.every((scope) => userScopes.includes(scope));

    if (!hasRequiredScopes) {
      return (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '100vh',
            gap: 2,
            p: 3,
            textAlign: 'center',
          }}
        >
          <Typography variant="h5" color="error">
            Access Denied
          </Typography>
          <Typography variant="body1" color="text.secondary">
            You don&apos;t have permission to access this page.
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Required scopes: {requiredScopes.join(', ')}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Your scopes: {userScopes.join(', ') || 'none'}
          </Typography>
        </Box>
      );
    }
  }

  return <>{children}</>;
}
