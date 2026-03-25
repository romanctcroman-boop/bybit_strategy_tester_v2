/**
 * 🃏 Card Component - Bybit Strategy Tester v2
 *
 * Reusable card component for displaying content blocks
 * with header, body, footer, and various styles.
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

import { Component } from './Component.js';

/**
 * Card component for content blocks
 */
export class Card extends Component {
    defaultProps() {
        return {
            title: '',
            subtitle: '',
            content: '',
            footer: '',
            headerActions: [],
            variant: '', // primary, secondary, success, danger, warning, info
            outline: false,
            shadow: true,
            collapsible: false,
            collapsed: false,
            loading: false,
            customClass: '',
            headerClass: '',
            bodyClass: '',
            footerClass: '',
            onCollapse: null,
            onClick: null
        };
    }

    defaultState() {
        return {
            collapsed: false
        };
    }

    constructor(options = {}) {
        super(options);
        this.state.collapsed = this.props.collapsed;
    }

    render() {
        const {
            variant, outline, shadow, collapsible: _collapsible,
            loading, customClass, onClick
        } = this.props;
        const { collapsed } = this.state;

        const cardClasses = [
            'card',
            variant ? (outline ? `border-${variant}` : `bg-${variant} text-white`) : '',
            shadow ? 'shadow-sm' : '',
            onClick ? 'card-clickable' : '',
            customClass
        ].filter(Boolean).join(' ');

        const card = this.h('div', {
            className: cardClasses,
            onClick: onClick ? () => onClick(this) : null,
            style: onClick ? { cursor: 'pointer' } : {}
        });

        // Header
        const header = this._renderHeader();
        if (header) card.appendChild(header);

        // Body (collapsible)
        if (!collapsed) {
            const body = this._renderBody();
            if (body) card.appendChild(body);

            // Footer
            const footer = this._renderFooter();
            if (footer) card.appendChild(footer);
        }

        // Loading overlay
        if (loading) {
            card.style.position = 'relative';
            card.appendChild(this._renderLoading());
        }

        return card;
    }

    _renderHeader() {
        const { title, subtitle, headerActions, collapsible, headerClass, variant, outline } = this.props;
        const { collapsed } = this.state;

        if (!title && headerActions.length === 0) return null;

        const headerClasses = [
            'card-header',
            variant && !outline ? `bg-${variant}` : '',
            headerClass
        ].filter(Boolean).join(' ');

        const header = this.h('div', { className: headerClasses });

        // Header content wrapper
        const headerContent = this.h('div', {
            className: 'd-flex justify-content-between align-items-center'
        });

        // Title area
        const titleArea = this.h('div', { className: 'card-title-area' });

        if (collapsible) {
            const collapseBtn = this.h('button', {
                className: 'btn btn-link p-0 me-2 text-decoration-none',
                onClick: (e) => {
                    e.stopPropagation();
                    this._toggleCollapse();
                }
            },
            this.h('i', { className: `bi ${collapsed ? 'bi-chevron-right' : 'bi-chevron-down'}` })
            );
            titleArea.appendChild(collapseBtn);
        }

        if (title) {
            const titleEl = this.h('h5', { className: 'card-title mb-0 d-inline' }, title);
            titleArea.appendChild(titleEl);
        }

        if (subtitle) {
            titleArea.appendChild(this.h('small', { className: 'text-muted ms-2' }, subtitle));
        }

        headerContent.appendChild(titleArea);

        // Actions
        if (headerActions.length > 0) {
            const actionsArea = this.h('div', { className: 'card-header-actions' });

            headerActions.forEach(action => {
                let btn;
                if (action.icon) {
                    btn = this.h('button', {
                        className: `btn btn-sm ${action.variant ? `btn-${action.variant}` : 'btn-outline-secondary'}`,
                        title: action.title || '',
                        onClick: (e) => {
                            e.stopPropagation();
                            if (action.onClick) action.onClick(this);
                        }
                    },
                    this.h('i', { className: `bi ${action.icon}` }),
                    action.text ? this.h('span', { className: 'ms-1' }, action.text) : null
                    );
                } else {
                    btn = this.h('button', {
                        className: `btn btn-sm ${action.variant ? `btn-${action.variant}` : 'btn-outline-secondary'}`,
                        onClick: (e) => {
                            e.stopPropagation();
                            if (action.onClick) action.onClick(this);
                        }
                    }, action.text);
                }

                actionsArea.appendChild(btn);
            });

            headerContent.appendChild(actionsArea);
        }

        header.appendChild(headerContent);
        return header;
    }

    _renderBody() {
        const { content, bodyClass, loading: _loading } = this.props;

        const bodyClasses = ['card-body', bodyClass].filter(Boolean).join(' ');
        const body = this.h('div', { className: bodyClasses });

        if (typeof content === 'string') {
            body.innerHTML = content;
        } else if (content instanceof HTMLElement) {
            body.appendChild(content);
        } else if (content instanceof Component) {
            body.appendChild(content.element || content.render());
        }

        return body;
    }

    _renderFooter() {
        const { footer, footerClass } = this.props;

        if (!footer) return null;

        const footerClasses = ['card-footer', footerClass].filter(Boolean).join(' ');
        const footerEl = this.h('div', { className: footerClasses });

        if (typeof footer === 'string') {
            footerEl.innerHTML = footer;
        } else if (footer instanceof HTMLElement) {
            footerEl.appendChild(footer);
        } else if (footer instanceof Component) {
            footerEl.appendChild(footer.element || footer.render());
        }

        return footerEl;
    }

    _renderLoading() {
        return this.h('div', {
            className: 'card-loading position-absolute top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center',
            style: { backgroundColor: 'rgba(255,255,255,0.8)', zIndex: 10, borderRadius: 'inherit' }
        },
        this.h('div', { className: 'spinner-border text-primary' })
        );
    }

    _toggleCollapse() {
        this.state.collapsed = !this.state.collapsed;
        this.update();

        if (this.props.onCollapse) {
            this.props.onCollapse(this.state.collapsed, this);
        }
    }

    // Public API
    setTitle(title) {
        this.props.title = title;
        this.update();
    }

    setContent(content) {
        this.props.content = content;
        this.update();
    }

    setLoading(loading) {
        this.props.loading = loading;
        this.update();
    }

    collapse() {
        if (!this.state.collapsed) {
            this._toggleCollapse();
        }
    }

    expand() {
        if (this.state.collapsed) {
            this._toggleCollapse();
        }
    }

    toggle() {
        this._toggleCollapse();
    }
}

export default Card;
