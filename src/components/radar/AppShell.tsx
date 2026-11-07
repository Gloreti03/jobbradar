import { Link, useRouter, useRouterState } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, Briefcase, Check, ChevronRight, FlaskConical, Globe2, Lock, Radar as RadarIcon, UserRound } from "lucide-react";
import type { ReactNode } from "react";
import { api, demo, qk, USE_MOCKS, API_URL } from "@/api";
import { RadarGlyph } from "./shared";

export function useProfileQuery() {
  return useQuery({ queryKey: qk.profile, queryFn: api.getProfile });
}

function NavItem({ to, icon, label, number, disabled }: {
  to: "/profile" | "/radar" | "/applications"; icon: ReactNode; label: string; number: string; disabled?: boolean;
}) {
  const content = <>{icon}<span>{label}</span><span className="nav-index">{disabled ? <Lock className="size-3" /> : number}</span></>;
  return disabled ? <div className="workspace-nav-link opacity-40" title="Create your profile to unlock Radar">{content}</div> : (
    <Link to={to} className="workspace-nav-link" activeProps={{ className: "workspace-nav-link is-active" }}>{content}</Link>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const profile = useProfileQuery();
  const qc = useQueryClient();
  const router = useRouter();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const hasProfile = profile.isSuccess;
  const name = profile.data?.profile.name;
  const initials = name?.split(/\s+/).slice(0, 2).map((n) => n[0]).join("") || "R";
  const page = pathname.startsWith("/profile") ? "Your profile" : pathname.startsWith("/radar") ? "Discover opportunities" : pathname.startsWith("/jobs") ? "Opportunity details" : pathname.startsWith("/interview") ? "Interview practice" : "Your applications";
  const switchDemo = (state: "empty" | "populated") => {
    demo.setProfileState(state);
    qc.clear();
    router.navigate({ to: "/profile" });
  };

  return (
    <div className="workspace-shell">
      <a className="skip-link" href="#workspace-content">Skip to content</a>
      <aside className="workspace-sidebar no-print">
        <Link to="/radar" className="workspace-brand" aria-label="Radar home">
          <RadarGlyph className="size-10" />
          <div><span className="brand-name">radar<span className="text-sidebar-primary">.</span></span><span className="brand-caption">A little direction. A bigger future.</span></div>
        </Link>
        <div className="sidebar-location"><Globe2 className="size-3.5" /><span>OSLO WORKSPACE</span><span className="status-dot" /></div>
        <div className="sidebar-section-label">YOUR NEXT CHAPTER</div>
        <nav aria-label="Main navigation" className="workspace-navigation">
          <NavItem to="/profile" icon={<UserRound />} label="Your profile" number="01" />
          <NavItem to="/radar" icon={<RadarIcon />} label="Radar" number="02" disabled={!hasProfile} />
          <NavItem to="/applications" icon={<Briefcase />} label="Applications" number="03" />
        </nav>
        <div className="sidebar-journey">
          <div className="sidebar-section-label">FROM POTENTIAL TO POSSIBILITY</div>
          <p>work that<br /><span>feels like you.</span></p>
          <div className="journey-track" aria-hidden="true"><span /><span /><span /><ArrowUpRight className="size-4" /></div>
          <span className="text-xs text-sidebar-foreground/60">Know yourself. Find your fit. Go for it.</span>
        </div>
        <div className="sidebar-footer">
          {USE_MOCKS ? <div className="demo-controls">
            <div className="flex items-center gap-2 text-xs font-semibold text-sidebar-primary"><FlaskConical className="size-3.5" /> Demo workspace</div>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <button onClick={() => switchDemo("empty")}>No CV yet</button>
              <button onClick={() => switchDemo("populated")}>Sample profile</button>
            </div>
            <button className="mt-2 w-full" onClick={() => { demo.reset(); qc.clear(); router.navigate({ to: "/profile" }); }}>Reset demo</button>
          </div> : <div className="workspace-mode" title={API_URL}><span className="status-dot" /> Live workspace</div>}
          <Link to="/profile" className="sidebar-person">
            <div className="person-avatar">{initials}</div>
            <div className="min-w-0 flex-1"><div className="truncate text-sm font-semibold">{name || "Your workspace"}</div><div className="mt-0.5 flex items-center gap-1 text-xs text-sidebar-foreground/60">{hasProfile ? <><Check className="size-3" /> Profile connected</> : "Start with your story"}</div></div>
            <ChevronRight className="size-4 opacity-50" />
          </Link>
        </div>
      </aside>
      <div className="workspace-body">
        <header className="workspace-topbar no-print">
          <div className="flex min-w-0 items-center gap-2 text-sm"><span className="hidden text-muted-foreground sm:inline">Workspace</span><ChevronRight className="hidden size-3 text-muted-foreground sm:block" /><span className="truncate font-medium">{page}</span></div>
          <div className="flex items-center gap-4"><span className="topbar-location"><span className="status-dot" /> Oslo, Norway</span><span className="topbar-avatar" aria-label={name || "Your profile"}>{initials}</span></div>
        </header>
        <main id="workspace-content" className="workspace-content"><div className="page-enter">{children}</div></main>
      </div>
    </div>
  );
}
