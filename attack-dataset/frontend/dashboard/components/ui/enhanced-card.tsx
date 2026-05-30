import { ReactNode } from "react";

interface EnhancedCardProps {
  children: ReactNode;
  className?: string;
  hover?: boolean;
  gradient?: boolean;
  glass?: boolean;
  onClick?: () => void;
}

export function EnhancedCard({ 
  children, 
  className = "", 
  hover = true, 
  gradient = false,
  glass = false,
  onClick 
}: EnhancedCardProps) {
  const baseClasses = "rounded-xl border transition-all duration-300";
  
  const variantClasses = [
    glass ? "bg-white/5 backdrop-blur-xl border-white/10" : "bg-slate-800/50 border-slate-700",
    gradient ? "bg-gradient-to-br from-slate-800/50 to-slate-900/50" : "",
    hover ? "hover:border-slate-600 hover:shadow-lg hover:shadow-cyan-500/10 hover:-translate-y-1" : "",
    onClick ? "cursor-pointer active:scale-[0.98]" : "",
    className
  ].filter(Boolean).join(" ");

  return (
    <div className={variantClasses} onClick={onClick}>
      {children}
    </div>
  );
}

interface CardHeaderProps {
  children: ReactNode;
  className?: string;
}

export function CardHeader({ children, className = "" }: CardHeaderProps) {
  return (
    <div className={`p-6 border-b border-slate-700/50 ${className}`}>
      {children}
    </div>
  );
}

interface CardContentProps {
  children: ReactNode;
  className?: string;
}

export function CardContent({ children, className = "" }: CardContentProps) {
  return (
    <div className={`p-6 ${className}`}>
      {children}
    </div>
  );
}

interface CardFooterProps {
  children: ReactNode;
  className?: string;
}

export function CardFooter({ children, className = "" }: CardFooterProps) {
  return (
    <div className={`p-6 border-t border-slate-700/50 ${className}`}>
      {children}
    </div>
  );
}