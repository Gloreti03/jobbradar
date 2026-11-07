import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Briefcase, MessagesSquare } from "lucide-react";
import { api, qk } from "@/api";
import { APPLICATION_STATUSES, type ApplicationOut, type ApplicationStatus } from "@/types";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { EmptyState, ErrorState, LoadingState, PageHeader, formatDate, statusLabel } from "@/components/radar/shared";

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
      <PageHeader title="Applications" subtitle="Every application you've drafted or sent. Change status as things progress." />
      {q.isPending && <LoadingState />}
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {q.isSuccess && q.data.length === 0 && (
        <EmptyState icon={<Briefcase className="size-6" />} title="No applications yet" body="Open a job from Radar and create an application." action={<Button asChild><Link to="/radar">Go to Radar</Link></Button>} />
      )}
      {q.isSuccess && q.data.length > 0 && (
        <div className="grid grid-cols-5 gap-4">
          {APPLICATION_STATUSES.map((s) => {
            const items = q.data.filter((a) => a.status === s);
            return (
              <div key={s} className="min-w-0 rounded-xl bg-muted/60 p-3">
                <div className="mb-3 flex items-center justify-between px-1">
                  <span className="text-sm font-semibold">{statusLabel[s]}</span>
                  <span className="rounded-full bg-card px-2 text-xs font-mono text-muted-foreground">{items.length}</span>
                </div>
                <div className="space-y-3">
                  {items.map((a) => (
                    <AppCard key={a.id} a={a} onStatus={(status) => setStatus.mutate({ id: a.id, status })} />
                  ))}
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
    <div className="rounded-lg border bg-card p-3 shadow-card">
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
