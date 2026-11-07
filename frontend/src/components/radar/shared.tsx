import { AlertCircle, AlertTriangle, Loader2, RefreshCw, WifiOff, ServerCrash, CalendarX } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/api";
import { cn } from "@/lib/utils";
import type { ApplicationStatus, JobOut, Verdict } from "@/types";

export function formatDate(iso: string | null | undefined) {
  if (!iso) return null;
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export function PostedDate({ job, className }: { job: JobOut; className?: string }) {
  const d = formatDate(job.posted_at);
  return d ? (
    <span className={className}>Posted {d}</span>
  ) : (
    <span className={cn("inline-flex items-center gap-1", className)}>
      <CalendarX className="size-3.5" /> Date unknown
    </span>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-heading">
      <div className="min-w-0">
        <div className="eyebrow mb-3"><span className="inline-block h-px w-6 bg-primary" /> THE NEXT CHAPTER</div>
        <h1>{title}</h1>
        {subtitle && <p className="mt-3 max-w-2xl text-sm leading-relaxed text-muted-foreground">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Panel({ children, className, title, icon }: { children: ReactNode; className?: string; title?: string; icon?: ReactNode }) {
  return (
    <section className={cn("radar-panel", className)}>
      {title && (
        <h2 className="mb-5 flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.12em] text-muted-foreground">
          {icon}
          {title}
        </h2>
      )}
      {children}
    </section>
  );
}

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" className="loading-state">
      <RadarGlyph active className="mb-5 size-16" />
      <p className="text-sm font-semibold text-foreground">{label}</p>
      <span className="mt-2 text-xs text-muted-foreground">Good things take a moment.</span>
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const e = error instanceof ApiError ? error : null;
  const Icon = e?.kind === "network" ? WifiOff : e?.kind === "server" ? ServerCrash : AlertTriangle;
  const title =
    e?.kind === "network" ? "Can't reach the server" : e?.kind === "server" ? "The server ran into a problem" : "Something went wrong";
  return (
    <div className="mx-auto flex max-w-md flex-col items-center py-20 text-center">
      <div className="mb-4 rounded-full bg-destructive/10 p-3 text-destructive">
        <Icon className="size-6" />
      </div>
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="mt-1 text-sm text-muted-foreground">{error instanceof Error ? error.message : String(error)}</p>
      {onRetry && (
        <Button variant="outline" className="mt-6" onClick={onRetry}>
          <RefreshCw /> Try again
        </Button>
      )}
    </div>
  );
}

export function EmptyState({ icon, title, body, action }: { icon: ReactNode; title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon">{icon}</div>
      <h3 className="text-xl font-semibold tracking-tight">{title}</h3>
      {body && <p className="mt-2 max-w-sm text-sm leading-relaxed text-muted-foreground">{body}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

const verdictStyle: Record<Verdict, string> = {
  strong: "bg-emerald-800 text-white",
  good: "bg-emerald-50 text-emerald-900",
  stretch: "bg-warning-soft text-warning-foreground",
  poor: "bg-muted text-muted-foreground",
};
export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  return (
    <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize", verdictStyle[verdict])}>
      {verdict} fit
    </span>
  );
}

export function ScoreRing({ score, size = 56 }: { score: number; size?: number }) {
  const color = score >= 70 ? "stroke-emerald-700" : score >= 45 ? "stroke-warning" : "stroke-muted-foreground";
  const r = (size - 6) / 2;
  const c = 2 * Math.PI * r;
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} title="Profile fit score — not a hiring probability">
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} className="fill-none stroke-muted" strokeWidth={5} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          className={cn("score-arc fill-none", color)}
          strokeWidth={5}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - score / 100)}
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center font-mono text-sm font-semibold">{score}</span>
    </div>
  );
}

export function LanguageBadges({ job }: { job: JobOut }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {job.language === "en" && <Chip tone="info">English posting</Chip>}
      {job.language === "no" && <Chip tone="muted">Norwegian posting</Chip>}
      {job.norwegian_required === true && <Chip tone="warning">Norwegian required</Chip>}
      {job.norwegian_required === false && <Chip tone="primary">No Norwegian needed</Chip>}
      {job.norwegian_required == null && <Chip tone="muted">Norwegian: unclear</Chip>}
    </div>
  );
}

export function Chip({ children, tone = "muted" }: { children: ReactNode; tone?: "muted" | "primary" | "warning" | "info" }) {
  const t = {
    muted: "bg-muted text-muted-foreground",
    primary: "bg-emerald-50 text-emerald-900",
    warning: "bg-warning-soft text-warning-foreground",
    info: "bg-info-soft text-info-foreground",
  }[tone];
  return <span className={cn("rounded-md px-2 py-0.5 text-xs font-medium", t)}>{children}</span>;
}

export const statusLabel: Record<ApplicationStatus, string> = {
  draft: "Draft",
  applied: "Applied",
  interviewing: "Interviewing",
  rejected: "Rejected",
  offer: "Offer",
};
export function StatusBadge({ status }: { status: ApplicationStatus }) {
  const tone = { draft: "muted", applied: "info", interviewing: "primary", rejected: "warning", offer: "primary" } as const;
  return <Chip tone={tone[status]}>{statusLabel[status]}</Chip>;
}

export function RadarGlyph({ active, className }: { active?: boolean; className?: string }) {
  return (
    <div aria-hidden="true" className={cn("radar-glyph relative aspect-square overflow-hidden rounded-full border border-primary/30 bg-primary-soft", className)}>
      <div className="absolute left-0 right-0 top-1/2 border-t border-primary/15" />
      <div className="absolute bottom-0 left-1/2 top-0 border-l border-primary/15" />
      <div className="absolute inset-[18%] rounded-full border border-primary/25" />
      <div className="absolute inset-[36%] rounded-full border border-primary/25" />
      <div
        className={cn("radar-beam absolute inset-0 rounded-full", active ? "animate-radar-sweep" : "animate-[radar-sweep_12s_linear_infinite]")}
        style={{ background: "conic-gradient(from 0deg, transparent 0deg, color-mix(in oklab, var(--primary) 45%, transparent) 60deg, transparent 61deg)" }}
      />
      {active && <div className="absolute inset-[30%] rounded-full bg-primary/30 animate-radar-ping" />}
      <span className="absolute left-[30%] top-[25%] size-[4%] rounded-full bg-primary/70" />
      <span className="absolute bottom-[29%] right-[23%] size-[3%] rounded-full bg-primary/50" />
      <div className="absolute left-1/2 top-1/2 size-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary" />
    </div>
  );
}

export function CompanyMark({ name, className }: { name: string | null; className?: string }) {
  const title = name || "Company";
  const letters = title.split(/\s+/).slice(0, 2).map((word) => word[0]).join("");
  const tone = [...title].reduce((sum, letter) => sum + letter.charCodeAt(0), 0) % 4;
  return <div aria-hidden="true" className={cn("company-mark", `company-tone-${tone}`, className)}>{letters}</div>;
}

export function Points({ icon, title, items, tone }: { icon: ReactNode; title: string; items: string[]; tone: string }) {
  return (
    <div>
      <div className={cn("mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide", tone)}>
        {icon}
        {title}
      </div>
      {items.length ? (
        <ul className="space-y-1 text-foreground/80">
          {items.map((x) => <li key={x}>{x}</li>)}
        </ul>
      ) : (
        <p className="flex items-center gap-1 text-muted-foreground"><AlertCircle className="size-3" /> None noted</p>
      )}
    </div>
  );
}
