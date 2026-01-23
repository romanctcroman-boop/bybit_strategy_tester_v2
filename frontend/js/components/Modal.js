/**
 * 🪟 Modal Component - Bybit Strategy Tester v2
 *
 * Reusable modal dialog component with customizable content,
 * animations, and keyboard/click-outside handling.
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

import { Component } from './Component.js';

/**
 * Modal dialog component
 *
 * @example
 * const modal = new Modal({
 *     title: 'Confirm Action',
 *     content: 'Are you sure?',
 *     size: 'md',
 *     buttons: [
 *         { text: 'Cancel', variant: 'secondary', action: 'close' },
 *         { text: 'Confirm', variant: 'primary', action: () => doSomething() }
 *     ]
 * });
 * modal.show();
 */
export class Modal extends Component {
    defaultProps() {
        return {
            title: '',
            content: '',
            size: 'md', // sm, md, lg, xl, fullscreen
            closable: true,
            closeOnBackdrop: true,
            closeOnEscape: true,
            showHeader: true,
            showFooter: true,
            centered: true,
            scrollable: false,
            animation: true,
            buttons: [],
            customClass: '',
            onShow: null,
            onHide: null,
            onConfirm: null
        };
    }

    defaultState() {
        return {
            visible: false,
            loading: false
        };
    }

    render() {
        const { title: _title, size, centered, scrollable, showHeader, showFooter, customClass } = this.props;

        // Backdrop
        const backdrop = this.h('div', {
            className: `modal-backdrop fade ${this.state.visible ? 'show' : ''}`,
            onClick: (e) => this._handleBackdropClick(e)
        });

        // Modal content
        const modalContent = this.h('div', { className: 'modal-content' },
            showHeader ? this._renderHeader() : null,
            this._renderBody(),
            showFooter ? this._renderFooter() : null
        );

        // Modal dialog
        const modalDialog = this.h('div', {
            className: `modal-dialog modal-${size} ${centered ? 'modal-dialog-centered' : ''} ${scrollable ? 'modal-dialog-scrollable' : ''}`
        }, modalContent);

        // Modal wrapper
        const modal = this.h('div', {
            className: `modal fade ${this.state.visible ? 'show' : ''} ${customClass}`,
            tabindex: '-1',
            role: 'dialog',
            'aria-modal': 'true',
            'aria-labelledby': 'modalTitle',
            style: { display: this.state.visible ? 'block' : 'none' },
            onClick: (e) => this._handleBackdropClick(e)
        }, modalDialog);

        // Container
        const container = this.h('div', { className: 'modal-container' }, backdrop, modal);

        return container;
    }

    _renderHeader() {
        const { title, closable } = this.props;

        const closeBtn = closable ? this.h('button', {
            type: 'button',
            className: 'btn-close',
            'aria-label': 'Close',
            onClick: () => this.hide()
        }) : null;

        return this.h('div', { className: 'modal-header' },
            this.h('h5', { className: 'modal-title', id: 'modalTitle' }, title),
            closeBtn
        );
    }

    _renderBody() {
        const { content } = this.props;

        // Content can be string, HTMLElement, or Component
        let bodyContent;
        if (typeof content === 'string') {
            bodyContent = this.h('div', { className: 'modal-body-content' });
            bodyContent.innerHTML = content;
        } else if (content instanceof HTMLElement) {
            bodyContent = content;
        } else if (content instanceof Component) {
            bodyContent = content.element || content.render();
        } else {
            bodyContent = this.h('div', { className: 'modal-body-content' });
        }

        const body = this.h('div', { className: 'modal-body' });
        body.appendChild(bodyContent);

        // Loading overlay
        if (this.state.loading) {
            const loader = this.h('div', { className: 'modal-loading' },
                this.h('div', { className: 'spinner-border text-primary' }),
                this.h('span', { className: 'ms-2' }, 'Loading...')
            );
            body.appendChild(loader);
        }

        return body;
    }

    _renderFooter() {
        const { buttons, onConfirm } = this.props;

        // Default buttons if none provided
        const defaultButtons = buttons.length > 0 ? buttons : [
            { text: 'Close', variant: 'secondary', action: 'close' }
        ];

        const buttonElements = defaultButtons.map(btn => {
            const onClick = () => {
                if (btn.action === 'close') {
                    this.hide();
                } else if (btn.action === 'confirm') {
                    if (onConfirm) onConfirm(this);
                    this.hide();
                } else if (typeof btn.action === 'function') {
                    btn.action(this);
                }
            };

            return this.h('button', {
                type: 'button',
                className: `btn btn-${btn.variant || 'secondary'} ${btn.className || ''}`,
                disabled: btn.disabled || this.state.loading,
                onClick
            }, btn.text);
        });

        return this.h('div', { className: 'modal-footer' }, ...buttonElements);
    }

    _handleBackdropClick(e) {
        if (this.props.closeOnBackdrop && e.target === e.currentTarget) {
            this.hide();
        }
    }

    _handleKeydown(e) {
        if (this.props.closeOnEscape && e.key === 'Escape') {
            this.hide();
        }
    }

    afterMount() {
        // Add keyboard listener
        this._keydownHandler = this._handleKeydown.bind(this);
        document.addEventListener('keydown', this._keydownHandler);
    }

    beforeUnmount() {
        // Remove keyboard listener
        document.removeEventListener('keydown', this._keydownHandler);
        document.body.classList.remove('modal-open');
    }

    /**
     * Show the modal
     * @returns {Modal} This modal for chaining
     */
    show() {
        this.setState({ visible: true });
        document.body.classList.add('modal-open');

        // Animation
        if (this.props.animation) {
            requestAnimationFrame(() => {
                this.element?.querySelector('.modal')?.classList.add('show');
                this.element?.querySelector('.modal-backdrop')?.classList.add('show');
            });
        }

        if (this.props.onShow) {
            this.props.onShow(this);
        }

        this.emit('modal:show', { modal: this });
        return this;
    }

    /**
     * Hide the modal
     * @returns {Modal} This modal for chaining
     */
    hide() {
        if (this.props.animation) {
            this.element?.querySelector('.modal')?.classList.remove('show');
            this.element?.querySelector('.modal-backdrop')?.classList.remove('show');

            setTimeout(() => {
                this.setState({ visible: false });
                document.body.classList.remove('modal-open');
            }, 150);
        } else {
            this.setState({ visible: false });
            document.body.classList.remove('modal-open');
        }

        if (this.props.onHide) {
            this.props.onHide(this);
        }

        this.emit('modal:hide', { modal: this });
        return this;
    }

    /**
     * Toggle modal visibility
     * @returns {Modal} This modal for chaining
     */
    toggle() {
        return this.state.visible ? this.hide() : this.show();
    }

    /**
     * Set loading state
     * @param {boolean} loading - Loading state
     * @returns {Modal} This modal for chaining
     */
    setLoading(loading) {
        this.setState({ loading });
        return this;
    }

    /**
     * Update modal content
     * @param {string|HTMLElement} content - New content
     * @returns {Modal} This modal for chaining
     */
    setContent(content) {
        this.props.content = content;
        this.update();
        return this;
    }

    /**
     * Update modal title
     * @param {string} title - New title
     * @returns {Modal} This modal for chaining
     */
    setTitle(title) {
        this.props.title = title;
        const titleEl = this.find('.modal-title');
        if (titleEl) titleEl.textContent = title;
        return this;
    }
}

/**
 * Confirmation dialog helper
 * @param {Object} options - Modal options
 * @returns {Promise<boolean>} Resolves true if confirmed, false if cancelled
 */
export function confirm(options = {}) {
    return new Promise((resolve) => {
        const modal = new Modal({
            container: document.body,
            title: options.title || 'Confirm',
            content: options.message || 'Are you sure?',
            size: options.size || 'sm',
            buttons: [
                {
                    text: options.cancelText || 'Cancel',
                    variant: 'secondary',
                    action: () => {
                        modal.hide();
                        setTimeout(() => modal.unmount(), 200);
                        resolve(false);
                    }
                },
                {
                    text: options.confirmText || 'Confirm',
                    variant: options.confirmVariant || 'primary',
                    action: () => {
                        modal.hide();
                        setTimeout(() => modal.unmount(), 200);
                        resolve(true);
                    }
                }
            ]
        });
        modal.show();
    });
}

/**
 * Alert dialog helper
 * @param {Object} options - Modal options
 * @returns {Promise<void>} Resolves when closed
 */
export function alert(options = {}) {
    return new Promise((resolve) => {
        const modal = new Modal({
            container: document.body,
            title: options.title || 'Alert',
            content: options.message || '',
            size: options.size || 'sm',
            buttons: [
                {
                    text: options.buttonText || 'OK',
                    variant: options.variant || 'primary',
                    action: () => {
                        modal.hide();
                        setTimeout(() => modal.unmount(), 200);
                        resolve();
                    }
                }
            ]
        });
        modal.show();
    });
}

export default Modal;
