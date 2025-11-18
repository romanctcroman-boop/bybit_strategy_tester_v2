import React from 'react';
import { Container, Box } from '@mui/material';
import OrchestratorDashboard from '../components/OrchestratorDashboard';

/**
 * Orchestrator Dashboard Page
 *
 * Displays:
 * - Plugin Manager status
 * - Priority System statistics
 * - System health monitoring
 * - Hot reload controls
 */
const OrchestratorPage: React.FC = () => {
  return (
    <Container maxWidth="xl">
      <Box sx={{ py: 4 }}>
        <OrchestratorDashboard />
      </Box>
    </Container>
  );
};

export default OrchestratorPage;
