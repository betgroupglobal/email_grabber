"use client";

// Export utilities for dashboard data

export type ExportFormat = 'json' | 'csv' | 'txt' | 'pdf';

export interface ExportOptions {
  format: ExportFormat;
  filename?: string;
  includeTimestamp?: boolean;
  prettyPrint?: boolean;
}

export interface ExportData {
  title: string;
  description?: string;
  data: any[];
  metadata?: {
    exportDate: string;
    exportedBy?: string;
    version?: string;
  };
}

// Export to JSON
export function exportToJSON(data: ExportData, options: ExportOptions = { format: 'json' }): void {
  const exportData = {
    ...data,
    metadata: {
      ...data.metadata,
      exportDate: new Date().toISOString()
    }
  };

  const jsonString = options.prettyPrint 
    ? JSON.stringify(exportData, null, 2)
    : JSON.stringify(exportData);

  downloadFile(jsonString, options.filename || 'export.json', 'application/json');
}

// Export to CSV
export function exportToCSV(data: ExportData, options: ExportOptions = { format: 'csv' }): void {
  if (!Array.isArray(data.data) || data.data.length === 0) {
    throw new Error('Data must be a non-empty array for CSV export');
  }

  const headers = Object.keys(data.data[0]);
  const csvRows = [
    headers.join(','),
    ...data.data.map(row => 
      headers.map(header => {
        const value = row[header];
        // Handle nested objects and arrays
        if (typeof value === 'object' && value !== null) {
          return `"${JSON.stringify(value).replace(/"/g, '""')}"`;
        }
        // Escape quotes and wrap in quotes if contains comma
        const stringValue = String(value ?? '');
        if (stringValue.includes(',') || stringValue.includes('"')) {
          return `"${stringValue.replace(/"/g, '""')}"`;
        }
        return stringValue;
      }).join(',')
    )
  ];

  // Add metadata as comments
  const csvContent = [
    `# ${data.title}`,
    `# Exported: ${new Date().toISOString()}`,
    data.description ? `# ${data.description}` : '',
    '',
    ...csvRows
  ].join('\n');

  downloadFile(csvContent, options.filename || 'export.csv', 'text/csv');
}

// Export to TXT (plain text report)
export function exportToTXT(data: ExportData, options: ExportOptions = { format: 'txt' }): void {
  const lines = [
    '='.repeat(80),
    data.title,
    '='.repeat(80),
    '',
    `Exported: ${new Date().toISOString()}`,
    data.description ? `Description: ${data.description}` : '',
    '',
    '='.repeat(80),
    'DATA',
    '='.repeat(80),
    ''
  ];

  if (Array.isArray(data.data)) {
    data.data.forEach((item, index) => {
      lines.push(`[${index + 1}] ${JSON.stringify(item, null, 2)}`);
      lines.push('');
    });
  } else {
    lines.push(JSON.stringify(data.data, null, 2));
  }

  lines.push('');
  lines.push('='.repeat(80));
  lines.push('END OF REPORT');
  lines.push('='.repeat(80));

  downloadFile(lines.join('\n'), options.filename || 'export.txt', 'text/plain');
}

// Export to PDF (basic text-based PDF simulation)
// For production, consider using libraries like jsPDF or react-pdf
export function exportToPDF(data: ExportData, options: ExportOptions = { format: 'pdf' }): void {
  // For now, we'll export as a formatted text file with .pdf extension
  // In production, this should use a proper PDF library
  const textContent = exportToTXTContent(data);
  
  // Create a simple HTML-based PDF
  const htmlContent = `
    <!DOCTYPE html>
    <html>
    <head>
      <title>${data.title}</title>
      <style>
        body { font-family: Arial, sans-serif; padding: 40px; }
        h1 { color: #333; }
        .metadata { color: #666; font-size: 12px; margin-bottom: 20px; }
        .data-item { margin-bottom: 15px; padding: 10px; background: #f5f5f5; border-radius: 4px; }
        pre { white-space: pre-wrap; word-wrap: break-word; }
      </style>
    </head>
    <body>
      <h1>${data.title}</h1>
      <div class="metadata">
        <p>Exported: ${new Date().toISOString()}</p>
        ${data.description ? `<p>${data.description}</p>` : ''}
      </div>
      <div class="data">
        ${Array.isArray(data.data) 
          ? data.data.map((item, index) => `
              <div class="data-item">
                <strong>Item ${index + 1}:</strong>
                <pre>${JSON.stringify(item, null, 2)}</pre>
              </div>
            `).join('')
          : `<pre>${JSON.stringify(data.data, null, 2)}</pre>`
        }
      </div>
    </body>
    </html>
  `;

  const blob = new Blob([htmlContent], { type: 'text/html' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = options.filename || 'export.html';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

// Helper function to generate text content
function exportToTXTContent(data: ExportData): string {
  const lines = [
    '='.repeat(80),
    data.title,
    '='.repeat(80),
    '',
    `Exported: ${new Date().toISOString()}`,
    data.description ? `Description: ${data.description}` : '',
    '',
    '='.repeat(80),
    'DATA',
    '='.repeat(80),
    ''
  ];

  if (Array.isArray(data.data)) {
    data.data.forEach((item, index) => {
      lines.push(`[${index + 1}] ${JSON.stringify(item, null, 2)}`);
      lines.push('');
    });
  } else {
    lines.push(JSON.stringify(data.data, null, 2));
  }

  return lines.join('\n');
}

// Generic export function
export function exportData(data: ExportData, options: ExportOptions): void {
  switch (options.format) {
    case 'json':
      exportToJSON(data, options);
      break;
    case 'csv':
      exportToCSV(data, options);
      break;
    case 'txt':
      exportToTXT(data, options);
      break;
    case 'pdf':
      exportToPDF(data, options);
      break;
    default:
      throw new Error(`Unsupported export format: ${options.format}`);
  }
}

// Helper function to download file
function downloadFile(content: string, filename: string, mimeType: string): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

// Export dashboard state
export function exportDashboardState(component: string, data: any): void {
  const exportData: ExportData = {
    title: `OpsecAI Dashboard Export - ${component}`,
    description: `Dashboard state export for ${component} component`,
    data: Array.isArray(data) ? data : [data],
    metadata: {
      exportDate: new Date().toISOString(),
      version: '1.0'
    }
  };

  exportToJSON(exportData, {
    format: 'json',
    filename: `opsecai_${component}_${Date.now()}.json`,
    prettyPrint: true
  });
}

// Export attack chain data
export function exportAttackChain(chainData: any): void {
  const exportData: ExportData = {
    title: 'OpsecAI Attack Chain Export',
    description: 'Complete attack chain configuration and execution data',
    data: Array.isArray(chainData) ? chainData : [chainData],
    metadata: {
      exportDate: new Date().toISOString(),
      version: '1.0'
    }
  };

  exportToJSON(exportData, {
    format: 'json',
    filename: `attack_chain_${Date.now()}.json`,
    prettyPrint: true
  });
}

// Export feedback loop data
export function exportFeedbackLoopData(feedbackData: any): void {
  const exportData: ExportData = {
    title: 'OpsecAI Feedback Loop Analytics',
    description: 'Feedback loop performance and adaptation metrics',
    data: Array.isArray(feedbackData) ? feedbackData : [feedbackData],
    metadata: {
      exportDate: new Date().toISOString(),
      version: '1.0'
    }
  };

  exportToCSV(exportData, {
    format: 'csv',
    filename: `feedback_loop_${Date.now()}.csv`
  });
}

// Export session data
export function exportSessionData(sessionData: any): void {
  const exportData: ExportData = {
    title: 'OpsecAI Session Data',
    description: 'Complete session information and execution history',
    data: Array.isArray(sessionData) ? sessionData : [sessionData],
    metadata: {
      exportDate: new Date().toISOString(),
      version: '1.0'
    }
  };

  exportToJSON(exportData, {
    format: 'json',
    filename: `session_data_${Date.now()}.json`,
    prettyPrint: true
  });
}

// Export agent performance data
export function exportAgentPerformance(agentData: any): void {
  const exportData: ExportData = {
    title: 'OpsecAI Agent Performance Report',
    description: 'Multi-agent orchestration performance metrics',
    data: Array.isArray(agentData) ? agentData : [agentData],
    metadata: {
      exportDate: new Date().toISOString(),
      version: '1.0'
    }
  };

  exportToCSV(exportData, {
    format: 'csv',
    filename: `agent_performance_${Date.now()}.csv`
  });
}

// Generate comprehensive report
export function generateComprehensiveReport(data: {
  attackChains?: any[];
  feedbackLoops?: any[];
  sessions?: any[];
  agentPerformance?: any[];
}): void {
  const exportData: ExportData = {
    title: 'OpsecAI Comprehensive Report',
    description: 'Complete system performance and security assessment report',
    data: [
      ...(data.attackChains || []).map(item => ({ ...item, type: 'attack_chain' })),
      ...(data.feedbackLoops || []).map(item => ({ ...item, type: 'feedback_loop' })),
      ...(data.sessions || []).map(item => ({ ...item, type: 'session' })),
      ...(data.agentPerformance || []).map(item => ({ ...item, type: 'agent_performance' }))
    ],
    metadata: {
      exportDate: new Date().toISOString(),
      version: '1.0'
    }
  };

  exportToJSON(exportData, {
    format: 'json',
    filename: `opsecai_comprehensive_report_${Date.now()}.json`,
    prettyPrint: true
  });
}