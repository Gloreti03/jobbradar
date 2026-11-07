import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, CircleHelp, ExternalLink, FileText, Loader2, MapPin, Minus, Plus, Sparkles } from "lucide-react";
import { api, qk, USE_MOCKS } from "@/api";
import { Button } from "@/components/ui/button";
import { useProfileQuery } from "@/components/radar/AppShell";
import { CompanyMark, ErrorState, LanguageBadges, LoadingState, Panel, Points, PostedDate, ScoreRing, StatusBadge, VerdictBadge, formatDate } from "@/components/radar/shared";

export const Route = createFileRoute("/jobs/$id")({
  head: () => ({
    meta: [
      { title: "Job details — JobbRadar" },
      { name: "description", content: "Job posting, match details and application drafting." },
      { property: "og:title", content: "Job details — JobbRadar" },
      { property: "og:description", content: "Job posting, match details and application drafting." },
    ],
  }),
  component: JobPage,
});

function JobPage() {
  const id = Number(Route.useParams().id);
  const q = useQuery({ queryKey: qk.job(id), queryFn: () => api.getJob(id) });
  const profile = useProfileQuery();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const create = useMutation({
    mutationFn: () => api.createApplication(id),
    onSuccess: (a) => {
      qc.setQueryData(qk.application(a.id), a);
      qc.invalidateQueries({ queryKey: qk.job(id) });
      qc.invalidateQueries({ queryKey: qk.applications });
      toast.success("Application draft created");
      navigate({ to: "/applications/$id", params: { id: String(a.id) } });
    },
    onError: (e) => toast.error(`Couldn't create application: ${e.message}`),
  });

  if (q.isPending) return <LoadingState label="Loading job…" />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const { job, match, application } = q.data;
  const demoJobOnLiveApi = !USE_MOCKS && job.source === "fixture";

  return (
    <div>
      <Link to="/radar" className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Back to JobbRadar
      </Link>

      <div className="mb-8 rounded-2xl border bg-card p-6 sm:p-8">
        <div className="mb-5 flex items-center gap-3"><CompanyMark name={job.company} /><span className="eyebrow">A POTENTIAL NEXT CHAPTER</span></div>
        <h1 className="max-w-4xl text-3xl font-semibold leading-tight tracking-[-1.3px] sm:text-4xl">{job.title}</h1>
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-muted-foreground">
          <span className="font-medium text-foreground">{job.company ?? "Unknown company"}</span>
          {job.location && <span className="inline-flex items-center gap-1"><MapPin className="size-4" />{job.location}</span>}
          <PostedDate job={job} />
          {job.expires_at && <span>Deadline {formatDate(job.expires_at)}</span>}
        </div>
        <div className="mt-3"><LanguageBadges job={job} /></div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Panel title="Job description">
            {job.description ? (
              <div className="whitespace-pre-line leading-relaxed text-foreground/85">{job.description}</div>
            ) : (
              <p className="text-muted-foreground">No description available. Open the original posting for details.</p>
            )}
            <a href={job.url} target="_blank" rel="noreferrer" className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline">
              View original posting <ExternalLink className="size-3.5" />
            </a>
          </Panel>
        </div>

        <div className="space-y-6 lg:sticky lg:top-6 lg:self-start">
          <Panel title="Next step" className="border-primary/30">
            {application ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span>You have an application for this job</span>
                  <StatusBadge status={application.status} />
                </div>
                <Button asChild size="lg" className="w-full">
                  <Link to="/applications/$id" params={{ id: String(application.id) }}>
                    <FileText /> Open application
                  </Link>
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-sm text-muted-foreground">Create a tailored CV and cover letter for this job, using only facts from your profile.</p>
                {demoJobOnLiveApi && <p role="alert" className="rounded-md bg-warning-soft p-3 text-sm text-warning-foreground">This is a sample posting. Choose a verified live posting to prepare a real application.</p>}
                <Button size="lg" className="w-full" disabled={create.isPending || !profile.isSuccess || demoJobOnLiveApi} onClick={() => create.mutate()}>
                  {create.isPending ? <><Loader2 className="animate-spin" /> Drafting documents…</> : <><Sparkles /> Create application</>}
                </Button>
                {!profile.isSuccess && !profile.isPending && <p className="text-xs text-muted-foreground">Create your profile first.</p>}
              </div>
            )}
          </Panel>

          <Panel title="Match">
            {match ? (
              <div className="space-y-5">
                <div className="flex items-center gap-4">
                  <ScoreRing score={match.score} size={72} />
                  <div>
                    <VerdictBadge verdict={match.verdict} />
                    <p className="mt-1.5 text-xs text-muted-foreground">Profile fit score, not a hiring probability.</p>
                  </div>
                </div>
                <Points icon={<Plus className="size-3.5" />} title="Why it fits" items={match.reasons} tone="text-primary" />
                <Points icon={<Minus className="size-3.5" />} title="Gaps" items={match.gaps} tone="text-warning-foreground" />
                <Points icon={<CircleHelp className="size-3.5" />} title="To clarify" items={match.to_clarify} tone="text-info-foreground" />
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No match analysis yet for this job. Run a JobbRadar scan to rank it.</p>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
