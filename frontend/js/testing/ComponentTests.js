/**
 * 🧪 Component Tests - Bybit Strategy Tester v2
 *
 * Unit tests for UI components.
 *
 * Part of Phase 4: Testing & Documentation
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

import { describe, assert, mock, dom } from './TestUtils.js';

// Component tests
export const componentTests = describe('Component System', ({ test, beforeEach, afterEach }) => {
    beforeEach(() => {
        dom.createContainer();
    });

    afterEach(() => {
        dom.clearContainer();
    });

    test('Component base class exists', async () => {
        const { Component } = await import('../components/Component.js');
        assert.ok(Component, 'Component class should exist');
        assert.isType(Component, 'function', 'Component should be a constructor');
    });

    test('Component can be instantiated', async () => {
        const { Component } = await import('../components/Component.js');
        const component = new Component({ className: 'test' });
        assert.isInstance(component, Component);
        assert.ok(component.element, 'Component should have element');
    });

    test('Component lifecycle methods', async () => {
        const { Component } = await import('../components/Component.js');

        const onMount = mock();
        const onUnmount = mock();

        class TestComponent extends Component {
            onMount() { onMount(); }
            onUnmount() { onUnmount(); }
        }

        const component = new TestComponent();
        const container = dom.createContainer();
        component.render(container);

        assert.equal(onMount.callCount(), 1, 'onMount should be called once');

        component.destroy();
        assert.equal(onUnmount.callCount(), 1, 'onUnmount should be called once');
    });

    test('Component state management', async () => {
        const { Component } = await import('../components/Component.js');

        class StatefulComponent extends Component {
            constructor() {
                super();
                this.state = { count: 0 };
            }

            increment() {
                this.setState({ count: this.state.count + 1 });
            }
        }

        const component = new StatefulComponent();
        assert.equal(component.state.count, 0);

        component.increment();
        assert.equal(component.state.count, 1);
    });
});

// Modal tests
export const modalTests = describe('Modal Component', ({ test, beforeEach, afterEach }) => {
    beforeEach(() => {
        dom.createContainer();
    });

    afterEach(() => {
        dom.clearContainer();
        // Clean up any modals
        document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
    });

    test('Modal can be created', async () => {
        const { Modal } = await import('../components/Modal.js');

        const modal = new Modal({
            title: 'Test Modal',
            content: 'Test content'
        });

        assert.ok(modal, 'Modal should be created');
        assert.ok(modal.element, 'Modal should have element');
    });

    test('Modal opens and closes', async () => {
        const { Modal } = await import('../components/Modal.js');

        const modal = new Modal({
            title: 'Test Modal',
            content: 'Test content'
        });

        modal.open();
        await dom.waitFor('.modal.show');
        assert.ok(modal.isOpen, 'Modal should be open');

        modal.close();
        assert.ok(!modal.isOpen, 'Modal should be closed');
    });

    test('Modal confirm returns promise', async () => {
        const { Modal } = await import('../components/Modal.js');

        // Mock user clicking confirm
        setTimeout(() => {
            const confirmBtn = document.querySelector('.modal .btn-primary');
            if (confirmBtn) dom.click(confirmBtn);
        }, 100);

        const result = await Modal.confirm('Confirm?', 'Are you sure?');
        assert.ok(result, 'Confirm should resolve to true');
    });
});

// Toast tests
export const toastTests = describe('Toast Component', ({ test, afterEach }) => {
    afterEach(() => {
        // Clean up toasts
        document.querySelectorAll('.toast-container').forEach(el => el.remove());
    });

    test('Toast can show message', async () => {
        const { Toast } = await import('../components/Toast.js');

        Toast.show('Test message', 'success');

        await dom.waitFor('.toast');
        const toast = document.querySelector('.toast');
        assert.ok(toast, 'Toast should be visible');
        assert.elementHasText('.toast', 'Test message');
    });

    test('Toast types', async () => {
        const { Toast } = await import('../components/Toast.js');

        const types = ['success', 'error', 'warning', 'info'];

        for (const type of types) {
            Toast.show(`${type} message`, type);
        }

        await dom.waitFor('.toast');
        const toasts = document.querySelectorAll('.toast');
        assert.equal(toasts.length, types.length, 'All toast types should be created');
    });
});

// DataTable tests
export const dataTableTests = describe('DataTable Component', ({ test, beforeEach, afterEach }) => {
    beforeEach(() => {
        dom.createContainer();
    });

    afterEach(() => {
        dom.clearContainer();
    });

    test('DataTable renders data', async () => {
        const { DataTable } = await import('../components/DataTable.js');

        const data = [
            { id: 1, name: 'Item 1', value: 100 },
            { id: 2, name: 'Item 2', value: 200 },
            { id: 3, name: 'Item 3', value: 300 }
        ];

        const columns = [
            { key: 'id', label: 'ID' },
            { key: 'name', label: 'Name' },
            { key: 'value', label: 'Value' }
        ];

        const table = new DataTable({ data, columns });
        const container = dom.createContainer();
        table.render(container);

        const rows = container.querySelectorAll('tbody tr');
        assert.equal(rows.length, data.length, 'Should render all data rows');
    });

    test('DataTable sorting', async () => {
        const { DataTable } = await import('../components/DataTable.js');

        const data = [
            { id: 3, name: 'C' },
            { id: 1, name: 'A' },
            { id: 2, name: 'B' }
        ];

        const columns = [
            { key: 'id', label: 'ID', sortable: true },
            { key: 'name', label: 'Name', sortable: true }
        ];

        const table = new DataTable({ data, columns });
        const container = dom.createContainer();
        table.render(container);

        // Sort by ID
        table.sort('id', 'asc');

        const firstCell = container.querySelector('tbody tr td');
        assert.ok(firstCell, 'First cell should exist');
    });

    test('DataTable pagination', async () => {
        const { DataTable } = await import('../components/DataTable.js');

        const data = Array.from({ length: 25 }, (_, i) => ({
            id: i + 1,
            name: `Item ${i + 1}`
        }));

        const columns = [
            { key: 'id', label: 'ID' },
            { key: 'name', label: 'Name' }
        ];

        const table = new DataTable({
            data,
            columns,
            pagination: true,
            pageSize: 10
        });

        const container = dom.createContainer();
        table.render(container);

        const rows = container.querySelectorAll('tbody tr');
        assert.equal(rows.length, 10, 'Should show pageSize rows');

        // Go to page 2
        table.goToPage(2);
        const newRows = container.querySelectorAll('tbody tr');
        assert.equal(newRows.length, 10, 'Page 2 should have 10 rows');
    });
});

// Form tests
export const formTests = describe('Form Component', ({ test, beforeEach, afterEach }) => {
    beforeEach(() => {
        dom.createContainer();
    });

    afterEach(() => {
        dom.clearContainer();
    });

    test('Form renders fields', async () => {
        const { Form } = await import('../components/Form.js');

        const fields = [
            { name: 'username', type: 'text', label: 'Username' },
            { name: 'email', type: 'email', label: 'Email' },
            { name: 'password', type: 'password', label: 'Password' }
        ];

        const form = new Form({ fields });
        const container = dom.createContainer();
        form.render(container);

        fields.forEach(field => {
            const input = container.querySelector(`[name="${field.name}"]`);
            assert.ok(input, `Field ${field.name} should exist`);
        });
    });

    test('Form validation', async () => {
        const { Form } = await import('../components/Form.js');

        const fields = [
            {
                name: 'email',
                type: 'email',
                label: 'Email',
                required: true,
                validation: {
                    pattern: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
                    message: 'Invalid email'
                }
            }
        ];

        const form = new Form({ fields });
        const container = dom.createContainer();
        form.render(container);

        // Set invalid email
        form.setValue('email', 'invalid');
        const isValid = form.validate();
        assert.ok(!isValid, 'Form should be invalid');

        // Set valid email
        form.setValue('email', 'test@example.com');
        const isValidNow = form.validate();
        assert.ok(isValidNow, 'Form should be valid');
    });

    test('Form submission', async () => {
        const { Form } = await import('../components/Form.js');
        const onSubmit = mock();

        const fields = [
            { name: 'name', type: 'text', label: 'Name' }
        ];

        const form = new Form({
            fields,
            onSubmit
        });

        const container = dom.createContainer();
        form.render(container);

        form.setValue('name', 'Test');
        form.submit();

        assert.equal(onSubmit.callCount(), 1, 'onSubmit should be called');
        const lastCall = onSubmit.lastCall();
        assert.deepEqual(lastCall.args[0], { name: 'Test' }, 'Should pass form data');
    });
});

// Export all test suites
export const allComponentTests = [
    componentTests,
    modalTests,
    toastTests,
    dataTableTests,
    formTests
];

export default allComponentTests;
