/**
 * Dashboard Component - Entry point
 * Uses DashboardLayout with 4-zone architecture (Green/DarkBlue/Teal/Purple)
 */

import React from 'react';
import DashboardLayout from './DashboardLayout';

interface DashboardProps {
  strategyName?: string;
  timeframe?: string;
}

const Dashboard: React.FC<DashboardProps> = () => {
  // DashboardLayout handles all state management and layout
  return <DashboardLayout />;
};

export default Dashboard;
