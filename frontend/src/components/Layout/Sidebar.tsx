import React from 'react';
import {
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Divider,
  Box,
  Typography,
} from '@mui/material';
import { Link, useLocation } from 'react-router-dom';
import {
  Dashboard as DashboardIcon,
  TrendingUp as OptimizeIcon,
  Assessment as BacktestIcon,
  Settings as SettingsIcon,
  DataObject as DataIcon,
} from '@mui/icons-material';

interface MenuItem {
  text: string;
  icon: React.ReactElement;
  path: string;
}

const menuItems: MenuItem[] = [
  { text: 'Dashboard', icon: <DashboardIcon />, path: '/' },
  { text: 'Optimization', icon: <OptimizeIcon />, path: '/optimization' },
  { text: 'Backtest', icon: <BacktestIcon />, path: '/backtest' },
  { text: 'Market Data', icon: <DataIcon />, path: '/data' },
  { text: 'Settings', icon: <SettingsIcon />, path: '/settings' },
];

const Sidebar: React.FC = () => {
  const location = useLocation();

  return (
    <Box sx={{ overflow: 'auto' }}>
      {/* Menu Section */}
      <List>
        {menuItems.map((item) => {
          const isActive = location.pathname === item.path;

          return (
            <ListItem key={item.text} disablePadding>
              <ListItemButton
                component={Link}
                to={item.path}
                selected={isActive}
                sx={{
                  '&.Mui-selected': {
                    backgroundColor: 'primary.main',
                    color: 'white',
                    '&:hover': {
                      backgroundColor: 'primary.dark',
                    },
                    '& .MuiListItemIcon-root': {
                      color: 'white',
                    },
                  },
                }}
              >
                <ListItemIcon
                  sx={{
                    color: isActive ? 'inherit' : 'action.active',
                  }}
                >
                  {item.icon}
                </ListItemIcon>
                <ListItemText
                  primary={item.text}
                  primaryTypographyProps={{
                    fontWeight: isActive ? 'bold' : 'normal',
                  }}
                />
              </ListItemButton>
            </ListItem>
          );
        })}
      </List>

      <Divider sx={{ my: 2 }} />

      {/* Footer Info */}
      <Box sx={{ p: 2, textAlign: 'center' }}>
        <Typography variant="caption" color="text.secondary">
          Backend Testing Tool
        </Typography>
        <Typography variant="caption" display="block" color="text.secondary">
          Phase 3: Frontend UI
        </Typography>
      </Box>
    </Box>
  );
};

export default Sidebar;
