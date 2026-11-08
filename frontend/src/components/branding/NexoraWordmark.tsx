import React from "react";
import { NexoraLogo } from "./NexoraLogo";

interface NexoraWordmarkProps {
  className?: string;
  logoSize?: number;
  showBadge?: boolean;
}

export const NexoraWordmark: React.FC<NexoraWordmarkProps> = ({
  className = "",
  logoSize = 28,
  showBadge = true,
}) => {
  return (
    <div className={`flex items-center gap-2.5 select-none ${className}`}>
      <NexoraLogo size={logoSize} />
      <div className="flex items-center gap-1.5">
        <span className="font-extrabold tracking-wider text-lg bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-800 dark:from-white dark:via-cyan-100 dark:to-indigo-200 bg-clip-text text-transparent">
          NEXORA
        </span>
        {showBadge && (
          <span className="text-[10px] uppercase font-bold tracking-widest px-1.5 py-0.5 rounded-full bg-gradient-to-r from-cyan-500/10 to-indigo-500/10 text-cyan-600 dark:text-cyan-400 border border-cyan-500/20">
            AI
          </span>
        )}
      </div>
    </div>
  );
};
