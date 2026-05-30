import { ReactNode } from "react";

interface FadeInProps {
  children: ReactNode;
  delay?: number;
  duration?: number;
  className?: string;
}

export function FadeIn({ children, delay = 0, duration = 300, className = "" }: FadeInProps) {
  return (
    <div
      className={className}
      style={{
        animation: `fadeIn ${duration}ms ease-out ${delay}ms both`,
      }}
    >
      {children}
    </div>
  );
}

interface SlideInProps {
  children: ReactNode;
  direction?: "up" | "down" | "left" | "right";
  delay?: number;
  duration?: number;
  className?: string;
}

export function SlideIn({ children, direction = "up", delay = 0, duration = 300, className = "" }: SlideInProps) {
  const animations = {
    up: "slideInUp",
    down: "slideInDown",
    left: "slideInLeft",
    right: "slideInRight"
  };

  return (
    <div
      className={className}
      style={{
        animation: `${animations[direction]} ${duration}ms ease-out ${delay}ms both`,
      }}
    >
      {children}
    </div>
  );
}

interface ScaleInProps {
  children: ReactNode;
  delay?: number;
  duration?: number;
  className?: string;
}

export function ScaleIn({ children, delay = 0, duration = 300, className = "" }: ScaleInProps) {
  return (
    <div
      className={className}
      style={{
        animation: `scaleIn ${duration}ms ease-out ${delay}ms both`,
      }}
    >
      {children}
    </div>
  );
}

interface PulseProps {
  children: ReactNode;
  className?: string;
}

export function Pulse({ children, className = "" }: PulseProps) {
  return (
    <div className={`animate-pulse ${className}`}>
      {children}
    </div>
  );
}

interface SpinnerProps {
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function Spinner({ size = "md", className = "" }: SpinnerProps) {
  const sizes = {
    sm: "w-4 h-4",
    md: "w-8 h-8",
    lg: "w-12 h-12"
  };

  return (
    <div className={`animate-spin rounded-full border-2 border-slate-600 border-t-cyan-500 ${sizes[size]} ${className}`} />
  );
}

// Add global CSS animations
export function GlobalAnimations() {
  return (
    <style jsx global>{`
      @keyframes fadeIn {
        from {
          opacity: 0;
        }
        to {
          opacity: 1;
        }
      }

      @keyframes slideInUp {
        from {
          opacity: 0;
          transform: translateY(20px);
        }
        to {
          opacity: 1;
          transform: translateY(0);
        }
      }

      @keyframes slideInDown {
        from {
          opacity: 0;
          transform: translateY(-20px);
        }
        to {
          opacity: 1;
          transform: translateY(0);
        }
      }

      @keyframes slideInLeft {
        from {
          opacity: 0;
          transform: translateX(-20px);
        }
        to {
          opacity: 1;
          transform: translateX(0);
        }
      }

      @keyframes slideInRight {
        from {
          opacity: 0;
          transform: translateX(20px);
        }
        to {
          opacity: 1;
          transform: translateX(0);
        }
      }

      @keyframes scaleIn {
        from {
          opacity: 0;
          transform: scale(0.9);
        }
        to {
          opacity: 1;
          transform: scale(1);
        }
      }
    `}</style>
  );
}