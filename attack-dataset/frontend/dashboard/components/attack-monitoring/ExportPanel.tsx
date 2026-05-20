"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { 
  exportData, 
  ExportFormat, 
  exportDashboardState,
  exportAttackChain,
  exportFeedbackLoopData,
  exportSessionData,
  exportAgentPerformance,
  generateComprehensiveReport
} from "@/lib/export";

interface ExportPanelProps {
  data?: any;
  component?: string;
}

export default function ExportPanel({ data, component }: ExportPanelProps) {
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>('json');
  const [isExporting, setIsExporting] = useState(false);
  const [exportScope, setExportScope] = useState<'current' | 'all'>('current');

  const handleExport = async () => {
    setIsExporting(true);
    
    try {
      // Simulate processing delay
      await new Promise(resolve => setTimeout(resolve, 500));

      if (component && data) {
        switch (component) {
          case 'attack_chain':
            exportAttackChain(data);
            break;
          case 'feedback_loop':
            exportFeedbackLoopData(data);
            break;
          case 'session':
            exportSessionData(data);
            break;
          case 'agent_performance':
            exportAgentPerformance(data);
            break;
          default:
            exportDashboardState(component, data);
        }
      } else {
        // Generic export
        exportData({
          title: 'OpsecAI Data Export',
          description: 'Generic data export from dashboard',
          data: Array.isArray(data) ? data : [data],
          metadata: {
            exportDate: new Date().toISOString(),
            version: '1.0'
          }
        }, { format: selectedFormat, prettyPrint: true });
      }
    } catch (error) {
      console.error('Export failed:', error);
      alert('Export failed. Please try again.');
    } finally {
      setIsExporting(false);
    }
  };

  const handleComprehensiveExport = async () => {
    setIsExporting(true);
    
    try {
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Generate comprehensive report with real data
      generateComprehensiveReport({
        attackChains: data?.attackChains || [],
        feedbackLoops: data?.feedbackLoops || [],
        sessions: data?.sessions || [],
        agentPerformance: data?.agentPerformance || []
      });
    } catch (error) {
      console.error('Comprehensive export failed:', error);
      alert('Export failed. Please try again.');
    } finally {
      setIsExporting(false);
    }
  };

  const formatOptions: { value: ExportFormat; label: string; description: string }[] = [
    { value: 'json', label: 'JSON', description: 'Structured data format' },
    { value: 'csv', label: 'CSV', description: 'Comma-separated values' },
    { value: 'txt', label: 'TXT', description: 'Plain text report' },
    { value: 'pdf', label: 'PDF', description: 'Formatted document' }
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white">Export Data</h2>
        <p className="text-slate-400 text-sm mt-1">Export dashboard data and reports in various formats</p>
      </div>

      {/* Export Options */}
      <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
        <h3 className="text-lg font-semibold text-white mb-4">Export Options</h3>
        
        {/* Format Selection */}
        <div className="mb-4">
          <label className="text-sm text-slate-400 mb-2 block">Export Format</label>
          <div className="grid grid-cols-2 gap-3">
            {formatOptions.map((format) => (
              <button
                key={format.value}
                onClick={() => setSelectedFormat(format.value)}
                className={`p-3 rounded-lg border-2 transition-all ${
                  selectedFormat === format.value
                    ? 'border-cyan-500 bg-cyan-900/20'
                    : 'border-slate-700 bg-slate-900/50 hover:border-slate-600'
                }`}
              >
                <div className="text-white font-medium">{format.label}</div>
                <div className="text-xs text-slate-400 mt-1">{format.description}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Scope Selection */}
        <div className="mb-4">
          <label className="text-sm text-slate-400 mb-2 block">Export Scope</label>
          <div className="flex gap-3">
            <button
              onClick={() => setExportScope('current')}
              className={`flex-1 p-3 rounded-lg border-2 transition-all ${
                exportScope === 'current'
                  ? 'border-cyan-500 bg-cyan-900/20'
                  : 'border-slate-700 bg-slate-900/50 hover:border-slate-600'
              }`}
            >
              <div className="text-white font-medium">Current View</div>
              <div className="text-xs text-slate-400 mt-1">Export only visible data</div>
            </button>
            <button
              onClick={() => setExportScope('all')}
              className={`flex-1 p-3 rounded-lg border-2 transition-all ${
                exportScope === 'all'
                  ? 'border-cyan-500 bg-cyan-900/20'
                  : 'border-slate-700 bg-slate-900/50 hover:border-slate-600'
              }`}
            >
              <div className="text-white font-medium">All Data</div>
              <div className="text-xs text-slate-400 mt-1">Export complete dataset</div>
            </button>
          </div>
        </div>

        {/* Export Button */}
        <Button
          onClick={handleExport}
          disabled={isExporting || !data}
          className="w-full bg-cyan-600 hover:bg-cyan-700 text-white py-3"
        >
          {isExporting ? 'Exporting...' : `Export as ${selectedFormat.toUpperCase()}`}
        </Button>
      </div>

      {/* Quick Exports */}
      <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
        <h3 className="text-lg font-semibold text-white mb-4">Quick Exports</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Button
            onClick={() => exportAttackChain(data?.attackChains || [])}
            variant="outline"
            disabled={isExporting}
          >
            Export Attack Chains
          </Button>
          <Button
            onClick={() => exportFeedbackLoopData(data?.feedbackLoops || [])}
            variant="outline"
            disabled={isExporting}
          >
            Export Feedback Loops
          </Button>
          <Button
            onClick={() => exportSessionData(data?.sessions || [])}
            variant="outline"
            disabled={isExporting}
          >
            Export Sessions
          </Button>
          <Button
            onClick={() => exportAgentPerformance(data?.agentPerformance || [])}
            variant="outline"
            disabled={isExporting}
          >
            Export Agent Performance
          </Button>
        </div>
      </div>

      {/* Comprehensive Report */}
      <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
        <h3 className="text-lg font-semibold text-white mb-4">Comprehensive Report</h3>
        <p className="text-sm text-slate-400 mb-4">
          Generate a complete report including all available data from the system.
        </p>
        <Button
          onClick={handleComprehensiveExport}
          disabled={isExporting}
          className="w-full bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-700 hover:to-blue-700 text-white py-3"
        >
          {isExporting ? 'Generating...' : 'Generate Comprehensive Report'}
        </Button>
      </div>

      {/* Export History */}
      <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
        <h3 className="text-lg font-semibold text-white mb-4">Export Information</h3>
        <div className="space-y-3 text-sm">
          <div className="flex justify-between">
            <span className="text-slate-400">Current Component:</span>
            <span className="text-white">{component || 'General'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Data Records:</span>
            <span className="text-white">{Array.isArray(data) ? data.length : 1}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Selected Format:</span>
            <span className="text-white">{selectedFormat.toUpperCase()}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Export Scope:</span>
            <span className="text-white">{exportScope === 'current' ? 'Current View' : 'All Data'}</span>
          </div>
        </div>
      </div>
    </div>
  );
}