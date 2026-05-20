"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useAlerts, AlertThreshold, AlertSeverity, AlertCategory } from "@/lib/alerts";

export default function AlertConfiguration() {
  const { config, updateConfig, updateThreshold, requestNotificationPermission } = useAlerts();
  const [editingThreshold, setEditingThreshold] = useState<string | null>(null);

  const handleToggleThreshold = (thresholdId: string) => {
    const threshold = config.thresholds.find(t => t.id === thresholdId);
    if (threshold) {
      updateThreshold(thresholdId, { enabled: !threshold.enabled });
    }
  };

  const handleUpdateThreshold = (thresholdId: string, field: keyof AlertThreshold, value: any) => {
    updateThreshold(thresholdId, { [field]: value });
  };

  const handleRequestNotificationPermission = () => {
    requestNotificationPermission();
  };

  const getCategoryColor = (category: AlertCategory) => {
    switch (category) {
      case 'security': return 'text-red-400';
      case 'operational': return 'text-yellow-400';
      case 'performance': return 'text-orange-400';
      case 'system': return 'text-blue-400';
      default: return 'text-slate-400';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Alert Configuration</h2>
          <p className="text-slate-400 text-sm mt-1">Configure alert thresholds and notification settings</p>
        </div>
        <Button
          onClick={handleRequestNotificationPermission}
          variant="outline"
          size="sm"
        >
          Enable Browser Notifications
        </Button>
      </div>

      {/* Global Settings */}
      <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
        <h3 className="text-lg font-semibold text-white mb-4">Global Notification Settings</h3>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-white font-medium">Dashboard Notifications</div>
              <div className="text-sm text-slate-400">Show alerts in the dashboard</div>
            </div>
            <button
              onClick={() => updateConfig({ 
                globalSettings: { 
                  ...config.globalSettings, 
                  enableDashboardNotifications: !config.globalSettings.enableDashboardNotifications 
                }
              })}
              className={`w-12 h-6 rounded-full transition-colors ${
                config.globalSettings.enableDashboardNotifications ? 'bg-cyan-600' : 'bg-slate-600'
              }`}
            >
              <div className={`w-5 h-5 bg-white rounded-full transition-transform ${
                config.globalSettings.enableDashboardNotifications ? 'translate-x-6' : 'translate-x-0.5'
              }`} />
            </button>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <div className="text-white font-medium">Email Notifications</div>
              <div className="text-sm text-slate-400">Send alerts via email</div>
            </div>
            <button
              onClick={() => updateConfig({ 
                globalSettings: { 
                  ...config.globalSettings, 
                  enableEmailNotifications: !config.globalSettings.enableEmailNotifications 
                }
              })}
              className={`w-12 h-6 rounded-full transition-colors ${
                config.globalSettings.enableEmailNotifications ? 'bg-cyan-600' : 'bg-slate-600'
              }`}
            >
              <div className={`w-5 h-5 bg-white rounded-full transition-transform ${
                config.globalSettings.enableEmailNotifications ? 'translate-x-6' : 'translate-x-0.5'
              }`} />
            </button>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <div className="text-white font-medium">Quiet Hours</div>
              <div className="text-sm text-slate-400">Suppress notifications during specified hours</div>
            </div>
            <button
              onClick={() => updateConfig({ 
                globalSettings: { 
                  ...config.globalSettings, 
                  quietHours: { 
                    enabled: !config.globalSettings.quietHours?.enabled,
                    startTime: config.globalSettings.quietHours?.startTime || '22:00',
                    endTime: config.globalSettings.quietHours?.endTime || '08:00'
                  }
                }
              })}
              className={`w-12 h-6 rounded-full transition-colors ${
                config.globalSettings.quietHours?.enabled ? 'bg-cyan-600' : 'bg-slate-600'
              }`}
            >
              <div className={`w-5 h-5 bg-white rounded-full transition-transform ${
                config.globalSettings.quietHours?.enabled ? 'translate-x-6' : 'translate-x-0.5'
              }`} />
            </button>
          </div>

          {config.globalSettings.quietHours?.enabled && (
            <div className="grid grid-cols-2 gap-4 pl-4 border-l-2 border-slate-600">
              <div>
                <label className="text-sm text-slate-400 mb-1 block">Start Time</label>
                <input
                  type="time"
                  value={config.globalSettings.quietHours.startTime}
                  onChange={(e) => updateConfig({ 
                    globalSettings: { 
                      ...config.globalSettings, 
                      quietHours: { 
                        enabled: config.globalSettings.quietHours?.enabled ?? false,
                        startTime: e.target.value,
                        endTime: config.globalSettings.quietHours?.endTime || '08:00'
                      }
                    }
                  })}
                  className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-white"
                />
              </div>
              <div>
                <label className="text-sm text-slate-400 mb-1 block">End Time</label>
                <input
                  type="time"
                  value={config.globalSettings.quietHours.endTime}
                  onChange={(e) => updateConfig({ 
                    globalSettings: { 
                      ...config.globalSettings, 
                      quietHours: { 
                        enabled: config.globalSettings.quietHours?.enabled ?? false,
                        startTime: config.globalSettings.quietHours?.startTime || '22:00',
                        endTime: e.target.value
                      }
                    }
                  })}
                  className="w-full bg-slate-900 border border-slate-700 rounded px-3 py-2 text-white"
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Alert Thresholds */}
      <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
        <h3 className="text-lg font-semibold text-white mb-4">Alert Thresholds</h3>
        <div className="space-y-4">
          {config.thresholds.map((threshold) => (
            <div
              key={threshold.id}
              className="bg-slate-900/50 rounded-lg p-4 border border-slate-700"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-sm font-medium ${getCategoryColor(threshold.category)}`}>
                      {threshold.category}
                    </span>
                    <span className="text-white font-medium">{threshold.name}</span>
                  </div>
                  <div className="text-sm text-slate-400">
                    {threshold.metric} {threshold.operator} {threshold.value}
                  </div>
                </div>
                <button
                  onClick={() => handleToggleThreshold(threshold.id)}
                  className={`w-12 h-6 rounded-full transition-colors ${
                    threshold.enabled ? 'bg-green-600' : 'bg-slate-600'
                  }`}
                >
                  <div className={`w-5 h-5 bg-white rounded-full transition-transform ${
                    threshold.enabled ? 'translate-x-6' : 'translate-x-0.5'
                  }`} />
                </button>
              </div>

              {editingThreshold === threshold.id && (
                <div className="grid grid-cols-2 gap-4 mt-4 pt-4 border-t border-slate-700">
                  <div>
                    <label className="text-xs text-slate-500 mb-1 block">Threshold Value</label>
                    <input
                      type="number"
                      value={threshold.value}
                      onChange={(e) => handleUpdateThreshold(threshold.id, 'value', parseFloat(e.target.value))}
                      className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1 text-white text-sm"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 mb-1 block">Cooldown (minutes)</label>
                    <input
                      type="number"
                      value={threshold.cooldownMinutes}
                      onChange={(e) => handleUpdateThreshold(threshold.id, 'cooldownMinutes', parseInt(e.target.value))}
                      className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1 text-white text-sm"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 mb-1 block">Operator</label>
                    <select
                      value={threshold.operator}
                      onChange={(e) => handleUpdateThreshold(threshold.id, 'operator', e.target.value)}
                      className="w-full bg-slate-800 border border-slate-600 rounded px-2 py-1 text-white text-sm"
                    >
                      <option value=">">&gt;</option>
                      <option value="<">&lt;</option>
                      <option value="=">=</option>
                      <option value=">=">&gt;=</option>
                      <option value="<=">&lt;=</option>
                    </select>
                  </div>
                  <div className="flex items-end">
                    <Button
                      onClick={() => setEditingThreshold(null)}
                      size="sm"
                      variant="outline"
                      className="w-full"
                    >
                      Done
                    </Button>
                  </div>
                </div>
              )}

              <div className="flex items-center justify-between mt-3">
                <div className="text-xs text-slate-500">
                  Notification methods: {threshold.notificationMethods.join(', ')}
                </div>
                <Button
                  onClick={() => setEditingThreshold(editingThreshold === threshold.id ? null : threshold.id)}
                  size="sm"
                  variant="outline"
                >
                  {editingThreshold === threshold.id ? 'Cancel' : 'Edit'}
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}