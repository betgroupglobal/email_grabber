"use client";

import { useEffect, useRef } from "react";

interface ChartData {
  label: string;
  value: number;
  color?: string;
}

interface BarChartProps {
  data: ChartData[];
  height?: number;
  showLabels?: boolean;
  animated?: boolean;
}

export function BarChart({ data, height = 200, showLabels = true, animated = true }: BarChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    
    canvas.width = rect.width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    const maxValue = Math.max(...data.map(d => d.value));
    const barWidth = (rect.width / data.length) * 0.6;
    const gap = (rect.width / data.length) * 0.4;
    const startX = gap / 2;

    let progress = 0;
    const animate = () => {
      progress += animated ? 0.05 : 1;
      if (progress > 1) progress = 1;

      ctx.clearRect(0, 0, rect.width, height);

      data.forEach((item, index) => {
        const x = startX + index * (barWidth + gap);
        const barHeight = (item.value / maxValue) * (height - 30) * progress;
        const y = height - barHeight - 20;

        // Bar gradient
        const gradient = ctx.createLinearGradient(x, y, x, height - 20);
        const color = item.color || "#06b6d4";
        gradient.addColorStop(0, color);
        gradient.addColorStop(1, `${color}40`);

        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.roundRect(x, y, barWidth, barHeight, [4, 4, 0, 0]);
        ctx.fill();

        // Label
        if (showLabels && progress === 1) {
          ctx.fillStyle = "#94a3b8";
          ctx.font = "11px system-ui";
          ctx.textAlign = "center";
          ctx.fillText(item.label, x + barWidth / 2, height - 5);
          
          ctx.fillStyle = "#ffffff";
          ctx.font = "bold 12px system-ui";
          ctx.fillText(item.value.toString(), x + barWidth / 2, y - 5);
        }
      });

      if (progress < 1) {
        animationRef.current = requestAnimationFrame(animate);
      }
    };

    animate();

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [data, height, showLabels, animated]);

  return <canvas ref={canvasRef} className="w-full" style={{ height }} />;
}

interface DonutChartProps {
  data: ChartData[];
  size?: number;
  showLegend?: boolean;
  animated?: boolean;
}

export function DonutChart({ data, size = 200, showLegend = true, animated = true }: DonutChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.scale(dpr, dpr);

    const centerX = size / 2;
    const centerY = size / 2;
    const radius = (size - 40) / 2;
    const innerRadius = radius * 0.6;
    const total = data.reduce((sum, item) => sum + item.value, 0);

    let progress = 0;
    const animate = () => {
      progress += animated ? 0.05 : 1;
      if (progress > 1) progress = 1;

      ctx.clearRect(0, 0, size, size);

      let startAngle = -Math.PI / 2;

      data.forEach((item) => {
        const sliceAngle = (item.value / total) * 2 * Math.PI * progress;
        const endAngle = startAngle + sliceAngle;

        // Draw slice
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, startAngle, endAngle);
        ctx.arc(centerX, centerY, innerRadius, endAngle, startAngle, true);
        ctx.closePath();
        
        const color = item.color || "#06b6d4";
        ctx.fillStyle = color;
        ctx.fill();

        // Add subtle border
        ctx.strokeStyle = "#1e293b";
        ctx.lineWidth = 2;
        ctx.stroke();

        startAngle = endAngle;
      });

      // Center text
      if (progress === 1) {
        ctx.fillStyle = "#ffffff";
        ctx.font = "bold 24px system-ui";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(total.toString(), centerX, centerY);
        
        ctx.fillStyle = "#94a3b8";
        ctx.font = "12px system-ui";
        ctx.fillText("Total", centerX, centerY + 20);
      }

      if (progress < 1) {
        animationRef.current = requestAnimationFrame(animate);
      }
    };

    animate();

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [data, size, animated]);

  return (
    <div className="flex flex-col items-center gap-4">
      <canvas ref={canvasRef} style={{ width: size, height: size }} />
      {showLegend && (
        <div className="flex flex-wrap gap-4 justify-center">
          {data.map((item, index) => (
            <div key={index} className="flex items-center gap-2">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: item.color || "#06b6d4" }}
              />
              <span className="text-sm text-slate-400">{item.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

interface LineChartProps {
  data: { x: string; y: number }[];
  height?: number;
  color?: string;
  showArea?: boolean;
  animated?: boolean;
}

export function LineChart({ data, height = 200, color = "#06b6d4", showArea = true, animated = true }: LineChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    
    canvas.width = rect.width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    const maxValue = Math.max(...data.map(d => d.y));
    const padding = 30;
    const chartWidth = rect.width - padding * 2;
    const chartHeight = height - padding * 2;

    let progress = 0;
    const animate = () => {
      progress += animated ? 0.05 : 1;
      if (progress > 1) progress = 1;

      ctx.clearRect(0, 0, rect.width, height);

      // Grid lines
      ctx.strokeStyle = "#334155";
      ctx.lineWidth = 1;
      for (let i = 0; i <= 4; i++) {
        const y = padding + (chartHeight / 4) * i;
        ctx.beginPath();
        ctx.moveTo(padding, y);
        ctx.lineTo(rect.width - padding, y);
        ctx.stroke();
      }

      // Calculate points
      const points = data.map((item, index) => ({
        x: padding + (chartWidth / (data.length - 1)) * index,
        y: padding + chartHeight - (item.y / maxValue) * chartHeight
      }));

      // Draw area
      if (showArea) {
        ctx.beginPath();
        ctx.moveTo(points[0].x, height - padding);
        
        for (let i = 0; i < points.length; i++) {
          const point = points[i];
          const targetY = point.y;
          const currentY = height - padding - (height - padding - targetY) * progress;
          ctx.lineTo(point.x, currentY);
        }
        
        ctx.lineTo(points[points.length - 1].x, height - padding);
        ctx.closePath();
        
        const gradient = ctx.createLinearGradient(0, padding, 0, height - padding);
        gradient.addColorStop(0, `${color}40`);
        gradient.addColorStop(1, `${color}00`);
        ctx.fillStyle = gradient;
        ctx.fill();
      }

      // Draw line
      ctx.beginPath();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.lineJoin = "round";
      ctx.lineCap = "round";

      for (let i = 0; i < points.length; i++) {
        const point = points[i];
        const targetY = point.y;
        const currentY = height - padding - (height - padding - targetY) * progress;
        
        if (i === 0) {
          ctx.moveTo(point.x, currentY);
        } else {
          ctx.lineTo(point.x, currentY);
        }
      }
      ctx.stroke();

      // Draw points
      if (progress === 1) {
        points.forEach((point) => {
          ctx.beginPath();
          ctx.arc(point.x, point.y, 4, 0, Math.PI * 2);
          ctx.fillStyle = color;
          ctx.fill();
          ctx.strokeStyle = "#1e293b";
          ctx.lineWidth = 2;
          ctx.stroke();
        });
      }

      if (progress < 1) {
        animationRef.current = requestAnimationFrame(animate);
      }
    };

    animate();

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [data, height, color, showArea, animated]);

  return <canvas ref={canvasRef} className="w-full" style={{ height }} />;
}