// --- Function/Class Map ---
// Component: DataTable
//   Role: Render sortable tabular data for A2UI dashboards.
//   Called from: components/generativeUiDashboard/renderer/Registry.tsx
//   Invokes: resolveArray, resolveBoolean
//   Why: Displays KPI and comparison tables with sorting.
//
// Accessibility (Optimization #15):
//   - role="region" for the collapsible container
//   - aria-expanded for collapsible state
//   - aria-sort on sortable columns
//   - scope="col" on th elements
//   - Keyboard navigation support
// --- End Function/Class Map ---
/**
 * DataTable Widget
 *
 * Sortable financial data table with accessibility support.
 */

import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
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

    // Collapsible state - default to collapsed
    const [isExpanded, setIsExpanded] = useState(false);

    // CSV Download handler
    const handleCsvDownload = () => {
        if (columns.length === 0 || sortedData.length === 0) return;

        // Build CSV header
        const headers = columns.map(col => col.label).join(',');

        // Build CSV rows
        const rows = sortedData.map(row =>
            columns.map(col => {
                const value = row[col.key];
                // Escape values containing commas or quotes
                if (value == null) return '';
                const str = String(value);
                if (str.includes(',') || str.includes('"') || str.includes('\n')) {
                    return `"${str.replace(/"/g, '""')}"`;
                }
                return str;
            }).join(',')
        );

        const csvContent = [headers, ...rows].join('\n');
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `data-export-${Date.now()}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    };

    // Accessibility: Generate unique IDs for ARIA
    const tableId = `${componentId}-table`;
    const headerId = `${componentId}-header`;

    return (
        <div
            className="a2ui-data-table-wrapper"
            data-component-id={componentId}
            // Accessibility: Region with label
            role="region"
            aria-labelledby={headerId}
            style={{
                marginBottom: '1rem',
                border: '1px solid rgba(148, 163, 184, 0.2)',
                borderRadius: '12px',
                overflow: 'hidden',
                backgroundColor: 'rgba(15, 23, 42, 0.6)',
            }}
        >
            {/* Collapsible Header */}
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0.75rem 1rem',
                    backgroundColor: 'rgba(30, 41, 59, 0.4)',
                    borderBottom: isExpanded ? '1px solid rgba(148, 163, 184, 0.2)' : 'none',
                    transition: 'background-color 0.2s',
                }}
            >
                <div
                    id={headerId}
                    onClick={() => setIsExpanded(!isExpanded)}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            setIsExpanded(!isExpanded);
                        }
                    }}
                    // Accessibility: Button-like behavior for expand/collapse
                    role="button"
                    tabIndex={0}
                    aria-expanded={isExpanded}
                    aria-controls={tableId}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', flex: 1 }}
                >
                    <span style={{ fontSize: '0.875rem' }} aria-hidden="true">📊</span>
                    <span style={{ fontSize: '0.875rem', fontWeight: 600, color: '#f8fafc' }}>
                        Data Preview
                    </span>
                    <span style={{ fontSize: '0.75rem', color: '#94a3b8' }} aria-label={`${sortedData.length} rows of data`}>
                        ({sortedData.length} rows)
                    </span>
                    <motion.span
                        animate={{ rotate: isExpanded ? 180 : 0 }}
                        transition={{ duration: 0.2 }}
                        style={{ fontSize: '0.65rem', color: '#64748b', marginLeft: '0.25rem' }}
                        aria-hidden="true"
                    >
                        ▼
                    </motion.span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    {/* CSV Download Button */}
                    <button
                        onClick={(e) => { e.stopPropagation(); handleCsvDownload(); }}
                        style={{
                            fontSize: '0.7rem',
                            color: '#10b981',
                            background: 'rgba(16, 185, 129, 0.1)',
                            border: '1px solid rgba(16, 185, 129, 0.3)',
                            padding: '0.25rem 0.5rem',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.25rem',
                            transition: 'all 0.2s',
                        }}
                        title="Download as CSV"
                        aria-label="Download table data as CSV file"
                    >
                        <span aria-hidden="true">📥</span> CSV
                    </button>
                    <button
                        onClick={() => setIsExpanded(!isExpanded)}
                        style={{
                            fontSize: '0.75rem',
                            color: '#6366f1',
                            background: 'transparent',
                            border: 'none',
                            cursor: 'pointer',
                        }}
                    >
                        {isExpanded ? 'Hide' : 'Show'}
                    </button>
                </div>
            </div>

            {/* Collapsible Content */}
            <AnimatePresence>
                {isExpanded && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.3, ease: 'easeInOut' }}
                        style={{ overflow: 'hidden' }}
                    >
                        <div
                            id={tableId}
                            className="a2ui-data-table"
                            style={{
                                overflowX: 'auto',
                                maxHeight: 'clamp(250px, 50vh, 400px)', // Responsive: smaller on mobile
                                WebkitOverflowScrolling: 'touch', // Smooth scroll on iOS
                            }}
                        >
                            <table
                                // Accessibility: Proper table role and caption
                                role="table"
                                aria-label={`Data table with ${sortedData.length} rows and ${columns.length} columns`}
                                style={{
                                    width: '100%',
                                    borderCollapse: 'collapse',
                                    fontSize: 'clamp(0.75rem, 2.5vw, 0.875rem)', // Responsive font
                                    minWidth: '300px', // Ensure minimum readable width
                                }}
                            >
                                <thead>
                                    <tr style={{ backgroundColor: 'rgba(30, 41, 59, 0.8)', position: 'sticky', top: 0, zIndex: 10 }}>
                                        {columns.map((col) => (
                                            <th
                                                key={col.key}
                                                // Accessibility: Column scope and sort state
                                                scope="col"
                                                aria-sort={
                                                    sortKey === col.key
                                                        ? sortDir === 'asc'
                                                            ? 'ascending'
                                                            : 'descending'
                                                        : undefined
                                                }
                                                onClick={() => handleSort(col.key)}
                                                onKeyDown={(e) => {
                                                    if (sortable && (e.key === 'Enter' || e.key === ' ')) {
                                                        e.preventDefault();
                                                        handleSort(col.key);
                                                    }
                                                }}
                                                tabIndex={sortable ? 0 : undefined}
                                                role={sortable ? 'columnheader button' : 'columnheader'}
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
                                                    backgroundColor: 'rgba(30, 41, 59, 0.95)',
                                                }}
                                            >
                                                {col.label}
                                                <span aria-hidden="true">{getSortIndicator(col.key)}</span>
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
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
