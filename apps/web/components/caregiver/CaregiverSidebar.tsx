"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  ArrowLeft,
  BarChart2,
  BellRing,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
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
  { href: "/dashboard", icon: BarChart2, label: "Insights & Alerts" },
  { href: "/alerts", icon: BellRing, label: "Alerts" },
  { href: "/profile", icon: User, label: "Profile" },
];

export default function CaregiverSidebar() {
  const [expanded, setExpanded] = useState(false);
  const pathname = usePathname();
  const router = useRouter();

  async function handleSignOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/auth");
  }

  return (
    <aside
      className={cn(
        "flex h-full flex-col border-r bg-card transition-[width] duration-200",
        expanded ? "w-48" : "w-14"
      )}
    >
      <div className="flex flex-col items-center gap-1 pt-3 pb-2">
        <Tooltip>
          <TooltipTrigger asChild>
            <Link
              href="/coaching"
              className="mx-auto flex h-10 w-10 items-center justify-center rounded-md bg-secondary text-secondary-foreground hover:bg-secondary/80"
              aria-label="Back to Coaching"
            >
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </TooltipTrigger>
          {!expanded && (
            <TooltipContent side="right">Back to Coaching</TooltipContent>
          )}
        </Tooltip>

        <button
          onClick={() => setExpanded(!expanded)}
          className="flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
          aria-label={expanded ? "Collapse sidebar" : "Expand sidebar"}
        >
          {expanded ? (
            <PanelLeftClose className="h-4 w-4" />
          ) : (
            <PanelLeftOpen className="h-4 w-4" />
          )}
        </button>
      </div>

      <div className="h-px w-full bg-border" />

      <nav className="flex flex-1 flex-col gap-1 px-2 pt-2">
        {NAV_ITEMS.map((item) => (
          <NavItem
            key={item.href}
            href={item.href}
            icon={item.icon}
            label={item.label}
            active={pathname.startsWith(item.href)}
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
                "flex h-9 items-center gap-3 rounded-md px-2.5 text-muted-foreground hover:bg-accent hover:text-foreground",
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

function NavItem({
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
              : "text-muted-foreground hover:bg-accent hover:text-foreground"
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
