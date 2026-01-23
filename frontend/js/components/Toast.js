/**
 * 🔔 Toast Component - Bybit Strategy Tester v2
 *
 * Reusable toast notification system with stacking,
 * auto-dismiss, and various types (success, error, warning, info).
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

import { Component } from './Component.js';

// Toast container singleton
let toastContainer = null;

/**
 * Get or create the toast container
 * @returns {HTMLElement}
 */
function getToastContainer() {
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
        toastContainer.style.zIndex = '10050';
        document.body.appendChild(toastContainer);
    }
    return toastContainer;
}

/**
 * Toast notification component
 */
export class Toast extends Component {
    defaultProps() {
        return {
            title: '',
            message: '',
            type: 'info', // success, error, warning, info
            duration: 5000, // 0 for no auto-dismiss
            closable: true,
            icon: null,
            position: 'top-right', // top-right, top-left, bottom-right, bottom-left, top-center, bottom-center
            animation: true,
            onClose: null
        };
    }

    defaultState() {
        return {
            visible: false,
            progress: 100
        };
    }

    constructor(options = {}) {
        super({
            ...options,
            container: getToastContainer(),
            autoMount: true
        });
        this._timeout = null;
        this._progressInterval = null;
    }

    render() {
        const { title, message, type, closable, icon } = this.props;

        // Type-specific configuration
        const typeConfig = {
            success: { icon: 'bi-check-circle-fill', color: 'text-success', bg: 'bg-success' },
            error: { icon: 'bi-x-circle-fill', color: 'text-danger', bg: 'bg-danger' },
            warning: { icon: 'bi-exclamation-triangle-fill', color: 'text-warning', bg: 'bg-warning' },
            info: { icon: 'bi-info-circle-fill', color: 'text-info', bg: 'bg-info' }
        };

        const config = typeConfig[type] || typeConfig.info;
        const iconClass = icon || config.icon;

        // Toast element
        const toast = this.h('div', {
            className: `toast ${this.state.visible ? 'show' : ''} border-0`,
            role: 'alert',
            'aria-live': 'assertive',
            'aria-atomic': 'true'
        },
        // Header
        this.h('div', { className: 'toast-header' },
            this.h('i', { className: `bi ${iconClass} ${config.color} me-2` }),
            this.h('strong', { className: 'me-auto' }, title || this._getDefaultTitle(type)),
            this.h('small', { className: 'text-muted' }, 'just now'),
            closable ? this.h('button', {
                type: 'button',
                className: 'btn-close',
                'aria-label': 'Close',
                onClick: () => this.hide()
            }) : null
        ),
        // Body
        this.h('div', { className: 'toast-body' }, message),
        // Progress bar
        this.props.duration > 0 ? this.h('div', {
            className: 'toast-progress',
            style: {
                position: 'absolute',
                bottom: '0',
                left: '0',
                height: '3px',
                width: `${this.state.progress}%`,
                backgroundColor: config.bg.replace('bg-', 'var(--bs-'),
                transition: 'width 100ms linear'
            }
        }) : null
        );

        return toast;
    }

    _getDefaultTitle(type) {
        const titles = {
            success: 'Success',
            error: 'Error',
            warning: 'Warning',
            info: 'Info'
        };
        return titles[type] || 'Notification';
    }

    afterMount() {
        // Show with animation
        requestAnimationFrame(() => {
            this.show();
        });
    }

    /**
     * Show the toast
     * @returns {Toast}
     */
    show() {
        this.setState({ visible: true });

        // Auto-dismiss
        if (this.props.duration > 0) {
            this._startProgress();

            this._timeout = setTimeout(() => {
                this.hide();
            }, this.props.duration);
        }

        return this;
    }

    /**
     * Hide the toast
     * @returns {Toast}
     */
    hide() {
        this._stopProgress();

        if (this._timeout) {
            clearTimeout(this._timeout);
            this._timeout = null;
        }

        this.setState({ visible: false });

        // Remove after animation
        setTimeout(() => {
            if (this.props.onClose) {
                this.props.onClose(this);
            }
            this.unmount();
        }, 300);

        return this;
    }

    _startProgress() {
        const { duration } = this.props;
        const interval = 100;
        const decrement = (interval / duration) * 100;

        this._progressInterval = setInterval(() => {
            const newProgress = Math.max(0, this.state.progress - decrement);
            this.setState({ progress: newProgress }, false);

            // Update progress bar directly for smoother animation
            const progressBar = this.find('.toast-progress');
            if (progressBar) {
                progressBar.style.width = `${newProgress}%`;
            }
        }, interval);
    }

    _stopProgress() {
        if (this._progressInterval) {
            clearInterval(this._progressInterval);
            this._progressInterval = null;
        }
    }
}

/**
 * Toast manager for easy access
 */
export const toast = {
    /**
     * Show a success toast
     * @param {string} message - Toast message
     * @param {Object} options - Additional options
     * @returns {Toast}
     */
    success(message, options = {}) {
        return new Toast({
            props: {
                type: 'success',
                message,
                title: options.title || 'Success',
                ...options
            }
        });
    },

    /**
     * Show an error toast
     * @param {string} message - Toast message
     * @param {Object} options - Additional options
     * @returns {Toast}
     */
    error(message, options = {}) {
        return new Toast({
            props: {
                type: 'error',
                message,
                title: options.title || 'Error',
                duration: options.duration || 8000, // Longer for errors
                ...options
            }
        });
    },

    /**
     * Show a warning toast
     * @param {string} message - Toast message
     * @param {Object} options - Additional options
     * @returns {Toast}
     */
    warning(message, options = {}) {
        return new Toast({
            props: {
                type: 'warning',
                message,
                title: options.title || 'Warning',
                ...options
            }
        });
    },

    /**
     * Show an info toast
     * @param {string} message - Toast message
     * @param {Object} options - Additional options
     * @returns {Toast}
     */
    info(message, options = {}) {
        return new Toast({
            props: {
                type: 'info',
                message,
                title: options.title || 'Info',
                ...options
            }
        });
    },

    /**
     * Clear all toasts
     */
    clear() {
        const container = getToastContainer();
        while (container.firstChild) {
            container.removeChild(container.firstChild);
        }
    }
};

export default Toast;
