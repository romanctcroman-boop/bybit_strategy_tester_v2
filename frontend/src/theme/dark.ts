/**
 * Dark Theme Configuration
 * Material-UI Theme for dark mode
 */

import { createTheme, Theme } from '@mui/material/styles';

export const darkTheme: Theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#90caf9', // Light blue for dark mode
      light: '#e3f2fd',
      dark: '#42a5f5',
      contrastText: '#000',
    },
    secondary: {
      main: '#ce93d8', // Light purple for AI features
      light: '#f3e5f5',
      dark: '#ab47bc',
      contrastText: '#000',
    },
    background: {
      default: '#121212', // True dark background
      paper: '#1e1e1e', // Slightly lighter for cards
    },
    text: {
      primary: '#ffffff',
      secondary: 'rgba(255, 255, 255, 0.7)',
    },
    success: {
      main: '#66bb6a', // Softer green for dark mode
      light: '#81c784',
      dark: '#388e3c',
    },
    error: {
      main: '#f44336', // Softer red for dark mode
      light: '#e57373',
      dark: '#d32f2f',
    },
    warning: {
      main: '#ffa726',
      light: '#ffb74d',
      dark: '#f57c00',
    },
    info: {
      main: '#29b6f6',
      light: '#4fc3f7',
      dark: '#0288d1',
    },
    divider: 'rgba(255, 255, 255, 0.12)',
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
    h4: {
      fontWeight: 600,
    },
    h5: {
      fontWeight: 600,
    },
    h6: {
      fontWeight: 600,
    },
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          backgroundColor: '#1e1e1e',
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          boxShadow: '0 2px 8px rgba(0,0,0,0.5)',
          backgroundColor: '#1e1e1e',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: '#1e1e1e',
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: '#1e1e1e',
        },
      },
    },
  },
});
