import { Link, useRouter } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Briefcase, FlaskConical, Radar as RadarIcon, UserRound, Lock } from "lucide-react";
import type { ReactNode } from "react";
import { api, demo, qk, USE_MOCKS, API_URL } from "@/api";
import { cn } from "@/lib/utils";
import { RadarGlyph } from "./shared";

export function useProfileQuery() {
  return useQuery({ queryKey: qk.profile, queryFn: api.getProfile });
}

function NavItem({ to, icon, label, disabled, hint }: { to: "/profile" | "/radar" | "/applications"; icon: ReactNode; label: string; disabled?: boolean; hint?: string }) {
  const base = "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors";
  if (disabled)
    return (
      <div className={cn(base, "cursor-not-allowed opacity-45")} title={hint}>
        {icon}
        {label}
        <Lock className="ml-auto size-3.5" />
      </div>
    );
  return (
    <Link
      to={to}
      className={cn(base, "hover:bg-sidebar-accent hover:text-sidebar-accent-foreground")}
      activeProps={{ className: "bg-sidebar-accent text-sidebar-accent-foreground" }}
    >
      {icon}
      {label}
    </Link>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const profile = useProfileQuery();
  const qc = useQueryClient();
  const router = useRouter();
  const hasProfile = profile.isSuccess;

  const switchDemo = (state: "empty" | "populated") => {
    demo.setProfileState(state);
    qc.invalidateQueries();
    router.navigate({ to: "/profile" });
  };

  return (
    <div className="flex min-h-screen">
      <aside className="no-print sticky top-0 flex h-screen w-64 shrink-0 flex-col bg-sidebar p-4 text-sidebar-foreground">
        <Link to="/profile" className="mb-8 flex items-center gap-3 px-2 pt-2">
          <RadarGlyph className="size-9" />
          <div>
            <div className="text-lg font-bold tracking-[0.2em] text-sidebar-accent-foreground">RADAR</div>
            <div className="text-[11px] text-sidebar-foreground/60">Oslo job hunting</div>
          </div>
        </Link>
        <nav className="flex flex-col gap-1">
          <NavItem to="/profile" icon={<UserRound className="size-4" />} label="Profile" />
          <NavItem to="/radar" icon={<RadarIcon className="size-4" />} label="Radar" disabled={!hasProfile} hint="Create your profile first" />
          <NavItem to="/applications" icon={<Briefcase className="size-4" />} label="Applications" />
        </nav>

        <div className="mt-auto space-y-3">
          {USE_MOCKS ? (
            <div className="rounded-lg border border-sidebar-border p-3">
              <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-sidebar-primary">
                <FlaskConical className="size-3.5" /> Demo data
              </div>
              <p className="mb-2 text-[11px] leading-snug text-sidebar-foreground/60">Test profile states:</p>
              <div className="grid grid-cols-2 gap-1.5">
                <button onClick={() => switchDemo("empty")} className="rounded-md bg-sidebar-accent px-2 py-1 text-[11px] hover:text-sidebar-accent-foreground">
                  No CV yet
                </button>
                <button onClick={() => switchDemo("populated")} className="rounded-md bg-sidebar-accent px-2 py-1 text-[11px] hover:text-sidebar-accent-foreground">
                  Sample profile
                </button>
              </div>
              <button
                onClick={() => {
                  demo.reset();
                  qc.invalidateQueries();
                }}
                className="mt-2 w-full text-[11px] text-sidebar-foreground/50 hover:text-sidebar-accent-foreground"
              >
                Reset demo
              </button>
            </div>
          ) : (
            <div className="truncate px-2 text-[11px] text-sidebar-foreground/50" title={API_URL}>
              Live API · {API_URL}
            </div>
          )}
        </div>
      </aside>
      <main className="min-w-0 flex-1">
        <div className="mx-auto max-w-6xl px-10 py-10">{children}</div>
      </main>
    </div>
  );
}
