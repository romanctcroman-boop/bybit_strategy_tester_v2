import React from 'react';
import './Footer.css';

const DashboardFooter: React.FC = () => {
  const currentDate = new Date().toLocaleString('ru-RU', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <footer className="dashboard-footer">
      <div className="footer-left">
        <span className="footer-label">Data Range:</span>
        <span className="footer-value">2024-01-01 to 2024-10-29</span>
        <span className="footer-separator">|</span>
        <span className="footer-label">Total Bars:</span>
        <span className="footer-value">44,000</span>
        <span className="footer-separator">|</span>
        <span className="footer-label">WFO Periods:</span>
        <span className="footer-value">22 cycles</span>
      </div>

      <div className="footer-center">
        <div className="status-message">
          <span className="status-icon">✓</span>
          <span>All strategies validated • Ready for analysis</span>
        </div>
      </div>

      <div className="footer-right">
        <span className="footer-label">Last Update:</span>
        <span className="footer-value">{currentDate}</span>
      </div>
    </footer>
  );
};

export default DashboardFooter;
