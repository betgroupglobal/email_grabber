import { ButtonHTMLAttributes, forwardRef, ReactNode } from "react";

interface EnhancedButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "success" | "danger" | "warning" | "ghost" | "gradient";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  icon?: ReactNode;
  iconPosition?: "left" | "right";
}

export const EnhancedButton = forwardRef<HTMLButtonElement, EnhancedButtonProps>(
  ({ 
    children, 
    variant = "primary", 
    size = "md", 
    loading = false,
    icon,
    iconPosition = "left",
    className = "",
    disabled,
    ...props 
  }, ref) => {
    const baseClasses = "inline-flex items-center justify-center font-medium rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-900 disabled:opacity-50 disabled:cursor-not-allowed";
    
    const variantClasses = {
      primary: "bg-cyan-600 hover:bg-cyan-700 text-white focus:ring-cyan-500 shadow-lg shadow-cyan-500/25",
      secondary: "bg-slate-700 hover:bg-slate-600 text-white focus:ring-slate-500",
      success: "bg-green-600 hover:bg-green-700 text-white focus:ring-green-500 shadow-lg shadow-green-500/25",
      danger: "bg-red-600 hover:bg-red-700 text-white focus:ring-red-500 shadow-lg shadow-red-500/25",
      warning: "bg-yellow-600 hover:bg-yellow-700 text-white focus:ring-yellow-500",
      ghost: "bg-transparent hover:bg-slate-700 text-slate-300 hover:text-white focus:ring-slate-500",
      gradient: "bg-gradient-to-r from-cyan-600 to-purple-600 hover:from-cyan-700 hover:to-purple-700 text-white focus:ring-cyan-500 shadow-lg shadow-purple-500/25"
    };
    
    const sizeClasses = {
      sm: "px-3 py-1.5 text-sm",
      md: "px-4 py-2 text-sm",
      lg: "px-6 py-3 text-base"
    };

    const classes = [
      baseClasses,
      variantClasses[variant],
      sizeClasses[size],
      loading ? "cursor-wait" : "",
      className
    ].filter(Boolean).join(" ");

    return (
      <button
        ref={ref}
        className={classes}
        disabled={disabled || loading}
        {...props}
      >
        {loading && (
          <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        )}
        {!loading && icon && iconPosition === "left" && (
          <span className="mr-2">{icon}</span>
        )}
        {children}
        {!loading && icon && iconPosition === "right" && (
          <span className="ml-2">{icon}</span>
        )}
      </button>
    );
  }
);

EnhancedButton.displayName = "EnhancedButton";