import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ArrowRight, ArrowUpRight, ChevronDown, CircleHelp, Info, Loader2, Lock, MapPin, Minus, Plus, Radar as RadarIcon, Search, SlidersHorizontal } from "lucide-react";
import { api, isNotFound } from "@/api";
import type { RadarRequest, RadarResponse, RadarResult } from "@/types";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { useProfileQuery } from "@/components/radar/AppShell";
import { CompanyMark, EmptyState, ErrorState, LanguageBadges, LoadingState, PostedDate, RadarGlyph, ScoreRing, VerdictBadge, formatDate, Points } from "@/components/radar/shared";
import { cn } from "@/lib/utils";
import { ScanFunnel } from "@/components/radar/ScanFunnel";

export const Route = createFileRoute("/radar")({
  head: () => ({ meta: [
    { title: "Discover opportunities — JobbRadar" },
    { name: "description", content: "Recent Oslo opportunities, ranked against your experience and interests." },
  ] }),
  component: RadarPage,
});
const DAYS: RadarRequest["days"][] = [3, 7, 14, 30];
const LAST = ["radar", "last"] as const;

function RadarPage() {
  const profile = useProfileQuery();
  const qc = useQueryClient();
  const [days, setDays] = useState<RadarRequest["days"]>(30);
  const [englishOnly, setEnglishOnly] = useState(false);
  const last = useQuery<RadarResponse | null>({ queryKey: LAST, queryFn: () => null, staleTime: Infinity, gcTime: Infinity });
  const scan = useMutation({
    mutationFn: () => api.scanRadar({ days, english_only: englishOnly, refresh: true }),
    onSuccess: (r) => qc.setQueryData(LAST, r),
  });
  if (profile.isPending) return <LoadingState />;
  if (profile.isError) {
    if (isNotFound(profile.error)) return <EmptyState icon={<Lock className="size-6" />} title="Your story comes first." body="Add your CV so JobbRadar can look for opportunities that fit your experience." action={<Button asChild><Link to="/profile">Build your profile <ArrowRight /></Link></Button>} />;
    return <ErrorState error={profile.error} onRetry={() => profile.refetch()} />;
  }
  const data = last.data;
  return (
    <div>
      <section className="scan-hero">
        <div className="scan-hero-copy">
          <div className="eyebrow"><span className="hero-signal" /> YOUR NEXT MOVE STARTS HERE</div>
          <h1>your next<br /><em>big thing.</em></h1>
          <p>Good work starts with a good fit. Explore recent openings connected to your experience, interests and ambitions.</p>
          <button className="scan-launch" aria-label="Scan for jobs" disabled={scan.isPending} onClick={() => scan.mutate()}>
            {scan.isPending ? <Loader2 className="size-4 animate-spin" /> : <RadarIcon className="size-4" />}
            {scan.isPending ? "Scanning your horizon…" : data ? "Run a fresh scan" : "Find my opportunities"}
            {!scan.isPending && <ArrowUpRight className="size-4" />}
          </button>
        </div>
        <div className="scan-visual" aria-hidden="true"><RadarGlyph active={scan.isPending} /><span className="orbit-cross orbit-cross-one">+</span><span className="orbit-cross orbit-cross-two">+</span><div className="signal-ticket"><span>LESS SCROLLING.</span><strong>more possibility ↗</strong></div></div>
        <div className="hero-footnote" aria-hidden="true"><span>BUILT AROUND YOU</span><span>PROFILE → OPPORTUNITY → NEXT CHAPTER</span></div>
      </section>

      <details open className="scan-filters" aria-label="Search preferences">
        <summary><SlidersHorizontal className="size-4" /><span>Fine-tune your search</span><ChevronDown className="ml-auto size-4" /></summary>
        <div className="scan-filter-controls">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs text-muted-foreground">Published within</span>
          <div className="flex rounded-lg bg-muted p-1" role="group" aria-label="Publication window">
            {DAYS.map((d) => <button key={d} disabled={scan.isPending} aria-pressed={d === days} onClick={() => setDays(d)} className={cn("rounded-md px-3 py-1.5 text-xs font-semibold transition-colors", d === days ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground")}>{d}d</button>)}
          </div>
        </div>
        <label className="flex cursor-pointer items-center gap-3 border-border sm:border-l sm:pl-5">
          <Switch checked={englishOnly} disabled={scan.isPending} onCheckedChange={setEnglishOnly} />
          <span><span className="block text-xs font-semibold">English-friendly</span><span className="text-[10px] text-muted-foreground">Exclude Norwegian-required roles</span></span>
        </label>
        </div>
      </details>

      {scan.isError && <ErrorState error={scan.error} onRetry={() => scan.mutate()} />}
      {!scan.isError && scan.isPending && !data && <LoadingState label="Finding and ranking your opportunities…" />}
      {!scan.isError && !scan.isPending && !data && <div className="grid gap-4 lg:grid-cols-[1fr_260px]">
        <EmptyState icon={<Search className="size-6" />} title="There's a next chapter out there." body="Start a scan to explore recent openings, see where you fit and understand what to work on." />
        <div className="radar-panel flex flex-col justify-center"><div className="eyebrow mb-4">BUILT AROUND YOU</div><p className="text-lg font-semibold tracking-tight">More than a job title.</p><p className="mt-3 text-sm leading-relaxed text-muted-foreground">Your projects, skills and preferences shape the search.</p><Link to="/profile" className="mt-5 inline-flex items-center gap-2 text-xs font-semibold text-primary">Fine-tune your profile <ArrowRight className="size-3.5" /></Link></div>
      </div>}
      {!scan.isError && data && <Results data={data} dim={scan.isPending} />}
    </div>
  );
}

function Results({ data, dim }: { data: RadarResponse; dim: boolean }) {
  const [search, setSearch] = useState("");
  const results = data.results.filter((r) => [r.job.title, r.job.company, r.job.location].join(" ").toLowerCase().includes(search.toLowerCase().trim()));
  return (
    <div className={cn("transition-opacity", dim && "pointer-events-none opacity-50")} aria-busy={dim}>
      <div className="result-stats">
        <div className="result-stat"><div className="stat-value">{data.scanned_count.toLocaleString()}</div><div className="stat-label">Openings considered</div></div>
        <div className="result-stat"><div className="stat-value text-primary">{data.results.length.toString().padStart(2, "0")}</div><div className="stat-label">Ranked opportunities</div></div>
        <div className="result-stat"><div className="stat-value">{data.days_used}<span className="ml-1 text-sm font-normal tracking-normal text-muted-foreground">days</span></div><div className="stat-label">Publication window</div></div>
      </div>
      <ScanFunnel funnel={data.funnel} resultCount={data.results.length} />
      {data.widened && <div className="mb-6 flex items-start gap-3 rounded-xl border border-info-foreground/20 bg-info-soft p-4 text-xs leading-relaxed text-info-foreground"><Info className="mt-0.5 size-4 shrink-0" /><span>We found few recent matches, so this scan covers <strong>{data.days_used} days</strong> instead of {data.days_requested}.</span></div>}
      <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div><div className="eyebrow mb-2">YOUR OPPORTUNITY SHORTLIST</div><h2 className="text-2xl font-semibold tracking-tight">A direction worth exploring.</h2><p className="mt-1 text-xs text-muted-foreground">{data.candidates_count} postings ranked · Updated {formatDate(data.generated_at)} · Scores describe fit, not hiring probability.</p>{search && <p role="status" className="mt-2 text-xs font-medium text-primary">Showing {results.length} of {data.results.length} opportunities</p>}</div>
        {data.results.length > 0 && <div className="relative w-full sm:w-56"><Search className="pointer-events-none absolute left-3 top-3 size-3.5 text-muted-foreground" /><Input aria-label="Filter these results" placeholder="Filter this shortlist…" className="bg-card pl-9 text-xs" value={search} onChange={(e) => setSearch(e.target.value)} /></div>}
      </div>
      {!results.length ? <EmptyState icon={<RadarIcon className="size-6" />} title={search ? "Nothing in this shortlist matches." : "No matching openings this time."} body={search ? "Try another title, company or location." : "Try a longer time window, adjust your preferences or turn off English-friendly."} action={search ? <Button variant="outline" onClick={() => setSearch("")}>Clear filter</Button> : undefined} /> : <div className="grid gap-4">{results.map((r, index) => <JobCard key={r.job.id} r={r} index={index} />)}</div>}
    </div>
  );
}

function JobCard({ r, index }: { r: RadarResult; index: number }) {
  const { job, match } = r;
  return (
    <Link to="/jobs/$id" params={{ id: String(job.id) }} className="job-result-card group">
      <div className="flex items-start gap-4">
        <CompanyMark name={job.company} className="hidden sm:grid" />
        <div className="min-w-0 flex-1">
          <div className="mb-1.5 flex items-center gap-2 text-[11px] text-muted-foreground"><span className="font-semibold text-foreground/70">{job.company || "Company not listed"}</span><span className="opacity-40">/</span><span className="capitalize">{job.source === "fixture" ? "Demo posting" : job.source}</span></div>
          <h3 className="text-lg font-semibold leading-snug tracking-tight transition-colors group-hover:text-primary">{job.title}</h3>
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">{job.location && <span className="inline-flex items-center gap-1"><MapPin className="size-3" />{job.location}</span>}<PostedDate job={job} /></div>
        </div>
        <div className="flex shrink-0 flex-col items-center gap-1"><ScoreRing score={match.score} size={52} /><span className="text-[8px] uppercase tracking-widest text-muted-foreground">profile fit</span></div>
      </div>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3"><LanguageBadges job={job} /><VerdictBadge verdict={match.verdict} /></div>
      <div className="fit-columns">
        <Points icon={<Plus className="size-3.5" />} title="Your advantage" items={match.reasons} tone="text-primary" />
        <Points icon={<Minus className="size-3.5" />} title="Room to grow" items={match.gaps} tone="text-warning-foreground" />
        <Points icon={<CircleHelp className="size-3.5" />} title="Worth clarifying" items={match.to_clarify} tone="text-info-foreground" />
      </div>
      <div className="mt-5 flex items-center justify-between"><span className="font-mono text-[9px] tracking-widest text-muted-foreground">OPPORTUNITY {(index + 1).toString().padStart(2, "0")}</span><span className="flex items-center gap-2 text-xs font-semibold text-primary">Explore role <span className="card-arrow"><ArrowUpRight className="size-4" /></span></span></div>
    </Link>
  );
}
