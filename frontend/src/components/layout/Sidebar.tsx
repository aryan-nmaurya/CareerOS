import { ClipboardList, LayoutDashboard, Map, MessageSquare, Settings } from "lucide-react";
import { NavLink } from "react-router-dom";

import { cn } from "@/lib/cn";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/roadmap", label: "Roadmap", icon: Map },
  { to: "/interview", label: "Interviews", icon: MessageSquare },
  { to: "/history", label: "History", icon: ClipboardList },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  return (
    <nav
      aria-label="Main"
      className={cn(
        "flex shrink-0 gap-1 border-line bg-surface",
        // Bottom bar on small screens, rail on md and up.
        "fixed inset-x-0 bottom-0 z-20 justify-around border-t p-2",
        "md:static md:h-dvh md:w-56 md:flex-col md:justify-start md:border-r md:border-t-0 md:p-3",
      )}
    >
      <div className="hidden px-2 pb-4 pt-2 md:block">
        <span className="text-lg font-semibold tracking-tight text-text-primary">
          Career<span className="text-accent">OS</span>
        </span>
      </div>

      {NAV.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          end={to === "/"}
          className={({ isActive }) =>
            cn(
              "flex flex-1 flex-col items-center gap-1 rounded-lg px-3 py-2 text-xs font-medium",
              "transition-colors duration-fast",
              "md:w-full md:flex-none md:flex-row md:gap-2.5 md:text-sm",
              isActive
                ? "bg-accent-soft text-accent"
                : "text-text-secondary hover:bg-surface-hover hover:text-text-primary",
            )
          }
        >
          <Icon className="size-[18px]" />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
