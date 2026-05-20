"use client";

import { useState, useEffect } from "react";
import { useServiceMonitor, ServiceStatus } from "@/lib/serviceMonitor";

interface Service {
  id: string;
  name: string;
  port: number;
  status: "operational" | "down" | "starting" | "stopping" | "restarting";
  description: string;
  type: "api" | "database" | "cache" | "orchestrator" | "monitoring" | "integration";
}

export default function ServicesControlPanel() {
  const { 
    statuses: monitorStatuses, 
    isMonitoring, 
    cacheStats,
    startMonitoring, 
    stopMonitoring, 
    checkService, 
    checkAllServices, 
    restartService,
    updateServiceConfig,
    clearCache 
  } = useServiceMonitor();

  const [services, setServices] = useState<Service[]>([
    {
      id: "knowledge-engine",
      name: "Knowledge Engine",
      port: 8000,
      status: "down",
      description: "Core API and backend logic for attack operations",
      type: "api"
    },
    {
      id: "realtime-analyzer",
      name: "Real-time Analyzer",
      port: 8001,
      status: "down",
      description: "Live attack pattern analysis and detection",
      type: "monitoring"
    },
    {
      id: "opsec-monitor",
      name: "OpSec Monitor",
      port: 8002,
      status: "down",
      description: "Security monitoring and alerting system",
      type: "monitoring"
    },
    {
      id: "orchestrator",
      name: "Orchestrator",
      port: 3001,
      status: "down",
      description: "Multi-agent coordination and workflow management",
      type: "orchestrator"
    },
    {
      id: "integration-hub",
      name: "Integration Hub",
      port: 8500,
      status: "down",
      description: "External service integrations and plugins",
      type: "integration"
    },
    {
      id: "qdrant",
      name: "Qdrant",
      port: 6333,
      status: "down",
      description: "Vector database for AI/ML search capabilities",
      type: "database"
    },
    {
      id: "postgresql",
      name: "PostgreSQL",
      port: 5432,
      status: "down",
      description: "Primary data storage and persistence layer",
      type: "database"
    }
  ]);

  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Check service status using serviceMonitor
  const checkServiceStatus = async (service: Service) => {
    try {
      const result = await checkService(service.id);
      const status = result.status === 'operational' ? 'operational' : 'down';
      
      setServices(prev => prev.map(s => 
        s.id === service.id ? { ...s, status: status as any } : s
      ));
    } catch (error) {
      console.error(`Failed to check status for ${service.name}:`, error);
      setServices(prev => prev.map(s => 
        s.id === service.id ? { ...s, status: "down" } : s
      ));
    }
  };

  // Check all services using serviceMonitor
  const checkAllServicesStatus = async () => {
    setIsRefreshing(true);
    try {
      const results = await checkAllServices();
      const updatedServices = services.map(service => {
        const result = results.find(r => r.serviceId === service.id);
        const status: 'operational' | 'down' = result?.status === 'operational' ? 'operational' : 'down';
        return {
          ...service,
          status
        };
      });
      setServices(updatedServices);
    } catch (error) {
      console.error("Failed to check services status:", error);
    }
    setIsRefreshing(false);
  };

  // Start service using serviceMonitor
  const handleStartService = async (service: Service) => {
    setServices(prev => prev.map(s => 
      s.id === service.id ? { ...s, status: "starting" } : s
    ));

    try {
      const result = await restartService(service.id);
      
      if (result) {
        // Wait a moment for the service to start
        await new Promise(resolve => setTimeout(resolve, 3000));
        // Refresh all services to get updated status
        await checkAllServicesStatus();
      } else {
        setServices(prev => prev.map(s => 
          s.id === service.id ? { ...s, status: "down" } : s
        ));
      }
    } catch (error) {
      console.error(`Failed to start ${service.name}:`, error);
      setServices(prev => prev.map(s => 
        s.id === service.id ? { ...s, status: "down" } : s
      ));
    }
  };

  // Stop service - note: serviceMonitor doesn't have stopService, so we'll just update status
  const handleStopService = async (service: Service) => {
    setServices(prev => prev.map(s => 
      s.id === service.id ? { ...s, status: "stopping" } : s
    ));

    try {
      // For now, just mark as down since the serviceMonitor doesn't have stop functionality
      // In production, this would call the backend API to stop the service
      await new Promise(resolve => setTimeout(resolve, 2000));
      setServices(prev => prev.map(s => 
        s.id === service.id ? { ...s, status: "down" } : s
      ));
    } catch (error) {
      console.error(`Failed to stop ${service.name}:`, error);
      setServices(prev => prev.map(s => 
        s.id === service.id ? { ...s, status: "operational" } : s
      ));
    }
  };

  // Start all services
  const startAllServices = async () => {
    setIsRefreshing(true);
    for (const service of services) {
      if (service.status !== "operational") {
        await handleStartService(service);
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    }
    setIsRefreshing(false);
  };

  // Stop all services
  const stopAllServices = async () => {
    setIsRefreshing(true);
    for (const service of services) {
      if (service.status === "operational") {
        await handleStopService(service);
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    }
    setIsRefreshing(false);
  };

  // Get status color
  const getStatusColor = (status: string) => {
    switch (status) {
      case "operational": return "bg-green-500";
      case "down": return "bg-red-500";
      case "starting": return "bg-yellow-500 animate-pulse";
      case "stopping": return "bg-orange-500 animate-pulse";
      case "restarting": return "bg-purple-500 animate-pulse";
      default: return "bg-gray-500";
    }
  };

  // Get status text
  const getStatusText = (status: string) => {
    switch (status) {
      case "operational": return "Running";
      case "down": return "Stopped";
      case "starting": return "Starting...";
      case "stopping": return "Stopping...";
      case "restarting": return "Restarting...";
      default: return status;
    }
  };

  // Get type icon
  const getTypeIcon = (type: string) => {
    switch (type) {
      case "api": return "⚡";
      case "database": return "🗄️";
      case "cache": return "⚡";
      case "orchestrator": return "🎯";
      case "monitoring": return "📊";
      case "integration": return "🔗";
      default: return "📦";
    }
  };

  // Check status on mount
  useEffect(() => {
    checkAllServicesStatus();
    startMonitoring(3000); // Start optimized monitoring with 3 second interval
    
    return () => {
      stopMonitoring();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Sync monitor statuses with service list
  useEffect(() => {
    setServices(prevServices => 
      prevServices.map(service => {
        const monitorStatus = monitorStatuses.find(s => s.id === service.id);
        if (monitorStatus) {
          return {
            ...service,
            status: monitorStatus.status,
            autoRestart: monitorStatus.autoRestart,
            restartCount: monitorStatus.restartCount,
            lastRestart: monitorStatus.lastRestart,
            responseTime: monitorStatus.responseTime
          } as any;
        }
        return service;
      })
    );
  }, [monitorStatuses]);

  const operationalCount = services.filter(s => s.status === "operational").length;
  const totalCount = services.length;

  // Handle auto-restart toggle
  const toggleAutoRestart = (serviceId: string) => {
    const service = services.find(s => s.id === serviceId);
    if (service) {
      const newAutoRestart = !(service as any).autoRestart;
      updateServiceConfig(serviceId, { autoRestart: newAutoRestart });
    }
  };

  // Handle manual restart
  const handleRestartService = async (serviceId: string) => {
    setIsRefreshing(true);
    try {
      await restartService(serviceId);
    } catch (error) {
      console.error('Failed to restart service:', error);
    }
    setIsRefreshing(false);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-cyan-400">Services Control Panel</h2>
          <p className="text-slate-400">Manage and monitor all OpsecAI services</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-sm text-slate-400">
            <span className="text-green-400 font-semibold">{operationalCount}</span>/{totalCount} Running
          </div>
          <div className="text-xs text-slate-500">
            Cache: {cacheStats.size}/{cacheStats.maxSize}
          </div>
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-lg text-sm transition-colors"
          >
            {showAdvanced ? "Hide Advanced" : "Advanced"}
          </button>
          <button
            onClick={async () => {
              setIsRefreshing(true);
              await checkAllServices();
              setIsRefreshing(false);
            }}
            disabled={isRefreshing}
            className="bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-lg text-sm transition-colors disabled:opacity-50"
          >
            {isRefreshing ? "Refreshing..." : "Refresh Status"}
          </button>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="flex gap-4">
        <button
          onClick={startAllServices}
          disabled={isRefreshing || operationalCount === totalCount}
          className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm transition-colors disabled:opacity-50"
        >
          🚀 Start All
        </button>
        <button
          onClick={stopAllServices}
          disabled={isRefreshing || operationalCount === 0}
          className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg text-sm transition-colors disabled:opacity-50"
        >
          ⏹️ Stop All
        </button>
        {showAdvanced && (
          <button
            onClick={clearCache}
            className="bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg text-sm transition-colors"
          >
          🗑️ Clear Cache
        </button>
        )}
      </div>

      {/* Advanced Controls */}
      {showAdvanced && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
          <h3 className="text-lg font-semibold text-white mb-4">Advanced Monitoring Controls</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-slate-900/50 rounded-lg p-4">
              <div className="text-sm text-slate-400 mb-1">Monitoring Status</div>
              <div className={`text-lg font-bold ${isMonitoring ? 'text-green-400' : 'text-red-400'}`}>
                {isMonitoring ? 'Active' : 'Inactive'}
              </div>
              <div className="text-xs text-slate-500 mt-1">3 second interval</div>
            </div>
            <div className="bg-slate-900/50 rounded-lg p-4">
              <div className="text-sm text-slate-400 mb-1">Cache Efficiency</div>
              <div className="text-lg font-bold text-cyan-400">
                {cacheStats.size}/{cacheStats.maxSize}
              </div>
              <div className="text-xs text-slate-500 mt-1">LRU cache with 5s TTL</div>
            </div>
            <div className="bg-slate-900/50 rounded-lg p-4">
              <div className="text-sm text-slate-400 mb-1">Performance</div>
              <div className="text-lg font-bold text-purple-400">
                Optimized
              </div>
              <div className="text-xs text-slate-500 mt-1">Concurrent health checks</div>
            </div>
          </div>
        </div>
      )}

      {/* Services Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {services.map((service) => (
          <div
            key={service.id}
            className="bg-slate-800/50 border border-slate-700 rounded-lg p-4"
          >
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-3">
                <span className="text-2xl">{getTypeIcon(service.type)}</span>
                <div>
                  <h3 className="font-semibold text-white text-sm">{service.name}</h3>
                  <p className="text-xs text-slate-400">Port {service.port}</p>
                  {(service as any).responseTime && (
                    <p className="text-xs text-slate-500">{(service as any).responseTime}ms</p>
                  )}
                </div>
              </div>
              <div className={`w-3 h-3 rounded-full ${getStatusColor(service.status)}`} />
            </div>

            <p className="text-xs text-slate-400 mb-3">{service.description}</p>

            <div className="flex items-center justify-between mb-3">
              <span className={`text-xs px-2 py-1 rounded ${
                service.status === "operational" ? "bg-green-900 text-green-300" :
                service.status === "down" ? "bg-red-900 text-red-300" :
                service.status === "restarting" ? "bg-purple-900 text-purple-300" :
                "bg-yellow-900 text-yellow-300"
              }`}>
                {getStatusText(service.status)}
              </span>
              <button
                onClick={() => checkServiceStatus(service)}
                className="text-xs text-slate-400 hover:text-white transition-colors"
              >
                Check
              </button>
            </div>

            <div className="flex gap-2">
              {service.status === "operational" ? (
                <button
                  onClick={() => handleStopService(service)}
                  disabled={isRefreshing}
                  className="flex-1 bg-red-600 hover:bg-red-700 text-white px-3 py-2 rounded text-xs transition-colors disabled:opacity-50"
                >
                  Stop
                </button>
              ) : (
                <button
                  onClick={() => handleStartService(service)}
                  disabled={isRefreshing}
                  className="flex-1 bg-green-600 hover:bg-green-700 text-white px-3 py-2 rounded text-xs transition-colors disabled:opacity-50"
                >
                  Start
                </button>
              )}
              {showAdvanced && (
                <button
                  onClick={() => handleRestartService(service.id)}
                  disabled={isRefreshing}
                  className="flex-1 bg-yellow-600 hover:bg-yellow-700 text-white px-3 py-2 rounded text-xs transition-colors disabled:opacity-50"
                >
                  Restart
                </button>
              )}
              <button
                onClick={() => checkServiceStatus(service)}
                disabled={isRefreshing}
                className="flex-1 bg-slate-700 hover:bg-slate-600 text-white px-3 py-2 rounded text-xs transition-colors disabled:opacity-50"
              >
                Check
              </button>
            </div>

            {/* Advanced service info */}
            {showAdvanced && (
              <div className="mt-3 pt-3 border-t border-slate-700 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400">Auto-restart</span>
                  <button
                    onClick={() => toggleAutoRestart(service.id)}
                    className={`w-8 h-4 rounded-full transition-colors ${
                      (service as any).autoRestart ? 'bg-green-600' : 'bg-slate-600'
                    }`}
                  >
                    <div className={`w-3 h-3 bg-white rounded-full transition-transform ${
                      (service as any).autoRestart ? 'translate-x-4' : 'translate-x-0.5'
                    }`} />
                  </button>
                </div>
                {(service as any).restartCount > 0 && (
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-400">Restarts</span>
                    <span className="text-yellow-400">{(service as any).restartCount}</span>
                  </div>
                )}
                {(service as any).lastRestart && (
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-400">Last restart</span>
                    <span className="text-slate-300">
                      {new Date((service as any).lastRestart).toLocaleTimeString()}
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Service Groups */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
          <h3 className="text-lg font-semibold text-white mb-3">Core Services</h3>
          <div className="space-y-2">
            {services.filter(s => s.type === "api").map(service => (
              <div key={service.id} className="flex items-center justify-between">
                <span className="text-sm text-slate-300">{service.name}</span>
                <div className={`w-2 h-2 rounded-full ${getStatusColor(service.status)}`} />
              </div>
            ))}
          </div>
        </div>

        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
          <h3 className="text-lg font-semibold text-white mb-3">Data Services</h3>
          <div className="space-y-2">
            {services.filter(s => s.type === "database" || s.type === "cache").map(service => (
              <div key={service.id} className="flex items-center justify-between">
                <span className="text-sm text-slate-300">{service.name}</span>
                <div className={`w-2 h-2 rounded-full ${getStatusColor(service.status)}`} />
              </div>
            ))}
          </div>
        </div>

        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
          <h3 className="text-lg font-semibold text-white mb-3">Auxiliary Services</h3>
          <div className="space-y-2">
            {services.filter(s => s.type === "monitoring" || s.type === "orchestrator" || s.type === "integration").map(service => (
              <div key={service.id} className="flex items-center justify-between">
                <span className="text-sm text-slate-300">{service.name}</span>
                <div className={`w-2 h-2 rounded-full ${getStatusColor(service.status)}`} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}