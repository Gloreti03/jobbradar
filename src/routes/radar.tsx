import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { AlertCircle, ArrowRight, CircleHelp, Info, Lock, MapPin, Minus, Plus, Radar as RadarIcon } from "lucide-react";
import { api, isNotFound } from "@/api";
import type { RadarRequest, RadarResponse, RadarResult } from "@/types";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { useProfileQuery } from "@/components/radar/AppShell";
import { EmptyState, ErrorState, LanguageBadges, LoadingState, PageHeader, PostedDate, RadarGlyph, ScoreRing, VerdictBadge, formatDate } from "@/components/radar/shared";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/radar")({
  head: () => ({
    meta: [
      { title: "Radar — RADAR" },
      { name: "description", content: "Scan recent Oslo job postings ranked by fit with your profile." },
      { property: "og:title", content: "Radar — RADAR" },
      { property: "og:description", content: "Scan recent Oslo job postings ranked by fit with your profile." },
    ],
  }),
  component: RadarPage,
});

const DAYS: RadarRequest["days"][] = [3, 7, 14, 30];
const LAST = ["radar", "last"] as const;

function RadarPage() {
  const profile = useProfileQuery();
  const qc = useQueryClient();
  const [days, setDays] = useState<RadarRequest["days"]>(7);
  const [englishOnly, setEnglishOnly] = useState(false);
  const last = useQuery<RadarResponse | null>({ queryKey: LAST, queryFn: () => null, staleTime: Infinity, gcTime: Infinity });
  const scan = useMutation({
    mutationFn: () => api.scanRadar({ days, english_only: englishOnly, refresh: true }),
    onSuccess: (r) => qc.setQueryData(LAST, r),
  });

  if (profile.isPending) return <LoadingState />;
  if (profile.isError) {
    if (isNotFound(profile.error))
      return (
        <EmptyState
          icon={<Lock className="size-6" />}
          title="Radar is locked"
          body="Upload your CV first — Radar ranks jobs against your profile."
          action={<Button asChild><Link to="/profile">Go to Profile</Link></Button>}
        />
      );
    return <ErrorState error={profile.error} onRetry={() => profile.refetch()} />;
  }

  const data = last.data;

  return (
    <div>
      <PageHeader title="Radar" subtitle="Recent Oslo postings, ranked by how well they fit your profile. Scores reflect profile fit — not your chances of being hired." />

      <div className="mb-8 flex flex-wrap items-center gap-8 rounded-2xl border bg-card p-6 shadow-card">
        <button
          onClick={() => scan.mutate()}
          disabled={scan.isPending}
          className="group relative flex items-center gap-5 rounded-full text-left disabled:cursor-wait"
          aria-label="Scan for jobs"
        >
          <RadarGlyph active={scan.isPending} className="size-24 shadow-glow transition-transform group-hover:scale-105" />
          <div>
            <div className="text-xl font-semibold">{scan.isPending ? "Scanning…" : data ? "Scan again" : "Start scan"}</div>
            <div className="text-sm text-muted-foreground">{scan.isPending ? "Ranking postings against your profile" : "Find matching jobs now"}</div>
          </div>
        </button>

        <div className="ml-auto flex flex-wrap items-center gap-8">
          <div>
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Posted within</div>
            <div className="flex rounded-lg bg-muted p-1">
              {DAYS.map((d) => (
                <button
                  key={d}
                  onClick={() => setDays(d)}
                  className={cn("rounded-md px-3 py-1.5 text-sm font-medium transition-colors", d === days ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground")}
                >
                  {d} days
                </button>
              ))}
            </div>
          </div>
          <label className="flex items-center gap-3">
            <Switch checked={englishOnly} onCheckedChange={setEnglishOnly} />
            <div>
              <div className="text-sm font-medium">English-friendly only</div>
              <div className="text-xs text-muted-foreground">Hide postings that require Norwegian</div>
            </div>
          </label>
        </div>
      </div>

      {scan.isError && <ErrorState error={scan.error} onRetry={() => scan.mutate()} />}
      {!scan.isError && scan.isPending && !data && <LoadingState label="Scanning job postings…" />}
      {!scan.isError && !scan.isPending && !data && (
        <EmptyState icon={<RadarIcon className="size-6" />} title="No scan yet" body="Pick a time window and press Start scan to see jobs that fit your profile." />
      )}
      {!scan.isError && data && <Results data={data} dim={scan.isPending} />}
    </div>
  );
}

function Results({ data, dim }: { data: RadarResponse; dim: boolean }) {
  return (
    <div className={cn("transition-opacity", dim && "opacity-50")}>
      <div className="mb-4 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-muted-foreground">
        <span>
          <strong className="text-foreground">{data.results.length}</strong> matches · {data.candidates_count} candidates from {data.scanned_count} postings
        </span>
        <span>Window: last {data.days_used} days</span>
        <span>Scanned {formatDate(data.generated_at)}</span>
      </div>
      {data.widened && (
        <div className="mb-6 flex items-start gap-3 rounded-xl border border-info-foreground/20 bg-info-soft p-4 text-sm text-info-foreground">
          <Info className="mt-0.5 size-4 shrink-0" />
          <span>
            Few postings matched the last {data.days_requested} days, so we widened the search to the last <strong>{data.days_used} days</strong>.
          </span>
        </div>
      )}
      {data.results.length === 0 ? (
        <EmptyState icon={<RadarIcon className="size-6" />} title="No matching jobs" body="Try a longer time window or turn off the English-friendly filter." />
      ) : (
        <div className="grid gap-4">
          {data.results.map((r) => (
            <JobCard key={r.job.id} r={r} />
          ))}
        </div>
      )}
    </div>
  );
}

function JobCard({ r }: { r: RadarResult }) {
  const { job, match } = r;
  return (
    <Link to="/jobs/$id" params={{ id: String(job.id) }} className="group block rounded-xl border bg-card p-6 shadow-card transition-all hover:border-primary/40 hover:shadow-glow">
      <div className="flex gap-5">
        <ScoreRing score={match.score} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold group-hover:text-primary">{job.title}</h3>
              <div className="mt-0.5 flex flex-wrap items-center gap-x-3 text-sm text-muted-foreground">
                <span className="font-medium text-foreground">{job.company ?? "Unknown company"}</span>
                {job.location && <span className="inline-flex items-center gap-1"><MapPin className="size-3.5" />{job.location}</span>}
                <PostedDate job={job} />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <VerdictBadge verdict={match.verdict} />
              <ArrowRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-1 group-hover:text-primary" />
            </div>
          </div>
          <div className="mt-3"><LanguageBadges job={job} /></div>
          <div className="mt-4 grid gap-4 text-sm md:grid-cols-3">
            <Points icon={<Plus className="size-3.5" />} title="Why it fits" items={match.reasons} tone="text-primary" />
            <Points icon={<Minus className="size-3.5" />} title="Gaps" items={match.gaps} tone="text-warning-foreground" />
            <Points icon={<CircleHelp className="size-3.5" />} title="To clarify" items={match.to_clarify} tone="text-info-foreground" />
          </div>
        </div>
      </div>
    </Link>
  );
}

export function Points({ icon, title, items, tone }: { icon: React.ReactNode; title: string; items: string[]; tone: string }) {
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
