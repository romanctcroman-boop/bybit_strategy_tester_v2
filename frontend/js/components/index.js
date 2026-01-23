/**
 * 🧩 Components Index - Bybit Strategy Tester v2
 *
 * Central export point for all UI components.
 * Part of Phase 2: Architecture Modernization
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

// Base component
export { Component } from './Component.js';

// UI Components
export { Modal, confirm, alert } from './Modal.js';
export { Toast, toast } from './Toast.js';
export { DataTable } from './DataTable.js';
export { Form } from './Form.js';
export { Card } from './Card.js';
export { Loader, showLoading, hideLoading, LoadingState } from './Loader.js';

// Component factory for dynamic component creation
export function createComponent(type, options = {}) {
    const componentMap = {
        modal: Modal,
        toast: Toast,
        table: DataTable,
        form: Form,
        card: Card,
        loader: Loader
    };

    const ComponentClass = componentMap[type.toLowerCase()];
    if (!ComponentClass) {
        console.warn(`Unknown component type: ${type}`);
        return null;
    }

    return new ComponentClass(options);
}

// Import for named imports
import { Modal } from './Modal.js';
import { Toast } from './Toast.js';
import { DataTable } from './DataTable.js';
import { Form } from './Form.js';
import { Card } from './Card.js';
import { Loader } from './Loader.js';

// Default export with all components
export default {
    Modal,
    Toast,
    DataTable,
    Form,
    Card,
    Loader,
    createComponent
};
