import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  TextField,
  Button,
  Typography,
  Alert,
  CircularProgress,
  Container,
  InputAdornment,
  IconButton,
} from '@mui/material';
import { Visibility, VisibilityOff, Lock, Person } from '@mui/icons-material';
import { login } from '../services/auth';
import { useAuth } from '../contexts/AuthContext';

export default function LoginPage() {
  const navigate = useNavigate();
  const { login: contextLogin, isAuthenticated } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loginAttempted, setLoginAttempted] = useState(false);

  // Navigate to home when authentication state changes to true AFTER login attempt
  useEffect(() => {
    if (isAuthenticated && loginAttempted) {
      navigate('/', { replace: true });
    }
  }, [isAuthenticated, loginAttempted, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    setLoginAttempted(true);

    try {
      await login(username, password);
      await contextLogin();
      // Navigation will happen automatically via useEffect when isAuthenticated becomes true
    } catch (err: any) {
      console.error('[LoginPage] Login error:', err);
      setError(err.message || 'Login failed. Please check your credentials.');
      setLoginAttempted(false); // Reset on error
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="sm">
      <Box
        sx={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Card sx={{ width: '100%', maxWidth: 450 }}>
          <CardContent sx={{ p: 4 }}>
            {/* Logo/Title */}
            <Box sx={{ textAlign: 'center', mb: 4 }}>
              <Typography variant="h4" component="h1" gutterBottom fontWeight="bold">
                Bybit Strategy Tester
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Phase 1 Security - JWT Authentication
              </Typography>
            </Box>

            {/* Error Alert */}
            {error && (
              <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
                {error}
              </Alert>
            )}

            {/* Login Form */}
            <form onSubmit={handleSubmit}>
              <TextField
                fullWidth
                label="Username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={loading}
                required
                autoFocus
                margin="normal"
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <Person />
                    </InputAdornment>
                  ),
                }}
              />

              <TextField
                fullWidth
                label="Password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loading}
                required
                margin="normal"
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <Lock />
                    </InputAdornment>
                  ),
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        onClick={() => setShowPassword(!showPassword)}
                        edge="end"
                        disabled={loading}
                        aria-label={showPassword ? 'Hide password' : 'Show password'}
                      >
                        {showPassword ? <VisibilityOff /> : <Visibility />}
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
              />

              <Button
                type="submit"
                fullWidth
                variant="contained"
                size="large"
                disabled={loading || !username || !password}
                sx={{ mt: 3, mb: 2, height: 48 }}
              >
                {loading ? <CircularProgress size={24} color="inherit" /> : 'Login'}
              </Button>
            </form>

            {/* Demo Credentials */}
            <Box sx={{ mt: 3, p: 2, bgcolor: 'action.hover', borderRadius: 1 }}>
              <Typography variant="caption" display="block" gutterBottom fontWeight="bold">
                Test Accounts:
              </Typography>
              <Typography variant="caption" display="block">
                Admin: admin / admin123
              </Typography>
              <Typography variant="caption" display="block">
                User: user / user123
              </Typography>
            </Box>

            {/* Register Link */}
            <Box sx={{ textAlign: 'center', mt: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Don&apos;t have an account?{' '}
                <a
                  href="/#/register"
                  style={{ textDecoration: 'none', color: '#1976d2', fontWeight: 500 }}
                >
                  Register here
                </a>
              </Typography>
            </Box>

            {/* Footer */}
            <Typography
              variant="caption"
              display="block"
              textAlign="center"
              sx={{ mt: 3 }}
              color="text.secondary"
            >
              Protected by JWT Bearer Authentication
            </Typography>
          </CardContent>
        </Card>
      </Box>
    </Container>
  );
}
