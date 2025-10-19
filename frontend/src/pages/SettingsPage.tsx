import React from 'react';
import { Box, Typography, Paper } from '@mui/material';

const SettingsPage: React.FC = () => {
  return (
    <Box>
      <Typography variant="h4" gutterBottom fontWeight="bold">
        ⚙️ Settings
      </Typography>
      <Paper sx={{ p: 3, mt: 3 }}>
        <Typography variant="body1" color="text.secondary">
          Settings page - coming soon
        </Typography>
      </Paper>
    </Box>
  );
};

export default SettingsPage;
