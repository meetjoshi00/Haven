"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BarChart2,
  BellRing,
  Clock,
  Home,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  User,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { createClient } from "@/lib/supabase/client";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const NAV_ITEMS = [
  { href: "/coaching", icon: Home, label: "Home" },
  { href: "/dashboard", icon: BarChart2, label: "Insights" },
  { href: "/alerts", icon: BellRing, label: "Alerts" },
  { href: "/coaching/history", icon: Clock, label: "History" },
  { href: "/profile", icon: User, label: "Profile" },
  { href: "/coaching/settings", icon: Settings, label: "Settings" },
];

export default function Sidebar() {
  const [expanded, setExpanded] = useState<boolean>(() => {
    if (typeof window === "undefined") return true;
    const stored = localStorage.getItem("haven-sidebar-expanded");
    return stored !== null ? stored === "true" : true;
  });
  const pathname = usePathname();
  const router = useRouter();

  async function handleSignOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/auth");
  }

  const isActive = (href: string) => {
    if (href === "/coaching") return pathname === "/coaching";
    return pathname.startsWith(href);
  };

  return (
    <aside
      className={cn(
        "flex h-full flex-col border-r bg-card transition-[width] duration-200",
        expanded ? "w-48" : "w-14"
      )}
    >
      {/* Header: "Haven" brand + collapse toggle */}
      <div
        className={cn(
          "flex items-center border-b py-3",
          expanded ? "justify-between px-3" : "justify-center"
        )}
      >
        {expanded && (
          <span className="text-base font-semibold tracking-tight">Haven</span>
        )}
        <button
          onClick={() => {
            const next = !expanded;
            setExpanded(next);
            localStorage.setItem("haven-sidebar-expanded", String(next));
          }}
          className="flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-accent/50 hover:text-foreground"
          aria-label={expanded ? "Collapse sidebar" : "Expand sidebar"}
        >
          {expanded ? (
            <PanelLeftClose className="h-4 w-4" />
          ) : (
            <PanelLeftOpen className="h-4 w-4" />
          )}
        </button>
      </div>

      <nav className="flex flex-1 flex-col gap-1 px-2 pt-2">
        {NAV_ITEMS.map((item) => (
          <SidebarItem
            key={item.href}
            href={item.href}
            icon={item.icon}
            label={item.label}
            active={isActive(item.href)}
            expanded={expanded}
          />
        ))}
      </nav>

      <div className="px-2 pb-3">
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              onClick={handleSignOut}
              className={cn(
                "flex h-9 items-center gap-3 rounded-md px-2.5 text-muted-foreground hover:bg-accent/50 hover:text-foreground",
                expanded ? "w-full" : "w-9 justify-center"
              )}
              aria-label="Sign out"
            >
              <LogOut className="h-4 w-4 shrink-0" />
              {expanded && <span className="text-sm">Sign out</span>}
            </button>
          </TooltipTrigger>
          {!expanded && (
            <TooltipContent side="right">Sign out</TooltipContent>
          )}
        </Tooltip>
      </div>
    </aside>
  );
}

function SidebarItem({
  href,
  icon: Icon,
  label,
  active,
  expanded,
}: {
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  active: boolean;
  expanded: boolean;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Link
          href={href}
          className={cn(
            "flex h-9 items-center gap-3 rounded-md px-2.5 transition-colors",
            expanded ? "w-full" : "w-9 justify-center",
            active
              ? "bg-accent text-foreground"
              : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
          )}
          aria-label={label}
        >
          <Icon className="h-4 w-4 shrink-0" />
          {expanded && <span className="text-sm">{label}</span>}
        </Link>
      </TooltipTrigger>
      {!expanded && <TooltipContent side="right">{label}</TooltipContent>}
    </Tooltip>
  );
}
