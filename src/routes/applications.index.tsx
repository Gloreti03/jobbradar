import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowUpRight, Briefcase, MessagesSquare, Plus } from "lucide-react";
import { api, qk } from "@/api";
import { APPLICATION_STATUSES, type ApplicationOut, type ApplicationStatus } from "@/types";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { CompanyMark, EmptyState, ErrorState, LoadingState, PageHeader, formatDate, statusLabel } from "@/components/radar/shared";

export const Route = createFileRoute("/applications/")({
  head: () => ({
    meta: [
      { title: "Applications — RADAR" },
      { name: "description", content: "Track your job applications from draft to offer." },
      { property: "og:title", content: "Applications — RADAR" },
      { property: "og:description", content: "Track your job applications from draft to offer." },
    ],
  }),
  component: ApplicationsPage,
});

function ApplicationsPage() {
  const q = useQuery({ queryKey: qk.applications, queryFn: api.listApplications });
  const qc = useQueryClient();
  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: ApplicationStatus }) => api.patchApplication(id, { status }),
    onSuccess: (a) => {
      qc.invalidateQueries({ queryKey: qk.applications });
      qc.setQueryData(qk.application(a.id), a);
      qc.invalidateQueries({ queryKey: qk.job(a.job_id) });
      toast.success(`Moved to ${statusLabel[a.status]}`);
    },
    onError: (e) => toast.error(`Couldn't update status: ${e.message}`),
  });

  return (
    <div>
      <PageHeader title="Keep your next move moving." subtitle="From a first draft to a new beginning. Your applications, documents and conversations, all in one place." actions={<Button asChild variant="outline"><Link to="/radar"><Plus /> Find opportunities</Link></Button>} />
      {q.isSuccess && q.data.length > 0 && <div className="result-stats"><div className="result-stat"><div className="stat-value">{q.data.length.toString().padStart(2, "0")}</div><div className="stat-label">Total applications</div></div><div className="result-stat"><div className="stat-value text-primary">{q.data.filter((a) => !!a.applied_at).length.toString().padStart(2, "0")}</div><div className="stat-label">Confirmed submissions</div></div><div className="result-stat"><div className="stat-value">{q.data.filter((a) => a.status === "interviewing").length.toString().padStart(2, "0")}</div><div className="stat-label">In conversation</div></div></div>}
      {q.isPending && <LoadingState />}
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {q.isSuccess && q.data.length === 0 && (
        <EmptyState icon={<Briefcase className="size-6" />} title="No applications yet" body="Open a job from Radar and create an application." action={<Button asChild><Link to="/radar">Go to Radar</Link></Button>} />
      )}
      {q.isSuccess && q.data.length > 0 && (
        <div className="pipeline-board" aria-label="Application stages">
          {APPLICATION_STATUSES.map((s) => {
            const items = q.data.filter((a) => a.status === s);
            return (
              <div key={s} className="pipeline-column">
                <div className="mb-4 flex items-center justify-between px-2">
                  <span className="flex items-center gap-2 text-xs font-semibold"><span className="size-1.5 rounded-full" style={{ background: s === "offer" ? "var(--primary)" : s === "interviewing" ? "var(--info-foreground)" : s === "rejected" ? "var(--warning)" : "var(--muted-foreground)" }} />{statusLabel[s]}</span>
                  <span className="rounded-md bg-card px-2 py-0.5 text-[10px] font-mono text-muted-foreground">{items.length}</span>
                </div>
                <div className="space-y-3">
                  {items.map((a) => (
                    <AppCard key={a.id} a={a} onStatus={(status) => setStatus.mutate({ id: a.id, status })} />
                  ))}
                  {items.length === 0 && <div className="rounded-lg border border-dashed px-3 py-8 text-center text-[11px] text-muted-foreground">Nothing here yet.</div>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function AppCard({ a, onStatus }: { a: ApplicationOut; onStatus: (s: ApplicationStatus) => void }) {
  const submitted = a.status !== "draft";
  return (
    <div className="pipeline-card">
      <div className="mb-4 flex items-center justify-between"><CompanyMark name={a.job.company} className="!size-8 !rounded-lg !text-xs" /><ArrowUpRight className="size-3.5 text-muted-foreground" /></div>
      <Link to="/applications/$id" params={{ id: String(a.id) }} className="block hover:text-primary">
        <div className="text-sm font-semibold leading-snug">{a.job.title}</div>
        <div className="mt-0.5 text-xs text-muted-foreground">{a.job.company ?? "Unknown company"}</div>
        <div className="mt-1 text-[11px] text-muted-foreground">
          {a.applied_at ? `Applied ${formatDate(a.applied_at)}` : `Created ${formatDate(a.created_at)}`}
        </div>
      </Link>
      <Select value={a.status} onValueChange={(v) => onStatus(v as ApplicationStatus)}>
        <SelectTrigger className="mt-3 h-8 text-xs" aria-label="Change status">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {APPLICATION_STATUSES.map((s) => (
            <SelectItem key={s} value={s}>{statusLabel[s]}</SelectItem>
          ))}
        </SelectContent>
      </Select>
      {submitted && (
        <Button asChild variant="ghost" size="sm" className="mt-2 w-full text-xs">
          <Link to="/interview/$applicationId" params={{ applicationId: String(a.id) }}>
            <MessagesSquare /> Practice interview
          </Link>
        </Button>
      )}
    </div>
  );
}
