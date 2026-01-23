/**
 * ⏳ Loader Component - Bybit Strategy Tester v2
 *
 * Reusable loading indicators with various styles
 * and overlay support.
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

import { Component } from './Component.js';

/**
 * Loader component for loading states
 */
export class Loader extends Component {
    defaultProps() {
        return {
            type: 'spinner', // spinner, dots, bars, pulse, skeleton
            size: 'md', // sm, md, lg
            variant: 'primary',
            text: '',
            overlay: false,
            fullscreen: false,
            customClass: ''
        };
    }

    render() {
        const { type, size, variant, text, overlay, fullscreen, customClass } = this.props;

        // Size mapping
        const sizeMap = {
            sm: { spinner: 'spinner-border-sm', width: '1rem' },
            md: { spinner: '', width: '2rem' },
            lg: { spinner: '', width: '3rem' }
        };

        let loaderContent;

        switch (type) {
        case 'dots':
            loaderContent = this._renderDots(variant);
            break;
        case 'bars':
            loaderContent = this._renderBars(variant);
            break;
        case 'pulse':
            loaderContent = this._renderPulse(variant, sizeMap[size].width);
            break;
        case 'skeleton':
            loaderContent = this._renderSkeleton();
            break;
        default:
            loaderContent = this._renderSpinner(variant, sizeMap[size].spinner);
        }

        // Add text if provided
        const content = this.h('div', {
            className: 'd-flex flex-column align-items-center gap-2'
        },
        loaderContent,
        text ? this.h('div', { className: 'loader-text text-muted' }, text) : null
        );

        // Wrapper
        if (fullscreen) {
            return this.h('div', {
                className: `loader-fullscreen position-fixed top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center ${customClass}`,
                style: {
                    backgroundColor: 'rgba(0, 0, 0, 0.5)',
                    zIndex: 9999
                }
            }, content);
        }

        if (overlay) {
            return this.h('div', {
                className: `loader-overlay position-absolute top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center ${customClass}`,
                style: {
                    backgroundColor: 'rgba(255, 255, 255, 0.8)',
                    zIndex: 10
                }
            }, content);
        }

        return this.h('div', {
            className: `loader-inline d-flex align-items-center justify-content-center ${customClass}`
        }, content);
    }

    _renderSpinner(variant, sizeClass) {
        return this.h('div', {
            className: `spinner-border text-${variant} ${sizeClass}`,
            role: 'status'
        },
        this.h('span', { className: 'visually-hidden' }, 'Loading...')
        );
    }

    _renderDots(variant) {
        const dotStyle = {
            width: '10px',
            height: '10px',
            borderRadius: '50%',
            animation: 'loader-dots 1.4s infinite ease-in-out both'
        };

        return this.h('div', {
            className: 'd-flex gap-1'
        },
        this.h('div', {
            className: `bg-${variant}`,
            style: { ...dotStyle, animationDelay: '-0.32s' }
        }),
        this.h('div', {
            className: `bg-${variant}`,
            style: { ...dotStyle, animationDelay: '-0.16s' }
        }),
        this.h('div', {
            className: `bg-${variant}`,
            style: dotStyle
        })
        );
    }

    _renderBars(variant) {
        const barStyle = {
            width: '4px',
            height: '20px',
            animation: 'loader-bars 1.2s infinite ease-in-out'
        };

        return this.h('div', {
            className: 'd-flex align-items-center gap-1'
        },
        ...[0, 1, 2, 3, 4].map(i =>
            this.h('div', {
                className: `bg-${variant}`,
                style: { ...barStyle, animationDelay: `${-1.2 + i * 0.1}s` }
            })
        )
        );
    }

    _renderPulse(variant, width) {
        return this.h('div', {
            className: `bg-${variant} rounded-circle`,
            style: {
                width,
                height: width,
                animation: 'loader-pulse 1.5s infinite ease-in-out'
            }
        });
    }

    _renderSkeleton() {
        return this.h('div', { className: 'skeleton-loader w-100' },
            this.h('div', {
                className: 'skeleton-line mb-2',
                style: { height: '1rem', width: '100%', backgroundColor: '#e0e0e0', borderRadius: '4px', animation: 'skeleton-pulse 1.5s infinite' }
            }),
            this.h('div', {
                className: 'skeleton-line mb-2',
                style: { height: '1rem', width: '80%', backgroundColor: '#e0e0e0', borderRadius: '4px', animation: 'skeleton-pulse 1.5s infinite', animationDelay: '0.1s' }
            }),
            this.h('div', {
                className: 'skeleton-line',
                style: { height: '1rem', width: '60%', backgroundColor: '#e0e0e0', borderRadius: '4px', animation: 'skeleton-pulse 1.5s infinite', animationDelay: '0.2s' }
            })
        );
    }
}

/**
 * Show global loading indicator
 */
let globalLoader = null;

export function showLoading(options = {}) {
    if (globalLoader) {
        hideLoading();
    }

    globalLoader = new Loader({
        container: document.body,
        props: {
            fullscreen: true,
            text: options.text || 'Loading...',
            variant: options.variant || 'primary',
            type: options.type || 'spinner'
        }
    });

    return globalLoader;
}

export function hideLoading() {
    if (globalLoader) {
        globalLoader.unmount();
        globalLoader = null;
    }
}

/**
 * Loading state manager for elements
 */
export class LoadingState {
    constructor(element) {
        this.element = typeof element === 'string'
            ? document.querySelector(element)
            : element;
        this.originalContent = null;
        this.loader = null;
    }

    show(options = {}) {
        if (!this.element) return this;

        // Store original content if replacing
        if (options.replace) {
            this.originalContent = this.element.innerHTML;
            this.element.innerHTML = '';
        }

        // Add position relative if not set
        const position = getComputedStyle(this.element).position;
        if (position === 'static') {
            this.element.style.position = 'relative';
        }

        this.loader = new Loader({
            container: this.element,
            props: {
                overlay: !options.replace,
                text: options.text,
                variant: options.variant || 'primary',
                type: options.type || 'spinner',
                size: options.size || 'md'
            }
        });

        return this;
    }

    hide() {
        if (this.loader) {
            this.loader.unmount();
            this.loader = null;
        }

        if (this.originalContent !== null) {
            this.element.innerHTML = this.originalContent;
            this.originalContent = null;
        }

        return this;
    }
}

export default Loader;
