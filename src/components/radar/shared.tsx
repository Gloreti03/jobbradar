import { AlertTriangle, Loader2, RefreshCw, WifiOff, ServerCrash, CalendarX } from "lucide-react";
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
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1.5 max-w-2xl text-muted-foreground">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Panel({ children, className, title, icon }: { children: ReactNode; className?: string; title?: string; icon?: ReactNode }) {
  return (
    <section className={cn("rounded-xl border bg-card p-6 shadow-card", className)}>
      {title && (
        <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
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
    <div className="flex items-center justify-center gap-3 py-24 text-muted-foreground">
      <Loader2 className="size-5 animate-spin text-primary" /> {label}
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
    <div className="flex flex-col items-center rounded-xl border border-dashed bg-card/60 px-6 py-16 text-center">
      <div className="mb-4 rounded-full bg-primary-soft p-3 text-primary">{icon}</div>
      <h3 className="text-lg font-semibold">{title}</h3>
      {body && <p className="mt-1 max-w-sm text-sm text-muted-foreground">{body}</p>}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

const verdictStyle: Record<Verdict, string> = {
  strong: "bg-primary text-primary-foreground",
  good: "bg-primary-soft text-accent-foreground",
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
          className="fill-none stroke-primary"
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
    primary: "bg-primary-soft text-accent-foreground",
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
    <div className={cn("relative aspect-square overflow-hidden rounded-full border border-primary/30 bg-primary-soft", className)}>
      <div className="absolute inset-[18%] rounded-full border border-primary/25" />
      <div className="absolute inset-[36%] rounded-full border border-primary/25" />
      <div
        className={cn("absolute inset-0 rounded-full", active ? "animate-radar-sweep" : "animate-[radar-sweep_8s_linear_infinite]")}
        style={{ background: "conic-gradient(from 0deg, transparent 0deg, color-mix(in oklab, var(--primary) 45%, transparent) 60deg, transparent 61deg)" }}
      />
      {active && <div className="absolute inset-[30%] rounded-full bg-primary/30 animate-radar-ping" />}
      <div className="absolute left-1/2 top-1/2 size-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary" />
    </div>
  );
}
