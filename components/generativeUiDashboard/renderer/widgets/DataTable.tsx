/**
 * DataTable Widget
 *
 * Sortable financial data table.
 */

import React, { useState, useMemo } from 'react';
import type { A2UIRendererProps } from '../Registry';
import { resolveArray, resolveBoolean } from '../../a2ui/DataBinder';
import type { DataTableProps } from '../../a2ui/types';

interface Column {
    key: string;
    label: string;
    type?: 'string' | 'number' | 'currency' | 'percentage';
    align?: 'left' | 'center' | 'right';
}

type RowData = Record<string, unknown>;

type SortDirection = 'asc' | 'desc' | null;

export function DataTable({
    componentId,
    props,
    dataModel,
}: A2UIRendererProps): React.ReactElement {
    const tableProps = props as unknown as DataTableProps;

    const columns = resolveArray<Column>(tableProps.columns, dataModel, []);
    const data = resolveArray<RowData>(tableProps.data, dataModel, []);
    const sortable = resolveBoolean(tableProps.sortable, dataModel, true);

    const [sortKey, setSortKey] = useState<string | null>(null);
    const [sortDir, setSortDir] = useState<SortDirection>(null);

    // Handle column header click
    const handleSort = (key: string) => {
        if (!sortable) return;

        if (sortKey === key) {
            // Cycle through: asc -> desc -> null
            if (sortDir === 'asc') {
                setSortDir('desc');
            } else if (sortDir === 'desc') {
                setSortKey(null);
                setSortDir(null);
            } else {
                setSortDir('asc');
            }
        } else {
            setSortKey(key);
            setSortDir('asc');
        }
    };

    // Sorted data
    const sortedData = useMemo(() => {
        if (!sortKey || !sortDir) return data;

        return [...data].sort((a, b) => {
            const aVal = a[sortKey];
            const bVal = b[sortKey];

            if (typeof aVal === 'number' && typeof bVal === 'number') {
                return sortDir === 'asc' ? aVal - bVal : bVal - aVal;
            }

            const aStr = String(aVal || '');
            const bStr = String(bVal || '');
            return sortDir === 'asc' ? aStr.localeCompare(bStr) : bStr.localeCompare(aStr);
        });
    }, [data, sortKey, sortDir]);

    // Format cell value
    const formatCell = (value: unknown, type?: string): string => {
        if (value == null) return '-';

        if (type === 'currency' && typeof value === 'number') {
            return `$${value.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
        }
        if (type === 'percentage' && typeof value === 'number') {
            return `${value.toFixed(2)}%`;
        }
        if (typeof value === 'number') {
            return value.toLocaleString();
        }

        return String(value);
    };

    // Sort indicator
    const getSortIndicator = (key: string): string => {
        if (sortKey !== key) return '';
        if (sortDir === 'asc') return ' ↑';
        if (sortDir === 'desc') return ' ↓';
        return '';
    };

    return (
        <div
            className="a2ui-data-table"
            data-component-id={componentId}
            style={{
                overflowX: 'auto',
                borderRadius: '8px',
                border: '1px solid rgba(99, 102, 241, 0.2)',
            }}
        >
            <table
                style={{
                    width: '100%',
                    borderCollapse: 'collapse',
                    fontSize: '0.875rem',
                }}
            >
                <thead>
                    <tr style={{ backgroundColor: 'rgba(30, 41, 59, 0.8)' }}>
                        {columns.map((col) => (
                            <th
                                key={col.key}
                                onClick={() => handleSort(col.key)}
                                style={{
                                    padding: '0.75rem 1rem',
                                    textAlign: col.align || 'left',
                                    color: '#94a3b8',
                                    fontWeight: 600,
                                    textTransform: 'uppercase',
                                    fontSize: '0.75rem',
                                    letterSpacing: '0.05em',
                                    cursor: sortable ? 'pointer' : 'default',
                                    userSelect: 'none',
                                    borderBottom: '1px solid rgba(99, 102, 241, 0.2)',
                                }}
                            >
                                {col.label}
                                {getSortIndicator(col.key)}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {sortedData.map((row, rowIndex) => (
                        <tr
                            key={rowIndex}
                            style={{
                                backgroundColor:
                                    rowIndex % 2 === 0 ? 'transparent' : 'rgba(30, 41, 59, 0.3)',
                            }}
                        >
                            {columns.map((col) => (
                                <td
                                    key={col.key}
                                    style={{
                                        padding: '0.75rem 1rem',
                                        textAlign: col.align || 'left',
                                        color: '#f8fafc',
                                        borderBottom: '1px solid rgba(99, 102, 241, 0.1)',
                                    }}
                                >
                                    {formatCell(row[col.key], col.type)}
                                </td>
                            ))}
                        </tr>
                    ))}
                    {sortedData.length === 0 && (
                        <tr>
                            <td
                                colSpan={columns.length}
                                style={{
                                    padding: '2rem',
                                    textAlign: 'center',
                                    color: '#64748b',
                                }}
                            >
                                No data available
                            </td>
                        </tr>
                    )}
                </tbody>
            </table>
        </div>
    );
}
