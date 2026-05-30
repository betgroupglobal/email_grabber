"use client";

import { useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Target,
  Shield,
  Plug,
  Brain,
  Radar,
  ListChecks,
  Lock,
  type LucideIcon,
} from "lucide-react";

const iconMap: Record<string, LucideIcon> = {
  Dashboard: LayoutDashboard,
  Target,
  Shield,
  Plug,
  Brain,
  Radar,
  ListChecks,
};

interface NavItem {
  id: string;
  label: string;
  icon: string;
  path: string;
  description?: string;
}

const navItems: NavItem[] = [
  { id: "home", label: "Home", icon: "Dashboard", path: "/", description: "Service health and engagements" },
  { id: "operations", label: "Autonomous Ops", icon: "Target", path: "/operations", description: "Unified assessment, attack ops, and MITRE AI" },
  { id: "scanner", label: "Scanner", icon: "Radar", path: "/scanner", description: "Network reconnaissance" },
  { id: "integration", label: "Integration Hub", icon: "Plug", path: "/integration-hub", description: "Plugin catalog and health" },
  { id: "ai-chat", label: "AI Assistant", icon: "Brain", path: "/ai-chat", description: "AI-powered analysis" },
];

export function SidebarNav() {
  const [collapsed, setCollapsed] = useState(false);
  const [expandedItem, setExpandedItem] = useState<string | null>(null);
  const router = useRouter();
  const pathname = usePathname();

  const isActive = (path: string) => {
    if (path === "/") return pathname === "/";
    return pathname?.startsWith(path);
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setCollapsed(!collapsed)}
        className="lg:hidden fixed top-4 left-4 z-50 p-2 bg-slate-800 rounded-lg border border-slate-700 text-white"
        aria-label={collapsed ? "Open navigation" : "Close navigation"}
      >
        {collapsed ? (
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        ) : (
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        )}
      </button>

      <aside
        className={`fixed top-0 left-0 h-full bg-slate-900/95 backdrop-blur-xl border-r border-slate-700/50 transition-all duration-300 z-40 ${
          collapsed ? "w-16" : "w-72"
        } ${collapsed ? "lg:w-16" : "lg:w-72"}`}
      >
        <div className="p-6 border-b border-slate-700/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-purple-600 flex items-center justify-center">
              <Lock className="h-5 w-5 text-white" />
            </div>
            {!collapsed && (
              <div>
                <h1 className="font-bold text-lg text-white">AutonomAI</h1>
                <p className="text-xs text-slate-400">Autonomous Operations</p>
              </div>
            )}
          </div>
        </div>

        <nav className="p-4 space-y-2">
          {navItems.map((item) => (
            <div key={item.id}>
              <button
                type="button"
                onClick={() => {
                  router.push(item.path);
                  if (window.innerWidth < 1024) setCollapsed(true);
                }}
                onMouseEnter={() => setExpandedItem(item.id)}
                onMouseLeave={() => setExpandedItem(null)}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 ${
                  isActive(item.path)
                    ? "bg-gradient-to-r from-cyan-600/20 to-purple-600/20 text-cyan-400 border border-cyan-500/30"
                    : "text-slate-400 hover:bg-slate-800 hover:text-white border border-transparent"
                }`}
              >
                {(() => {
                  const IconComponent = iconMap[item.icon];
                  return IconComponent ? (
                    <IconComponent className="h-5 w-5 flex-shrink-0" />
                  ) : (
                    <span className="text-xl flex-shrink-0">{item.icon}</span>
                  );
                })()}
                {!collapsed && (
                  <span className="font-medium flex-1 text-left">{item.label}</span>
                )}
              </button>

              {collapsed && expandedItem === item.id && (
                <div className="fixed left-20 ml-2 px-3 py-2 bg-slate-800 rounded-lg border border-slate-700 text-sm text-white whitespace-nowrap z-50 shadow-xl">
                  <div className="font-medium">{item.label}</div>
                  {item.description && (
                    <div className="text-xs text-slate-400 mt-1">{item.description}</div>
                  )}
                </div>
              )}
            </div>
          ))}
        </nav>

        <div className="absolute bottom-4 left-4 right-4">
          <button
            type="button"
            onClick={() => setCollapsed(!collapsed)}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors border border-slate-700"
          >
            {collapsed ? "Expand" : "Collapse"}
          </button>
        </div>
      </aside>

      {collapsed && (
        <div
          className="lg:hidden fixed inset-0 bg-black/50 z-30"
          onClick={() => setCollapsed(false)}
          role="presentation"
        />
      )}
    </>
  );
}
