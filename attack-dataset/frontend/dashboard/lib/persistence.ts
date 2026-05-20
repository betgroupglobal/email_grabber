"use client";

import { useState } from 'react';

// Dashboard state persistence utilities using localStorage

const STORAGE_PREFIX = 'opsecai_dashboard_';
const STORAGE_VERSION = 'v1';

interface PersistedState {
  version: string;
  timestamp: number;
  data: any;
}

export function saveState(key: string, data: any): void {
  try {
    const state: PersistedState = {
      version: STORAGE_VERSION,
      timestamp: Date.now(),
      data
    };
    localStorage.setItem(`${STORAGE_PREFIX}${key}`, JSON.stringify(state));
  } catch (error) {
    console.error(`Error saving state for key "${key}":`, error);
  }
}

export function loadState<T>(key: string, defaultValue: T): T {
  try {
    const item = localStorage.getItem(`${STORAGE_PREFIX}${key}`);
    if (!item) return defaultValue;

    const state: PersistedState = JSON.parse(item);
    
    // Check version compatibility
    if (state.version !== STORAGE_VERSION) {
      console.warn(`State version mismatch for key "${key}". Expected ${STORAGE_VERSION}, got ${state.version}`);
      return defaultValue;
    }

    // Check if state is too old (7 days)
    const maxAge = 7 * 24 * 60 * 60 * 1000; // 7 days in milliseconds
    if (Date.now() - state.timestamp > maxAge) {
      console.warn(`State for key "${key}" is too old, using default`);
      return defaultValue;
    }

    return state.data as T;
  } catch (error) {
    console.error(`Error loading state for key "${key}":`, error);
    return defaultValue;
  }
}

export function removeState(key: string): void {
  try {
    localStorage.removeItem(`${STORAGE_PREFIX}${key}`);
  } catch (error) {
    console.error(`Error removing state for key "${key}":`, error);
  }
}

export function clearAllState(): void {
  try {
    const keys = Object.keys(localStorage);
    keys.forEach(key => {
      if (key.startsWith(STORAGE_PREFIX)) {
        localStorage.removeItem(key);
      }
    });
  } catch (error) {
    console.error('Error clearing all state:', error);
  }
}

export function getStateKeys(): string[] {
  try {
    const keys = Object.keys(localStorage);
    return keys
      .filter(key => key.startsWith(STORAGE_PREFIX))
      .map(key => key.replace(STORAGE_PREFIX, ''));
  } catch (error) {
    console.error('Error getting state keys:', error);
    return [];
  }
}

// React hook for persistent state
export function usePersistentState<T>(
  key: string,
  defaultValue: T
): [T, (value: T | ((prev: T) => T)) => void] {
  const [state, setState] = useState<T>(() => loadState(key, defaultValue));

  const setPersistentState = (value: T | ((prev: T) => T)) => {
    setState(prev => {
      const newValue = typeof value === 'function' ? (value as (prev: T) => T)(prev) : value;
      saveState(key, newValue);
      return newValue;
    });
  };

  return [state, setPersistentState];
}

// Specific state management for dashboard components
export const DashboardStateKeys = {
  ACTIVE_TAB: 'active_tab',
  FILTERS: 'filters',
  TIME_RANGE: 'time_range',
  SELECTED_SESSION: 'selected_session',
  TERMINAL_ACTIVE: 'terminal_active',
  VIEW_PREFERENCES: 'view_preferences',
  ALERT_CONFIG: 'alert_config',
  COLUMN_VISIBILITY: 'column_visibility',
  LAYOUT_CONFIG: 'layout_config'
} as const;

// Helper functions for common dashboard state
export function saveActiveTab(tab: string): void {
  saveState(DashboardStateKeys.ACTIVE_TAB, tab);
}

export function loadActiveTab(defaultTab: string = 'monitor'): string {
  return loadState(DashboardStateKeys.ACTIVE_TAB, defaultTab);
}

export function saveFilters(filters: Record<string, any>): void {
  saveState(DashboardStateKeys.FILTERS, filters);
}

export function loadFilters(): Record<string, any> {
  return loadState(DashboardStateKeys.FILTERS, {});
}

export function saveTimeRange(range: '24h' | '7d' | '30d'): void {
  saveState(DashboardStateKeys.TIME_RANGE, range);
}

export function loadTimeRange(defaultRange: '24h' | '7d' | '30d' = '7d'): '24h' | '7d' | '30d' {
  return loadState(DashboardStateKeys.TIME_RANGE, defaultRange);
}

export function saveViewPreferences(preferences: Record<string, any>): void {
  saveState(DashboardStateKeys.VIEW_PREFERENCES, preferences);
}

export function loadViewPreferences(): Record<string, any> {
  return loadState(DashboardStateKeys.VIEW_PREFERENCES, {
    theme: 'dark',
    compactMode: false,
    showAnimations: true
  });
}