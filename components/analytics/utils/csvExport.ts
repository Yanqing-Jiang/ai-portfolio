// CSV export utilities

export const downloadCsv = (data: any[], filename: string = 'analytics_data.csv') => {
  try {
    if (!data || !Array.isArray(data) || data.length === 0) {
      console.warn('No data available for CSV export');
      return;
    }

    // Collect all unique headers
    const headersSet = new Set<string>();
    data.forEach(row => {
      if (row && typeof row === 'object') {
        Object.keys(row).forEach(key => headersSet.add(key));
      }
    });
    
    const headers = Array.from(headersSet);
    
    // Escape CSV values
    const escape = (value: any): string => {
      if (value === null || value === undefined) return '';
      const str = String(value).replace(/"/g, '""');
      return `"${str}"`;
    };
    
    // Build CSV content
    const lines = [headers.join(',')];
    for (const row of data) {
      const line = headers.map(header => escape(row?.[header])).join(',');
      lines.push(line);
    }
    
    // Add BOM for Excel compatibility
    const csv = '\uFEFF' + lines.join('\r\n');
    
    // Create and download file
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (error) {
    console.error('CSV download failed:', error);
  }
};

export const extractDataFromChartSpec = (chartSpec: any): any[] => {
  return Array.isArray(chartSpec?.meta?.rawData) ? chartSpec.meta.rawData : [];
};