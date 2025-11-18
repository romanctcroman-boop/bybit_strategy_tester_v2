import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
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
import { Visibility, VisibilityOff, Lock, Person, Email } from '@mui/icons-material';
import apiClient from '../services/api';
import { saveTokens } from '../services/auth';
import { useAuth } from '../contexts/AuthContext';

export default function RegisterPage() {
  const navigate = useNavigate();
  const { login: contextLogin, isAuthenticated } = useAuth();
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [registrationAttempted, setRegistrationAttempted] = useState(false);

  // Navigate to home when authentication state changes to true AFTER registration attempt
  useEffect(() => {
    if (isAuthenticated && registrationAttempted) {
      navigate('/', { replace: true });
    }
  }, [isAuthenticated, registrationAttempted, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validation
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }

    setLoading(true);
    setRegistrationAttempted(true);

    try {
      const response = await apiClient.post('/auth/register', {
        username,
        password,
        email: email || undefined,
      });

      // Save tokens
      saveTokens(response.data);

      // Update AuthContext - sets isAuthenticated=true
      await contextLogin();

      // Navigation will happen automatically via useEffect when isAuthenticated becomes true
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || 'Registration failed. Please try again.';
      setError(errorMessage);
      setRegistrationAttempted(false); // Reset on error
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
                Create Account
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Register for Bybit Strategy Tester
              </Typography>
            </Box>

            {/* Error Alert */}
            {error && (
              <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
                {error}
              </Alert>
            )}

            {/* Registration Form */}
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
                label="Email (optional)"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loading}
                margin="normal"
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <Email />
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
                helperText="At least 6 characters"
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
                        aria-label={showPassword ? 'Hide' : 'Show'}
                      >
                        {showPassword ? <VisibilityOff /> : <Visibility />}
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
              />

              <TextField
                fullWidth
                label="Confirm Password"
                type={showPassword ? 'text' : 'password'}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                disabled={loading}
                required
                margin="normal"
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <Lock />
                    </InputAdornment>
                  ),
                }}
              />

              <Button
                type="submit"
                fullWidth
                variant="contained"
                size="large"
                disabled={loading || !username || !password || !confirmPassword}
                sx={{ mt: 3, mb: 2, height: 48 }}
              >
                {loading ? <CircularProgress size={24} color="inherit" /> : 'Register'}
              </Button>
            </form>

            {/* Login Link */}
            <Box sx={{ textAlign: 'center', mt: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Already have an account?{' '}
                <Link
                  to="/login"
                  style={{ textDecoration: 'none', color: '#1976d2', fontWeight: 500 }}
                >
                  Login here
                </Link>
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
              Protected by bcrypt password hashing
            </Typography>
          </CardContent>
        </Card>
      </Box>
    </Container>
  );
}
