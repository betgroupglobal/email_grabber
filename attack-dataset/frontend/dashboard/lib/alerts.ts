"use client";

import { useState, useEffect, useCallback } from 'react';

// Alert types and interfaces
export type AlertSeverity = 'info' | 'warning' | 'error' | 'success';
export type AlertCategory = 'system' | 'security' | 'performance' | 'operational';

export interface AlertThreshold {
  id: string;
  name: string;
  category: AlertCategory;
  metric: string;
  operator: '>' | '<' | '=' | '>=' | '<=';
  value: number;
  enabled: boolean;
  notificationMethods: ('dashboard' | 'email' | 'webhook')[];
  cooldownMinutes: number;
}

export interface Alert {
  id: string;
  severity: AlertSeverity;
  category: AlertCategory;
  title: string;
  message: string;
  timestamp: number;
  acknowledged: boolean;
  thresholdId?: string;
  metadata?: Record<string, any>;
}

export interface AlertConfig {
  thresholds: AlertThreshold[];
  globalSettings: {
    enableDashboardNotifications: boolean;
    enableEmailNotifications: boolean;
    enableWebhookNotifications: boolean;
    webhookUrl?: string;
    emailRecipients?: string[];
    quietHours?: {
      enabled: boolean;
      startTime: string; // HH:MM format
      endTime: string;   // HH:MM format
    };
  };
}

// Default alert configuration
const defaultAlertConfig: AlertConfig = {
  thresholds: [
    {
      id: 'high_detection_rate',
      name: 'High Detection Rate',
      category: 'security',
      metric: 'detection_rate',
      operator: '>',
      value: 0.7,
      enabled: true,
      notificationMethods: ['dashboard', 'email'],
      cooldownMinutes: 30
    },
    {
      id: 'low_success_rate',
      name: 'Low Success Rate',
      category: 'operational',
      metric: 'success_rate',
      operator: '<',
      value: 0.5,
      enabled: true,
      notificationMethods: ['dashboard'],
      cooldownMinutes: 15
    },
    {
      id: 'high_response_time',
      name: 'High Response Time',
      category: 'performance',
      metric: 'response_time_ms',
      operator: '>',
      value: 5000,
      enabled: true,
      notificationMethods: ['dashboard'],
      cooldownMinutes: 10
    },
    {
      id: 'session_failure',
      name: 'Session Failure',
      category: 'operational',
      metric: 'session_status',
      operator: '=',
      value: 1, // 1 = failed
      enabled: true,
      notificationMethods: ['dashboard', 'email'],
      cooldownMinutes: 5
    }
  ],
  globalSettings: {
    enableDashboardNotifications: true,
    enableEmailNotifications: false,
    enableWebhookNotifications: false,
    quietHours: {
      enabled: false,
      startTime: '22:00',
      endTime: '08:00'
    }
  }
};

// Alert manager class
class AlertManager {
  private alerts: Alert[] = [];
  private config: AlertConfig;
  private lastTriggered: Map<string, number> = new Map();
  private listeners: Set<(alerts: Alert[]) => void> = new Set();

  constructor(config: AlertConfig = defaultAlertConfig) {
    this.config = config;
    this.loadFromStorage();
  }

  private loadFromStorage(): void {
    if (typeof window === 'undefined' || !window.localStorage) {
      return;
    }

    try {
      const savedConfig = window.localStorage.getItem('opsecai_alert_config');
      if (savedConfig) {
        this.config = JSON.parse(savedConfig);
      }

      const savedAlerts = window.localStorage.getItem('opsecai_alerts');
      if (savedAlerts) {
        this.alerts = JSON.parse(savedAlerts);
        // Remove alerts older than 24 hours
        const cutoff = Date.now() - (24 * 60 * 60 * 1000);
        this.alerts = this.alerts.filter(alert => alert.timestamp > cutoff);
      }
    } catch (error) {
      console.error('Error loading alert data:', error);
    }
  }

  private saveToStorage(): void {
    if (typeof window === 'undefined' || !window.localStorage) {
      return;
    }

    try {
      window.localStorage.setItem('opsecai_alert_config', JSON.stringify(this.config));
      window.localStorage.setItem('opsecai_alerts', JSON.stringify(this.alerts));
    } catch (error) {
      console.error('Error saving alert data:', error);
    }
  }

  subscribe(listener: (alerts: Alert[]) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private notifyListeners(): void {
    this.listeners.forEach(listener => listener([...this.alerts]));
  }

  getConfig(): AlertConfig {
    return { ...this.config };
  }

  updateConfig(config: Partial<AlertConfig>): void {
    this.config = { ...this.config, ...config };
    this.saveToStorage();
  }

  updateThreshold(thresholdId: string, updates: Partial<AlertThreshold>): void {
    const index = this.config.thresholds.findIndex(t => t.id === thresholdId);
    if (index !== -1) {
      this.config.thresholds[index] = { ...this.config.thresholds[index], ...updates };
      this.saveToStorage();
    }
  }

  getAlerts(): Alert[] {
    return [...this.alerts].sort((a, b) => b.timestamp - a.timestamp);
  }

  acknowledgeAlert(alertId: string): void {
    const alert = this.alerts.find(a => a.id === alertId);
    if (alert) {
      alert.acknowledged = true;
      this.saveToStorage();
      this.notifyListeners();
    }
  }

  acknowledgeAllAlerts(): void {
    this.alerts.forEach(alert => alert.acknowledged = true);
    this.saveToStorage();
    this.notifyListeners();
  }

  clearAlert(alertId: string): void {
    this.alerts = this.alerts.filter(a => a.id !== alertId);
    this.saveToStorage();
    this.notifyListeners();
  }

  clearAcknowledgedAlerts(): void {
    this.alerts = this.alerts.filter(a => !a.acknowledged);
    this.saveToStorage();
    this.notifyListeners();
  }

  private isInQuietHours(): boolean {
    if (!this.config.globalSettings.quietHours?.enabled) return false;
    
    const now = new Date();
    const currentTime = now.getHours() * 60 + now.getMinutes();
    
    const [startHour, startMin] = this.config.globalSettings.quietHours.startTime.split(':').map(Number);
    const [endHour, endMin] = this.config.globalSettings.quietHours.endTime.split(':').map(Number);
    
    const startTime = startHour * 60 + startMin;
    const endTime = endHour * 60 + endMin;
    
    if (startTime < endTime) {
      return currentTime >= startTime && currentTime < endTime;
    } else {
      // Overnight quiet hours
      return currentTime >= startTime || currentTime < endTime;
    }
  }

  checkThresholds(metrics: Record<string, number>): void {
    if (this.isInQuietHours()) return;

    this.config.thresholds.forEach(threshold => {
      if (!threshold.enabled) return;

      const metricValue = metrics[threshold.metric];
      if (metricValue === undefined) return;

      const shouldTrigger = this.evaluateThreshold(metricValue, threshold.operator, threshold.value);
      
      if (shouldTrigger) {
        const lastTriggered = this.lastTriggered.get(threshold.id) || 0;
        const cooldownMs = threshold.cooldownMinutes * 60 * 1000;
        
        if (Date.now() - lastTriggered > cooldownMs) {
          this.triggerAlert(threshold, metricValue);
          this.lastTriggered.set(threshold.id, Date.now());
        }
      }
    });
  }

  private evaluateThreshold(value: number, operator: string, threshold: number): boolean {
    switch (operator) {
      case '>': return value > threshold;
      case '<': return value < threshold;
      case '=': return value === threshold;
      case '>=': return value >= threshold;
      case '<=': return value <= threshold;
      default: return false;
    }
  }

  private triggerAlert(threshold: AlertThreshold, value: number): void {
    const alert: Alert = {
      id: `alert_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      severity: this.getSeverityFromCategory(threshold.category),
      category: threshold.category,
      title: threshold.name,
      message: `${threshold.metric} is ${threshold.operator} ${threshold.value} (current: ${value})`,
      timestamp: Date.now(),
      acknowledged: false,
      thresholdId: threshold.id,
      metadata: { thresholdValue: threshold.value, currentValue: value }
    };

    this.alerts.unshift(alert);
    
    // Keep only last 100 alerts
    if (this.alerts.length > 100) {
      this.alerts = this.alerts.slice(0, 100);
    }

    this.saveToStorage();
    this.notifyListeners();

    // Send notifications based on configuration
    if (this.config.globalSettings.enableDashboardNotifications && 
        threshold.notificationMethods.includes('dashboard')) {
      this.showBrowserNotification(alert);
    }
  }

  private getSeverityFromCategory(category: AlertCategory): AlertSeverity {
    switch (category) {
      case 'security': return 'error';
      case 'operational': return 'warning';
      case 'performance': return 'warning';
      case 'system': return 'info';
      default: return 'info';
    }
  }

  private showBrowserNotification(alert: Alert): void {
    if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
      new Notification(`AutonomAI Alert: ${alert.title}`, {
        body: alert.message,
        icon: '/favicon.ico'
      });
    }
  }

  requestNotificationPermission(): void {
    if (typeof Notification !== 'undefined' && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }
}

// Global alert manager instance
const alertManager = new AlertManager();

// React hook for alerts
export function useAlerts() {
  const [alerts, setAlerts] = useState<Alert[]>(() => alertManager.getAlerts());
  const [config, setConfig] = useState<AlertConfig>(() => alertManager.getConfig());

  useEffect(() => {
    const unsubscribe = alertManager.subscribe(setAlerts);
    return unsubscribe;
  }, []);

  const checkThresholds = useCallback((metrics: Record<string, number>) => {
    alertManager.checkThresholds(metrics);
    setAlerts(alertManager.getAlerts());
  }, []);

  const acknowledgeAlert = useCallback((alertId: string) => {
    alertManager.acknowledgeAlert(alertId);
    setAlerts(alertManager.getAlerts());
  }, []);

  const acknowledgeAllAlerts = useCallback(() => {
    alertManager.acknowledgeAllAlerts();
    setAlerts(alertManager.getAlerts());
  }, []);

  const clearAlert = useCallback((alertId: string) => {
    alertManager.clearAlert(alertId);
    setAlerts(alertManager.getAlerts());
  }, []);

  const clearAcknowledgedAlerts = useCallback(() => {
    alertManager.clearAcknowledgedAlerts();
    setAlerts(alertManager.getAlerts());
  }, []);

  const updateConfig = useCallback((updates: Partial<AlertConfig>) => {
    alertManager.updateConfig(updates);
    setConfig(alertManager.getConfig());
  }, []);

  const updateThreshold = useCallback((thresholdId: string, updates: Partial<AlertThreshold>) => {
    alertManager.updateThreshold(thresholdId, updates);
    setConfig(alertManager.getConfig());
  }, []);

  const requestNotificationPermission = useCallback(() => {
    alertManager.requestNotificationPermission();
  }, []);

  return {
    alerts,
    config,
    checkThresholds,
    acknowledgeAlert,
    acknowledgeAllAlerts,
    clearAlert,
    clearAcknowledgedAlerts,
    updateConfig,
    updateThreshold,
    requestNotificationPermission
  };
}

export { alertManager };