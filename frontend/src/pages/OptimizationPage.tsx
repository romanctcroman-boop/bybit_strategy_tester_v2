import React from 'react';
import { Box, Typography, Paper } from '@mui/material';

const OptimizationPage: React.FC = () => {
  return (
    <Box>
      <Typography variant="h4" gutterBottom fontWeight="bold">
        🎯 Optimization
      </Typography>
      <Paper sx={{ p: 3, mt: 3 }}>
        <Typography variant="body1" color="text.secondary">
          Optimization page - coming soon
        </Typography>
      </Paper>
    </Box>
  );
};

export default OptimizationPage;
