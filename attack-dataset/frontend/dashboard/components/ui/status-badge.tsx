import { ReactNode } from "react";

interface StatusBadgeProps {
  status: "success" | "warning" | "danger" | "info" | "neutral";
  children: ReactNode;
  size?: "sm" | "md";
  pulse?: boolean;
  icon?: ReactNode;
}

export function StatusBadge({ status, children, size = "md", pulse = false, icon }: StatusBadgeProps) {
  const statusConfig = {
    success: {
      bg: "bg-green-900/30",
      text: "text-green-300",
      border: "border-green-700/50",
      icon: "✓"
    },
    warning: {
      bg: "bg-yellow-900/30",
      text: "text-yellow-300",
      border: "border-yellow-700/50",
      icon: "⚠"
    },
    danger: {
      bg: "bg-red-900/30",
      text: "text-red-300",
      border: "border-red-700/50",
      icon: "✕"
    },
    info: {
      bg: "bg-cyan-900/30",
      text: "text-cyan-300",
      border: "border-cyan-700/50",
      icon: "ℹ"
    },
    neutral: {
      bg: "bg-slate-700/30",
      text: "text-slate-300",
      border: "border-slate-600/50",
      icon: "○"
    }
  };

  const config = statusConfig[status];
  const sizeClasses = size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm";

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border ${config.bg} ${config.text} ${config.border} ${sizeClasses} ${pulse ? "animate-pulse" : ""}`}>
      {icon || <span>{config.icon}</span>}
      {children}
    </span>
  );
}

interface ProgressRingProps {
  progress: number;
  size?: number;
  strokeWidth?: number;
  className?: string;
}

export function ProgressRing({ progress, size = 40, strokeWidth = 4, className = "" }: ProgressRingProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (progress / 100) * circumference;

  const getColor = (progress: number) => {
    if (progress >= 80) return "#22c55e"; // green
    if (progress >= 60) return "#eab308"; // yellow
    if (progress >= 40) return "#f97316"; // orange
    return "#ef4444"; // red
  };

  return (
    <div className={`relative inline-flex items-center justify-center ${className}`} style={{ width: size, height: size }}>
      <svg className="transform -rotate-90" width={size} height={size}>
        <circle
          className="text-slate-700"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          fill="transparent"
          r={radius}
          cx={size / 2}
          cy={size / 2}
        />
        <circle
          className="transition-all duration-500 ease-out"
          stroke={getColor(progress)}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          fill="transparent"
          r={radius}
          cx={size / 2}
          cy={size / 2}
        />
      </svg>
      <span className="absolute text-xs font-medium text-white">
        {Math.round(progress)}%
      </span>
    </div>
  );
}