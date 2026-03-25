/**
 * 📊 DataTable Component - Bybit Strategy Tester v2
 *
 * Reusable data table with sorting, pagination, searching,
 * and row selection capabilities.
 *
 * @version 1.0.0
 * @date 2025-12-21
 */

import { Component } from './Component.js';

/**
 * DataTable component for displaying tabular data
 *
 * @example
 * const table = new DataTable({
 *     container: '#table-container',
 *     props: {
 *         columns: [
 *             { key: 'name', label: 'Name', sortable: true },
 *             { key: 'value', label: 'Value', format: (v) => `$${v}` }
 *         ],
 *         data: [{ name: 'Item 1', value: 100 }],
 *         pagination: true,
 *         pageSize: 10
 *     }
 * });
 */
export class DataTable extends Component {
    defaultProps() {
        return {
            columns: [],
            data: [],
            sortable: true,
            searchable: true,
            pagination: true,
            pageSize: 10,
            pageSizeOptions: [10, 25, 50, 100],
            selectable: false,
            multiSelect: false,
            striped: true,
            hover: true,
            bordered: false,
            responsive: true,
            loading: false,
            emptyMessage: 'No data available',
            customClass: '',
            onSort: null,
            onSelect: null,
            onRowClick: null,
            onPageChange: null
        };
    }

    defaultState() {
        return {
            currentPage: 1,
            sortKey: null,
            sortOrder: 'asc', // asc, desc
            searchQuery: '',
            selectedRows: new Set(),
            filteredData: []
        };
    }

    afterMount() {
        this._processData();
    }

    render() {
        const { responsive, customClass, searchable, pagination, loading } = this.props;

        const container = this.h('div', {
            className: `data-table-wrapper ${customClass}`
        });

        // Toolbar (search, actions)
        if (searchable) {
            container.appendChild(this._renderToolbar());
        }

        // Table wrapper
        const tableWrapper = this.h('div', {
            className: responsive ? 'table-responsive' : ''
        });

        // Main table
        tableWrapper.appendChild(this._renderTable());

        // Loading overlay
        if (loading) {
            tableWrapper.appendChild(this._renderLoading());
        }

        container.appendChild(tableWrapper);

        // Pagination
        if (pagination) {
            container.appendChild(this._renderPagination());
        }

        return container;
    }

    _renderToolbar() {
        const { searchable, selectable } = this.props;
        const { selectedRows } = this.state;

        const toolbar = this.h('div', {
            className: 'data-table-toolbar d-flex justify-content-between align-items-center mb-3'
        });

        // Search
        if (searchable) {
            const searchGroup = this.h('div', { className: 'input-group', style: { maxWidth: '300px' } },
                this.h('span', { className: 'input-group-text' },
                    this.h('i', { className: 'bi bi-search' })
                ),
                this.h('input', {
                    type: 'text',
                    className: 'form-control',
                    placeholder: 'Search...',
                    value: this.state.searchQuery,
                    onInput: (e) => this._handleSearch(e.target.value)
                })
            );
            toolbar.appendChild(searchGroup);
        }

        // Selection info
        if (selectable && selectedRows.size > 0) {
            const selectionInfo = this.h('div', { className: 'selection-info text-muted' },
                `${selectedRows.size} row(s) selected`
            );
            toolbar.appendChild(selectionInfo);
        }

        return toolbar;
    }

    _renderTable() {
        const { columns, striped, hover, bordered, selectable } = this.props;
        const displayData = this._getDisplayData();

        const tableClasses = [
            'table',
            striped ? 'table-striped' : '',
            hover ? 'table-hover' : '',
            bordered ? 'table-bordered' : ''
        ].filter(Boolean).join(' ');

        const table = this.h('table', { className: tableClasses });

        // Header
        const thead = this.h('thead', { className: 'table-dark' });
        const headerRow = this.h('tr');

        // Select all checkbox
        if (selectable) {
            const selectAllCell = this.h('th', { style: { width: '50px' } },
                this.h('input', {
                    type: 'checkbox',
                    className: 'form-check-input',
                    checked: this._isAllSelected(),
                    onChange: (e) => this._handleSelectAll(e.target.checked)
                })
            );
            headerRow.appendChild(selectAllCell);
        }

        // Column headers
        columns.forEach(col => {
            const th = this.h('th', {
                className: col.sortable !== false ? 'sortable' : '',
                style: col.width ? { width: col.width } : {},
                onClick: col.sortable !== false ? () => this._handleSort(col.key) : null
            });

            const headerContent = this.h('div', {
                className: 'd-flex align-items-center justify-content-between'
            },
            this.h('span', {}, col.label || col.key),
            col.sortable !== false ? this._renderSortIcon(col.key) : null
            );

            th.appendChild(headerContent);
            headerRow.appendChild(th);
        });

        thead.appendChild(headerRow);
        table.appendChild(thead);

        // Body
        const tbody = this.h('tbody');

        if (displayData.length === 0) {
            const emptyRow = this.h('tr',
                this.h('td', {
                    colSpan: columns.length + (selectable ? 1 : 0),
                    className: 'text-center text-muted py-4'
                }, this.props.emptyMessage)
            );
            tbody.appendChild(emptyRow);
        } else {
            displayData.forEach((row, index) => {
                tbody.appendChild(this._renderRow(row, index));
            });
        }

        table.appendChild(tbody);
        return table;
    }

    _renderRow(row, _index) {
        const { columns, selectable, onRowClick } = this.props;
        const { selectedRows } = this.state;
        const rowId = row.id || row._id || _index;
        const isSelected = selectedRows.has(rowId);

        const tr = this.h('tr', {
            className: isSelected ? 'table-active' : '',
            onClick: onRowClick ? () => onRowClick(row) : null,
            style: onRowClick ? { cursor: 'pointer' } : {}
        });

        // Selection checkbox
        if (selectable) {
            const selectCell = this.h('td',
                this.h('input', {
                    type: 'checkbox',
                    className: 'form-check-input',
                    checked: isSelected,
                    onChange: (e) => {
                        e.stopPropagation();
                        this._handleRowSelect(rowId, e.target.checked);
                    }
                })
            );
            tr.appendChild(selectCell);
        }

        // Data cells
        columns.forEach(col => {
            let value = this._getNestedValue(row, col.key);

            // Apply formatter
            if (col.format) {
                value = col.format(value, row);
            }

            // Apply renderer
            let cellContent;
            if (col.render) {
                cellContent = col.render(value, row);
            } else {
                cellContent = value ?? '-';
            }

            const td = this.h('td', {
                className: col.className || '',
                style: col.align ? { textAlign: col.align } : {}
            });

            if (cellContent instanceof HTMLElement) {
                td.appendChild(cellContent);
            } else {
                td.textContent = String(cellContent);
            }

            tr.appendChild(td);
        });

        return tr;
    }

    _renderSortIcon(key) {
        const { sortKey, sortOrder } = this.state;
        let iconClass = 'bi-chevron-expand text-muted';

        if (sortKey === key) {
            iconClass = sortOrder === 'asc' ? 'bi-chevron-up' : 'bi-chevron-down';
        }

        return this.h('i', { className: `bi ${iconClass} ms-1` });
    }

    _renderPagination() {
        const { pageSize, pageSizeOptions } = this.props;
        const { currentPage, filteredData } = this.state;

        const totalPages = Math.ceil(filteredData.length / pageSize);
        const start = (currentPage - 1) * pageSize + 1;
        const end = Math.min(currentPage * pageSize, filteredData.length);

        const pagination = this.h('div', {
            className: 'data-table-pagination d-flex justify-content-between align-items-center mt-3'
        });

        // Page size selector
        const pageSizeSelect = this.h('div', { className: 'd-flex align-items-center gap-2' },
            this.h('span', { className: 'text-muted' }, 'Show'),
            this.h('select', {
                className: 'form-select form-select-sm',
                style: { width: 'auto' },
                value: pageSize,
                onChange: (e) => this._handlePageSizeChange(Number(e.target.value))
            }, ...pageSizeOptions.map(size =>
                this.h('option', { value: size }, size)
            )),
            this.h('span', { className: 'text-muted' }, 'entries')
        );
        pagination.appendChild(pageSizeSelect);

        // Info
        const info = this.h('div', { className: 'text-muted' },
            filteredData.length > 0
                ? `Showing ${start} to ${end} of ${filteredData.length} entries`
                : 'No entries'
        );
        pagination.appendChild(info);

        // Page navigation
        const nav = this.h('nav');
        const ul = this.h('ul', { className: 'pagination pagination-sm mb-0' });

        // Previous button
        ul.appendChild(this.h('li', { className: `page-item ${currentPage === 1 ? 'disabled' : ''}` },
            this.h('a', {
                className: 'page-link',
                href: '#',
                onClick: (e) => { e.preventDefault(); this._handlePageChange(currentPage - 1); }
            }, 'Previous')
        ));

        // Page numbers
        const pages = this._getPageNumbers(currentPage, totalPages);
        pages.forEach(page => {
            if (page === '...') {
                ul.appendChild(this.h('li', { className: 'page-item disabled' },
                    this.h('span', { className: 'page-link' }, '...')
                ));
            } else {
                ul.appendChild(this.h('li', { className: `page-item ${page === currentPage ? 'active' : ''}` },
                    this.h('a', {
                        className: 'page-link',
                        href: '#',
                        onClick: (e) => { e.preventDefault(); this._handlePageChange(page); }
                    }, page)
                ));
            }
        });

        // Next button
        ul.appendChild(this.h('li', { className: `page-item ${currentPage === totalPages ? 'disabled' : ''}` },
            this.h('a', {
                className: 'page-link',
                href: '#',
                onClick: (e) => { e.preventDefault(); this._handlePageChange(currentPage + 1); }
            }, 'Next')
        ));

        nav.appendChild(ul);
        pagination.appendChild(nav);

        return pagination;
    }

    _renderLoading() {
        return this.h('div', {
            className: 'data-table-loading position-absolute top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center',
            style: { backgroundColor: 'rgba(255,255,255,0.8)', zIndex: 10 }
        },
        this.h('div', { className: 'spinner-border text-primary' })
        );
    }

    // Data processing
    _processData() {
        let data = [...this.props.data];

        // Search filter
        if (this.state.searchQuery) {
            const query = this.state.searchQuery.toLowerCase();
            data = data.filter(row =>
                this.props.columns.some(col => {
                    const value = this._getNestedValue(row, col.key);
                    return String(value).toLowerCase().includes(query);
                })
            );
        }

        // Sort
        if (this.state.sortKey) {
            data.sort((a, b) => {
                const aVal = this._getNestedValue(a, this.state.sortKey);
                const bVal = this._getNestedValue(b, this.state.sortKey);

                let comparison = 0;
                if (aVal < bVal) comparison = -1;
                if (aVal > bVal) comparison = 1;

                return this.state.sortOrder === 'desc' ? -comparison : comparison;
            });
        }

        this.state.filteredData = data;
    }

    _getDisplayData() {
        const { pagination, pageSize } = this.props;
        const { currentPage, filteredData } = this.state;

        if (!pagination) return filteredData;

        const start = (currentPage - 1) * pageSize;
        return filteredData.slice(start, start + pageSize);
    }

    _getNestedValue(obj, path) {
        return path.split('.').reduce((acc, part) => acc?.[part], obj);
    }

    _getPageNumbers(current, total) {
        if (total <= 7) {
            return Array.from({ length: total }, (_, i) => i + 1);
        }

        const pages = [];
        if (current <= 3) {
            pages.push(1, 2, 3, 4, '...', total);
        } else if (current >= total - 2) {
            pages.push(1, '...', total - 3, total - 2, total - 1, total);
        } else {
            pages.push(1, '...', current - 1, current, current + 1, '...', total);
        }
        return pages;
    }

    _isAllSelected() {
        const displayData = this._getDisplayData();
        if (displayData.length === 0) return false;
        return displayData.every(row => {
            const rowId = row.id || row._id;
            return this.state.selectedRows.has(rowId);
        });
    }

    // Event handlers
    _handleSearch(query) {
        this.state.searchQuery = query;
        this.state.currentPage = 1;
        this._processData();
        this.update();
    }

    _handleSort(key) {
        if (this.state.sortKey === key) {
            this.state.sortOrder = this.state.sortOrder === 'asc' ? 'desc' : 'asc';
        } else {
            this.state.sortKey = key;
            this.state.sortOrder = 'asc';
        }
        this._processData();
        this.update();

        if (this.props.onSort) {
            this.props.onSort(key, this.state.sortOrder);
        }
    }

    _handleRowSelect(rowId, selected) {
        if (this.props.multiSelect) {
            if (selected) {
                this.state.selectedRows.add(rowId);
            } else {
                this.state.selectedRows.delete(rowId);
            }
        } else {
            this.state.selectedRows.clear();
            if (selected) {
                this.state.selectedRows.add(rowId);
            }
        }
        this.update();

        if (this.props.onSelect) {
            this.props.onSelect(Array.from(this.state.selectedRows));
        }
    }

    _handleSelectAll(selected) {
        const displayData = this._getDisplayData();
        if (selected) {
            displayData.forEach(row => {
                const rowId = row.id || row._id;
                this.state.selectedRows.add(rowId);
            });
        } else {
            displayData.forEach(row => {
                const rowId = row.id || row._id;
                this.state.selectedRows.delete(rowId);
            });
        }
        this.update();

        if (this.props.onSelect) {
            this.props.onSelect(Array.from(this.state.selectedRows));
        }
    }

    _handlePageChange(page) {
        const totalPages = Math.ceil(this.state.filteredData.length / this.props.pageSize);
        if (page < 1 || page > totalPages) return;

        this.state.currentPage = page;
        this.update();

        if (this.props.onPageChange) {
            this.props.onPageChange(page);
        }
    }

    _handlePageSizeChange(size) {
        this.props.pageSize = size;
        this.state.currentPage = 1;
        this.update();
    }

    // Public API
    setData(data) {
        this.props.data = data;
        this.state.currentPage = 1;
        this._processData();
        this.update();
    }

    getSelectedRows() {
        return this.props.data.filter(row => {
            const rowId = row.id || row._id;
            return this.state.selectedRows.has(rowId);
        });
    }

    clearSelection() {
        this.state.selectedRows.clear();
        this.update();
    }

    setLoading(loading) {
        this.props.loading = loading;
        this.update();
    }

    refresh() {
        this._processData();
        this.update();
    }
}

export default DataTable;
