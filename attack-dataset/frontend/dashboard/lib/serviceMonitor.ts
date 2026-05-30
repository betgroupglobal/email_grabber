"use client";

import { useState, useEffect, useCallback, useRef } from 'react';

// Simple LRU Cache implementation
class LRUCache<K, V> {
  private cache: Map<K, { value: V; timestamp: number }>;
  private maxSize: number;
  private ttl: number;

  constructor(maxSize: number = 100, ttl: number = 5000) {
    this.cache = new Map();
    this.maxSize = maxSize;
    this.ttl = ttl;
  }

  get(key: K): V | null {
    const entry = this.cache.get(key);
    if (!entry) return null;

    if (Date.now() - entry.timestamp > this.ttl) {
      this.cache.delete(key);
      return null;
    }

    // Move to end (most recently used)
    this.cache.delete(key);
    this.cache.set(key, entry);
    return entry.value;
  }

  set(key: K, value: V): void {
    // Remove oldest if at capacity
    if (this.cache.size >= this.maxSize) {
      const firstKey = this.cache.keys().next().value;
      if (firstKey !== undefined) {
        this.cache.delete(firstKey);
      }
    }

    this.cache.set(key, { value, timestamp: Date.now() });
  }

  clear(): void {
    this.cache.clear();
  }

  size(): number {
    return this.cache.size;
  }
}

// Environment hash cache
const environmentHashCache = new LRUCache<string, string>(128, 60000); // 1 minute TTL

function getEnvironmentHash(): string {
  const envString = JSON.stringify(process.env);
  const cacheKey = 'env_hash';
  
  const cached = environmentHashCache.get(cacheKey);
  if (cached) return cached;

  // Simple hash function
  let hash = 0;
  for (let i = 0; i < envString.length; i++) {
    const char = envString.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  
  const hashString = Math.abs(hash).toString(36);
  environmentHashCache.set(cacheKey, hashString);
  return hashString;
}

// Service interfaces
export interface ServiceConfig {
  id: string;
  name: string;
  port: number;
  healthCheckEndpoint: string;
  autoRestart: boolean;
  maxRestartAttempts: number;
  restartDelay: number;
}

export interface ServiceStatus {
  id: string;
  name: string;
  port: number;
  status: 'operational' | 'down' | 'starting' | 'stopping' | 'restarting';
  lastCheck: number;
  responseTime?: number;
  restartCount: number;
  lastRestart?: number;
  autoRestart: boolean;
}

export interface HealthCheckResult {
  serviceId: string;
  status: 'operational' | 'down';
  responseTime: number;
  timestamp: number;
}

// Service monitoring class
class ServiceMonitor {
  private healthCheckCache: LRUCache<string, HealthCheckResult>;
  private services: Map<string, ServiceConfig>;
  private serviceStatus: Map<string, ServiceStatus>;
  private monitoringInterval: NodeJS.Timeout | null = null;
  private recoveryInterval: NodeJS.Timeout | null = null;
  private listeners: Set<(statuses: ServiceStatus[]) => void> = new Set();

  constructor() {
    this.healthCheckCache = new LRUCache<string, HealthCheckResult>(100, 5000); // 5 second TTL
    this.services = new Map();
    this.serviceStatus = new Map();
    this.initializeDefaultServices();
  }

  private initializeDefaultServices(): void {
    const defaultServices: ServiceConfig[] = [
      {
        id: 'knowledge-engine',
        name: 'Knowledge Engine',
        port: 8000,
        healthCheckEndpoint: '/health',
        autoRestart: true,
        maxRestartAttempts: 5,
        restartDelay: 5000
      },
      {
        id: 'realtime-analyzer',
        name: 'Real-time Analyzer',
        port: 8001,
        healthCheckEndpoint: '/health',
        autoRestart: true,
        maxRestartAttempts: 5,
        restartDelay: 5000
      },
      {
        id: 'opsec-monitor',
        name: 'OpSec Monitor',
        port: 8002,
        healthCheckEndpoint: '/health',
        autoRestart: true,
        maxRestartAttempts: 5,
        restartDelay: 5000
      },
      {
        id: 'orchestrator',
        name: 'Orchestrator',
        port: 3001,
        healthCheckEndpoint: '/system/health',
        autoRestart: true,
        maxRestartAttempts: 5,
        restartDelay: 5000
      },
      {
        id: 'integration-hub',
        name: 'Integration Hub',
        port: 8500,
        healthCheckEndpoint: '/health',
        autoRestart: true,
        maxRestartAttempts: 5,
        restartDelay: 5000
      },
      {
        id: 'qdrant',
        name: 'Qdrant',
        port: 6333,
        healthCheckEndpoint: '/health',
        autoRestart: false, // Database services typically shouldn't auto-restart
        maxRestartAttempts: 3,
        restartDelay: 10000
      },
      {
        id: 'postgresql',
        name: 'PostgreSQL',
        port: 5432,
        healthCheckEndpoint: '/health',
        autoRestart: false, // Database services typically shouldn't auto-restart
        maxRestartAttempts: 3,
        restartDelay: 10000
      }
    ];

    defaultServices.forEach(service => {
      this.services.set(service.id, service);
      this.serviceStatus.set(service.id, {
        id: service.id,
        name: service.name,
        port: service.port,
        status: 'down',
        lastCheck: 0,
        restartCount: 0,
        autoRestart: service.autoRestart
      });
    });
  }

  subscribe(listener: (statuses: ServiceStatus[]) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private notifyListeners(): void {
    const statuses = Array.from(this.serviceStatus.values());
    this.listeners.forEach(listener => listener(statuses));
  }

  // Optimized health check with caching
  async checkServiceHealth(serviceId: string): Promise<HealthCheckResult> {
    const service = this.services.get(serviceId);
    if (!service) {
      throw new Error(`Service ${serviceId} not found`);
    }

    const envHash = getEnvironmentHash();
    const cacheKey = `${serviceId}_${envHash}`;

    // Check cache first
    const cached = this.healthCheckCache.get(cacheKey);
    if (cached) {
      this.updateServiceStatus(serviceId, cached.status, cached.responseTime);
      return cached;
    }

    // Perform actual health check
    const startTime = Date.now();
    let status: 'operational' | 'down' = 'down';

    try {
      let healthEndpoint = service.healthCheckEndpoint;
      
      // Use special endpoints for specific services
      if (serviceId === 'qdrant') {
        healthEndpoint = '/healthz';
      } else if (serviceId === 'postgresql') {
        // PostgreSQL doesn't have HTTP endpoint, assume healthy if we get here
        status = 'operational';
      } else {
        const response = await fetch(`http://localhost:${service.port}${healthEndpoint}`, {
          method: 'GET',
          signal: AbortSignal.timeout(5000) // 5 second timeout
        });
        status = response.ok ? 'operational' : 'down';
      }
    } catch (error) {
      status = 'down';
    }

    const responseTime = Date.now() - startTime;
    const result: HealthCheckResult = {
      serviceId,
      status,
      responseTime,
      timestamp: Date.now()
    };

    // Cache the result
    this.healthCheckCache.set(cacheKey, result);
    this.updateServiceStatus(serviceId, status, responseTime);

    return result;
  }

  // Concurrent health checks for all services
  async checkAllServices(): Promise<HealthCheckResult[]> {
    const serviceIds = Array.from(this.services.keys());
    const checks = serviceIds.map(id => this.checkServiceHealth(id));
    return Promise.all(checks);
  }

  private updateServiceStatus(
    serviceId: string,
    status: 'operational' | 'down' | 'restarting',
    responseTime?: number
  ): void {
    const currentStatus = this.serviceStatus.get(serviceId);
    if (!currentStatus) return;

    const updatedStatus: ServiceStatus = {
      ...currentStatus,
      status,
      lastCheck: Date.now(),
      responseTime
    };

    this.serviceStatus.set(serviceId, updatedStatus);
    this.notifyListeners();
  }

  // Start monitoring with optimized interval
  startMonitoring(intervalMs: number = 3000): void {
    if (this.monitoringInterval) {
      clearInterval(this.monitoringInterval);
    }

    this.monitoringInterval = setInterval(() => {
      this.checkAllServices().catch(error => {
        console.error('Health check failed:', error);
      });
    }, intervalMs);

    // Start recovery monitoring
    this.startRecoveryMonitoring();
  }

  stopMonitoring(): void {
    if (this.monitoringInterval) {
      clearInterval(this.monitoringInterval);
      this.monitoringInterval = null;
    }
    if (this.recoveryInterval) {
      clearInterval(this.recoveryInterval);
      this.recoveryInterval = null;
    }
  }

  // Auto-restart and recovery logic
  private startRecoveryMonitoring(): void {
    if (this.recoveryInterval) {
      clearInterval(this.recoveryInterval);
    }

    this.recoveryInterval = setInterval(async () => {
      await this.checkAndRecoverServices();
    }, 10000); // Check every 10 seconds
  }

  private async checkAndRecoverServices(): Promise<void> {
    const statuses = Array.from(this.serviceStatus.values());

    for (const status of statuses) {
      const service = this.services.get(status.id);
      if (!service || !service.autoRestart) continue;

      if (status.status === 'down' && status.restartCount < service.maxRestartAttempts) {
        console.log(`Attempting to restart service: ${service.name}`);
        await this.restartService(status.id);
      }
    }
  }

  async restartService(serviceId: string): Promise<boolean> {
    const service = this.services.get(serviceId);
    if (!service) return false;

    const status = this.serviceStatus.get(serviceId);
    if (!status) return false;

    // Check if we've exceeded max restart attempts
    if (status.restartCount >= service.maxRestartAttempts) {
      console.log(`Max restart attempts reached for ${service.name}`);
      return false;
    }

    try {
      // Update status to restarting
      this.updateServiceStatus(serviceId, 'restarting');

      // Stop the service
      await this.stopService(serviceId);

      // Wait for restart delay
      await new Promise(resolve => setTimeout(resolve, service.restartDelay));

      // Start the service
      await this.startService(serviceId);

      // Update restart count and timestamp
      const updatedStatus: ServiceStatus = {
        ...this.serviceStatus.get(serviceId)!,
        restartCount: status.restartCount + 1,
        lastRestart: Date.now()
      };

      this.serviceStatus.set(serviceId, updatedStatus);

      // Wait for service to be ready
      await new Promise(resolve => setTimeout(resolve, 3000));

      // Check if service is now operational
      const healthResult = await this.checkServiceHealth(serviceId);
      
      if (healthResult.status === 'operational') {
        console.log(`Successfully restarted ${service.name}`);
        // Reset restart count on successful recovery
        updatedStatus.restartCount = 0;
        this.serviceStatus.set(serviceId, updatedStatus);
      }

      this.notifyListeners();
      return healthResult.status === 'operational';

    } catch (error) {
      console.error(`Failed to restart ${service.name}:`, error);
      this.updateServiceStatus(serviceId, 'down');
      return false;
    }
  }

  async startService(serviceId: string): Promise<boolean> {
    try {
      const response = await fetch('/api/services/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ serviceId })
      });

      if (!response.ok) throw new Error('Failed to start service');

      const result = await response.json();
      return result.success;
    } catch (error) {
      console.error(`Error starting service ${serviceId}:`, error);
      return false;
    }
  }

  async stopService(serviceId: string): Promise<boolean> {
    try {
      const response = await fetch('/api/services/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ serviceId })
      });

      if (!response.ok) throw new Error('Failed to stop service');

      const result = await response.json();
      return result.success;
    } catch (error) {
      console.error(`Error stopping service ${serviceId}:`, error);
      return false;
    }
  }

  getServiceStatus(serviceId: string): ServiceStatus | undefined {
    return this.serviceStatus.get(serviceId);
  }

  getAllServiceStatuses(): ServiceStatus[] {
    return Array.from(this.serviceStatus.values());
  }

  updateServiceConfig(serviceId: string, config: Partial<ServiceConfig>): void {
    const service = this.services.get(serviceId);
    if (service) {
      this.services.set(serviceId, { ...service, ...config });
      
      const status = this.serviceStatus.get(serviceId);
      if (status && config.autoRestart !== undefined) {
        status.autoRestart = config.autoRestart;
        this.serviceStatus.set(serviceId, status);
      }
    }
  }

  clearCache(): void {
    this.healthCheckCache.clear();
    environmentHashCache.clear();
  }

  getCacheStats(): { size: number; maxSize: number } {
    return {
      size: this.healthCheckCache.size(),
      maxSize: 100
    };
  }
}

// Global service monitor instance
const serviceMonitor = new ServiceMonitor();

// React hook for service monitoring
export function useServiceMonitor() {
  const [statuses, setStatuses] = useState<ServiceStatus[]>(() => 
    serviceMonitor.getAllServiceStatuses()
  );
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [cacheStats, setCacheStats] = useState(() => 
    serviceMonitor.getCacheStats()
  );

  useEffect(() => {
    const unsubscribe = serviceMonitor.subscribe((newStatuses) => {
      setStatuses(newStatuses);
      setCacheStats(serviceMonitor.getCacheStats());
    });

    return unsubscribe;
  }, []);

  const startMonitoring = useCallback((intervalMs: number = 3000) => {
    serviceMonitor.startMonitoring(intervalMs);
    setIsMonitoring(true);
  }, []);

  const stopMonitoring = useCallback(() => {
    serviceMonitor.stopMonitoring();
    setIsMonitoring(false);
  }, []);

  const checkService = useCallback(async (serviceId: string) => {
    return await serviceMonitor.checkServiceHealth(serviceId);
  }, []);

  const checkAllServices = useCallback(async () => {
    return await serviceMonitor.checkAllServices();
  }, []);

  const restartService = useCallback(async (serviceId: string) => {
    return await serviceMonitor.restartService(serviceId);
  }, []);

  const updateServiceConfig = useCallback((serviceId: string, config: Partial<ServiceConfig>) => {
    serviceMonitor.updateServiceConfig(serviceId, config);
    setStatuses(serviceMonitor.getAllServiceStatuses());
  }, []);

  const clearCache = useCallback(() => {
    serviceMonitor.clearCache();
    setCacheStats(serviceMonitor.getCacheStats());
  }, []);

  return {
    statuses,
    isMonitoring,
    cacheStats,
    startMonitoring,
    stopMonitoring,
    checkService,
    checkAllServices,
    restartService,
    updateServiceConfig,
    clearCache
  };
}

export { serviceMonitor };