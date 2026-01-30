/**
 * 🧩 Components Index - Bybit Strategy Tester v2
 *
 * Central export point for all UI components.
 * Part of Phase 2: Architecture Modernization
 *
 * @version 1.1.0
 * @date 2026-01-24
 */

// Base component
export { Component } from "./Component.js";

// UI Components
export { Modal, confirm, alert } from "./Modal.js";
export { Toast, toast } from "./Toast.js";
export { DataTable } from "./DataTable.js";
export { Form } from "./Form.js";
export { Card } from "./Card.js";
export { Loader, showLoading, hideLoading, LoadingState } from "./Loader.js";

// Chart Components
export { TradingViewEquityChart } from "./TradingViewEquityChart.js";
export { MonteCarloChart } from "./MonteCarloChart.js";
export { OptimizationHeatmap } from "./OptimizationHeatmap.js";
export { ParameterSensitivityChart } from "./ParameterSensitivityChart.js";

// Component factory for dynamic component creation
export function createComponent(type, options = {}) {
  const componentMap = {
    modal: Modal,
    toast: Toast,
    table: DataTable,
    form: Form,
    card: Card,
    loader: Loader,
    monteCarlo: MonteCarloChart,
    heatmap: OptimizationHeatmap,
    sensitivity: ParameterSensitivityChart,
  };

  const ComponentClass = componentMap[type.toLowerCase()];
  if (!ComponentClass) {
    console.warn(`Unknown component type: ${type}`);
    return null;
  }

  return new ComponentClass(options);
}

// Import for named imports
import { Modal } from "./Modal.js";
import { Toast } from "./Toast.js";
import { DataTable } from "./DataTable.js";
import { Form } from "./Form.js";
import { Card } from "./Card.js";
import { Loader } from "./Loader.js";
import { MonteCarloChart } from "./MonteCarloChart.js";
import { OptimizationHeatmap } from "./OptimizationHeatmap.js";
import { ParameterSensitivityChart } from "./ParameterSensitivityChart.js";

// Default export with all components
export default {
  Modal,
  Toast,
  DataTable,
  Form,
  Card,
  Loader,
  MonteCarloChart,
  OptimizationHeatmap,
  ParameterSensitivityChart,
  createComponent,
};
