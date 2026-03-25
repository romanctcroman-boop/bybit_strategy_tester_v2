/**
 * 📝 Form Component - Bybit Strategy Tester v2
 *
 * Reusable form component with validation, field types,
 * and automatic state management.
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

import { Component } from './Component.js';

/**
 * Form component with built-in validation
 *
 * @example
 * const form = new Form({
 *     container: '#form-container',
 *     props: {
 *         fields: [
 *             { name: 'email', type: 'email', label: 'Email', required: true },
 *             { name: 'password', type: 'password', label: 'Password', minLength: 8 }
 *         ],
 *         onSubmit: (data) => console.log(data)
 *     }
 * });
 */
export class Form extends Component {
    defaultProps() {
        return {
            fields: [],
            values: {},
            layout: 'vertical', // vertical, horizontal, inline
            submitText: 'Submit',
            cancelText: 'Cancel',
            showCancel: false,
            showReset: false,
            resetText: 'Reset',
            disabled: false,
            loading: false,
            customClass: '',
            labelWidth: '150px', // for horizontal layout
            onSubmit: null,
            onCancel: null,
            onChange: null,
            onValidate: null
        };
    }

    defaultState() {
        return {
            values: {},
            errors: {},
            touched: {},
            isValid: true,
            isSubmitting: false
        };
    }

    constructor(options = {}) {
        super(options);
        // Initialize values from props
        this.state.values = { ...this.props.values };
    }

    render() {
        const { layout, customClass, disabled, loading } = this.props;

        const form = this.h('form', {
            className: `form-component ${layout === 'inline' ? 'd-flex flex-wrap gap-3' : ''} ${customClass}`,
            novalidate: true,
            onSubmit: (e) => this._handleSubmit(e)
        });

        // Render fields
        this.props.fields.forEach(field => {
            form.appendChild(this._renderField(field));
        });

        // Actions
        form.appendChild(this._renderActions());

        // Loading overlay
        if (loading) {
            const overlay = this.h('div', {
                className: 'form-loading position-absolute top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center',
                style: { backgroundColor: 'rgba(255,255,255,0.7)', zIndex: 10 }
            },
            this.h('div', { className: 'spinner-border text-primary' })
            );
            form.appendChild(overlay);
            form.style.position = 'relative';
        }

        if (disabled) {
            form.classList.add('form-disabled');
        }

        return form;
    }

    _renderField(field) {
        const { layout, labelWidth } = this.props;
        const value = this.state.values[field.name] ?? field.defaultValue ?? '';
        const error = this.state.errors[field.name];
        const touched = this.state.touched[field.name];

        const wrapper = this.h('div', {
            className: `mb-3 ${layout === 'horizontal' ? 'row' : ''} ${layout === 'inline' ? 'flex-grow-1' : ''}`
        });

        // Label
        if (field.label && field.type !== 'hidden') {
            const labelAttrs = {
                className: `form-label ${field.required ? 'required' : ''} ${layout === 'horizontal' ? 'col-form-label' : ''}`,
                for: `field-${field.name}`
            };

            if (layout === 'horizontal') {
                labelAttrs.style = { width: labelWidth };
                labelAttrs.className += ' text-end pe-3';
            }

            wrapper.appendChild(this.h('label', labelAttrs,
                field.label,
                field.required ? this.h('span', { className: 'text-danger ms-1' }, '*') : null
            ));
        }

        // Input wrapper for horizontal layout
        const inputWrapper = layout === 'horizontal'
            ? this.h('div', { className: 'col' })
            : wrapper;

        // Render input based on type
        let input;
        switch (field.type) {
        case 'select':
            input = this._renderSelect(field, value);
            break;
        case 'textarea':
            input = this._renderTextarea(field, value);
            break;
        case 'checkbox':
            input = this._renderCheckbox(field, value);
            break;
        case 'radio':
            input = this._renderRadio(field, value);
            break;
        case 'switch':
            input = this._renderSwitch(field, value);
            break;
        case 'range':
            input = this._renderRange(field, value);
            break;
        case 'file':
            input = this._renderFile(field, value);
            break;
        default:
            input = this._renderInput(field, value);
        }

        if (layout === 'horizontal') {
            inputWrapper.appendChild(input);
            wrapper.appendChild(inputWrapper);
        } else {
            wrapper.appendChild(input);
        }

        // Help text
        if (field.help) {
            const helpText = this.h('div', { className: 'form-text text-muted' }, field.help);
            (layout === 'horizontal' ? inputWrapper : wrapper).appendChild(helpText);
        }

        // Error message
        if (touched && error) {
            const errorText = this.h('div', { className: 'invalid-feedback d-block' }, error);
            (layout === 'horizontal' ? inputWrapper : wrapper).appendChild(errorText);
        }

        return wrapper;
    }

    _renderInput(field, value) {
        const error = this.state.errors[field.name];
        const touched = this.state.touched[field.name];

        return this.h('input', {
            type: field.type || 'text',
            id: `field-${field.name}`,
            name: field.name,
            className: `form-control ${touched && error ? 'is-invalid' : ''} ${touched && !error ? 'is-valid' : ''} ${field.size ? `form-control-${field.size}` : ''}`,
            value: value,
            placeholder: field.placeholder || '',
            disabled: field.disabled || this.props.disabled,
            readonly: field.readonly,
            min: field.min,
            max: field.max,
            step: field.step,
            pattern: field.pattern,
            autocomplete: field.autocomplete,
            onInput: (e) => this._handleChange(field.name, e.target.value),
            onBlur: () => this._handleBlur(field.name)
        });
    }

    _renderSelect(field, value) {
        const error = this.state.errors[field.name];
        const touched = this.state.touched[field.name];

        const select = this.h('select', {
            id: `field-${field.name}`,
            name: field.name,
            className: `form-select ${touched && error ? 'is-invalid' : ''} ${field.size ? `form-select-${field.size}` : ''}`,
            disabled: field.disabled || this.props.disabled,
            multiple: field.multiple,
            onChange: (e) => this._handleChange(field.name, field.multiple
                ? Array.from(e.target.selectedOptions).map(o => o.value)
                : e.target.value
            ),
            onBlur: () => this._handleBlur(field.name)
        });

        // Placeholder option
        if (field.placeholder) {
            select.appendChild(this.h('option', { value: '', disabled: true, selected: !value }, field.placeholder));
        }

        // Options
        (field.options || []).forEach(opt => {
            const optValue = typeof opt === 'object' ? opt.value : opt;
            const optLabel = typeof opt === 'object' ? opt.label : opt;
            const isSelected = Array.isArray(value) ? value.includes(optValue) : value === optValue;

            select.appendChild(this.h('option', {
                value: optValue,
                selected: isSelected,
                disabled: opt.disabled
            }, optLabel));
        });

        return select;
    }

    _renderTextarea(field, value) {
        const error = this.state.errors[field.name];
        const touched = this.state.touched[field.name];

        return this.h('textarea', {
            id: `field-${field.name}`,
            name: field.name,
            className: `form-control ${touched && error ? 'is-invalid' : ''}`,
            rows: field.rows || 3,
            placeholder: field.placeholder || '',
            disabled: field.disabled || this.props.disabled,
            readonly: field.readonly,
            maxlength: field.maxLength,
            onInput: (e) => this._handleChange(field.name, e.target.value),
            onBlur: () => this._handleBlur(field.name)
        }, value);
    }

    _renderCheckbox(field, value) {
        const wrapper = this.h('div', { className: 'form-check' });

        wrapper.appendChild(this.h('input', {
            type: 'checkbox',
            id: `field-${field.name}`,
            name: field.name,
            className: 'form-check-input',
            checked: !!value,
            disabled: field.disabled || this.props.disabled,
            onChange: (e) => this._handleChange(field.name, e.target.checked)
        }));

        if (field.checkLabel || field.label) {
            wrapper.appendChild(this.h('label', {
                className: 'form-check-label',
                for: `field-${field.name}`
            }, field.checkLabel || field.label));
        }

        return wrapper;
    }

    _renderRadio(field, value) {
        const wrapper = this.h('div', { className: field.inline ? 'd-flex gap-3' : '' });

        (field.options || []).forEach((opt, idx) => {
            const optValue = typeof opt === 'object' ? opt.value : opt;
            const optLabel = typeof opt === 'object' ? opt.label : opt;

            const radioWrapper = this.h('div', { className: 'form-check' });

            radioWrapper.appendChild(this.h('input', {
                type: 'radio',
                id: `field-${field.name}-${idx}`,
                name: field.name,
                className: 'form-check-input',
                value: optValue,
                checked: value === optValue,
                disabled: field.disabled || this.props.disabled || opt.disabled,
                onChange: (e) => this._handleChange(field.name, e.target.value)
            }));

            radioWrapper.appendChild(this.h('label', {
                className: 'form-check-label',
                for: `field-${field.name}-${idx}`
            }, optLabel));

            wrapper.appendChild(radioWrapper);
        });

        return wrapper;
    }

    _renderSwitch(field, value) {
        const wrapper = this.h('div', { className: 'form-check form-switch' });

        wrapper.appendChild(this.h('input', {
            type: 'checkbox',
            id: `field-${field.name}`,
            name: field.name,
            className: 'form-check-input',
            role: 'switch',
            checked: !!value,
            disabled: field.disabled || this.props.disabled,
            onChange: (e) => this._handleChange(field.name, e.target.checked)
        }));

        if (field.switchLabel) {
            wrapper.appendChild(this.h('label', {
                className: 'form-check-label',
                for: `field-${field.name}`
            }, field.switchLabel));
        }

        return wrapper;
    }

    _renderRange(field, value) {
        const wrapper = this.h('div', { className: 'd-flex align-items-center gap-2' });

        wrapper.appendChild(this.h('input', {
            type: 'range',
            id: `field-${field.name}`,
            name: field.name,
            className: 'form-range flex-grow-1',
            value: value,
            min: field.min || 0,
            max: field.max || 100,
            step: field.step || 1,
            disabled: field.disabled || this.props.disabled,
            onInput: (e) => this._handleChange(field.name, Number(e.target.value))
        }));

        // Value display
        wrapper.appendChild(this.h('span', {
            className: 'badge bg-secondary',
            style: { minWidth: '50px' }
        }, value));

        return wrapper;
    }

    _renderFile(field, _value) {
        return this.h('input', {
            type: 'file',
            id: `field-${field.name}`,
            name: field.name,
            className: 'form-control',
            accept: field.accept,
            multiple: field.multiple,
            disabled: field.disabled || this.props.disabled,
            onChange: (e) => this._handleChange(field.name, field.multiple ? e.target.files : e.target.files[0])
        });
    }

    _renderActions() {
        const { submitText, cancelText, showCancel, showReset, resetText, disabled, loading } = this.props;
        const { isSubmitting } = this.state;

        return this.h('div', { className: 'form-actions d-flex gap-2 mt-4' },
            // Submit button
            this.h('button', {
                type: 'submit',
                className: 'btn btn-primary',
                disabled: disabled || loading || isSubmitting
            },
            isSubmitting ? this.h('span', { className: 'spinner-border spinner-border-sm me-2' }) : null,
            submitText
            ),
            // Cancel button
            showCancel ? this.h('button', {
                type: 'button',
                className: 'btn btn-secondary',
                disabled: disabled || isSubmitting,
                onClick: () => this._handleCancel()
            }, cancelText) : null,
            // Reset button
            showReset ? this.h('button', {
                type: 'button',
                className: 'btn btn-outline-secondary',
                disabled: disabled || isSubmitting,
                onClick: () => this._handleReset()
            }, resetText) : null
        );
    }

    // Event handlers
    _handleChange(name, value) {
        this.state.values[name] = value;
        this._validateField(name);

        // Update just the value display without full re-render
        if (this.props.onChange) {
            this.props.onChange(name, value, { ...this.state.values });
        }
    }

    _handleBlur(name) {
        this.state.touched[name] = true;
        this._validateField(name);
        this.update();
    }

    _handleSubmit(e) {
        e.preventDefault();

        // Mark all fields as touched
        this.props.fields.forEach(field => {
            this.state.touched[field.name] = true;
        });

        // Validate all
        const isValid = this._validateAll();

        if (!isValid) {
            this.update();
            return;
        }

        if (this.props.onSubmit) {
            this.state.isSubmitting = true;
            this.update();

            const result = this.props.onSubmit({ ...this.state.values });

            // Handle async submit
            if (result instanceof Promise) {
                result
                    .then(() => {
                        this.state.isSubmitting = false;
                        this.update();
                    })
                    .catch(() => {
                        this.state.isSubmitting = false;
                        this.update();
                    });
            } else {
                this.state.isSubmitting = false;
            }
        }
    }

    _handleCancel() {
        if (this.props.onCancel) {
            this.props.onCancel();
        }
    }

    _handleReset() {
        this.state.values = { ...this.props.values };
        this.state.errors = {};
        this.state.touched = {};
        this.update();
    }

    // Validation
    _validateField(name) {
        const field = this.props.fields.find(f => f.name === name);
        if (!field) return true;

        const value = this.state.values[name];
        let error = null;

        // Required
        if (field.required && !value && value !== 0 && value !== false) {
            error = field.requiredMessage || `${field.label || name} is required`;
        }

        // Min length
        if (!error && field.minLength && value && value.length < field.minLength) {
            error = field.minLengthMessage || `Minimum ${field.minLength} characters required`;
        }

        // Max length
        if (!error && field.maxLength && value && value.length > field.maxLength) {
            error = field.maxLengthMessage || `Maximum ${field.maxLength} characters allowed`;
        }

        // Pattern
        if (!error && field.pattern && value) {
            const regex = new RegExp(field.pattern);
            if (!regex.test(value)) {
                error = field.patternMessage || 'Invalid format';
            }
        }

        // Email
        if (!error && field.type === 'email' && value) {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(value)) {
                error = field.emailMessage || 'Invalid email address';
            }
        }

        // Number range
        if (!error && field.type === 'number' && value !== '' && value !== null) {
            const num = Number(value);
            if (field.min !== undefined && num < field.min) {
                error = field.minMessage || `Minimum value is ${field.min}`;
            }
            if (field.max !== undefined && num > field.max) {
                error = field.maxMessage || `Maximum value is ${field.max}`;
            }
        }

        // Custom validator
        if (!error && field.validate) {
            error = field.validate(value, this.state.values);
        }

        this.state.errors[name] = error;
        return !error;
    }

    _validateAll() {
        let isValid = true;
        this.props.fields.forEach(field => {
            if (!this._validateField(field.name)) {
                isValid = false;
            }
        });

        this.state.isValid = isValid;

        if (this.props.onValidate) {
            this.props.onValidate(isValid, { ...this.state.errors });
        }

        return isValid;
    }

    // Public API
    getValues() {
        return { ...this.state.values };
    }

    setValues(values) {
        this.state.values = { ...this.state.values, ...values };
        this.update();
    }

    getValue(name) {
        return this.state.values[name];
    }

    setValue(name, value) {
        this.state.values[name] = value;
        this._validateField(name);
        this.update();
    }

    getErrors() {
        return { ...this.state.errors };
    }

    setError(name, error) {
        this.state.errors[name] = error;
        this.state.touched[name] = true;
        this.update();
    }

    isValid() {
        return this._validateAll();
    }

    reset() {
        this._handleReset();
    }

    submit() {
        this._handleSubmit(new Event('submit'));
    }
}

export default Form;
