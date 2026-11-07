import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, ArrowLeft, Check, CheckCircle2, ExternalLink, Loader2, MessagesSquare, PenLine, Printer, Save } from "lucide-react";
import { api, qk } from "@/api";
import type { ApplicationOut, TailoredCV } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ErrorState, LoadingState, Panel, StatusBadge, formatDate } from "@/components/radar/shared";
import { CVDocument, CoverDocument } from "@/components/radar/Documents";

export const Route = createFileRoute("/applications/$id")({
  head: () => ({
    meta: [
      { title: "Application — RADAR" },
      { name: "description", content: "Edit your tailored CV and cover letter, then apply." },
      { property: "og:title", content: "Application — RADAR" },
      { property: "og:description", content: "Edit your tailored CV and cover letter, then apply." },
    ],
  }),
  component: EditorPage,
});

function EditorPage() {
  const id = Number(Route.useParams().id);
  const q = useQuery({ queryKey: qk.application(id), queryFn: () => api.getApplication(id) });
  if (q.isPending) return <LoadingState label="Loading application…" />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  return <Editor app={q.data} />;
}

function Editor({ app }: { app: ApplicationOut }) {
  const qc = useQueryClient();
  const [cv, setCv] = useState<TailoredCV>(app.cv);
  const [letter, setLetter] = useState(app.cover_letter);
  useEffect(() => {
    setCv(app.cv);
    setLetter(app.cover_letter);
  }, [app.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const dirty = JSON.stringify(cv) !== JSON.stringify(app.cv) || letter !== app.cover_letter;
  const sync = (a: ApplicationOut) => {
    qc.setQueryData(qk.application(a.id), a);
    qc.invalidateQueries({ queryKey: qk.applications });
    qc.invalidateQueries({ queryKey: qk.job(a.job_id) });
  };

  const saveM = useMutation({
    mutationFn: () => api.patchApplication(app.id, { cv, cover_letter: letter }),
    onSuccess: (a) => {
      sync(a);
      toast.success("Saved");
    },
    onError: (e) => toast.error(`Couldn't save: ${e.message}`),
  });

  const appliedM = useMutation({
    mutationFn: async () => {
      if (dirty) await api.patchApplication(app.id, { cv, cover_letter: letter }); // save pending edits first
      return api.markApplied(app.id);
    },
    onSuccess: (a) => {
      sync(a);
      toast.success("Marked as applied — good luck!");
    },
    onError: (e) => toast.error(`Couldn't mark as applied: ${e.message}`),
  });

  const openPrint = async (kind: "cv" | "cover") => {
    if (dirty) {
      try {
        await saveM.mutateAsync();
      } catch {
        return;
      }
    }
    window.open(`/print/${kind}/${app.id}`, "_blank");
  };

  const setC = <K extends keyof TailoredCV>(k: K, v: TailoredCV[K]) => setCv((x) => ({ ...x, [k]: v }));
  const applyUrl = app.job.apply_url ?? app.job.url;
  const isDraft = app.status === "draft";

  return (
    <div>
      <Link to="/applications" className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> All applications
      </Link>

      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-semibold tracking-tight">{app.job.title}</h1>
            <StatusBadge status={app.status} />
          </div>
          <p className="mt-1 text-muted-foreground">
            <Link to="/jobs/$id" params={{ id: String(app.job_id) }} className="hover:text-foreground hover:underline">
              {app.job.company ?? "Unknown company"}
            </Link>
            {" · "}Created {formatDate(app.created_at)}
            {app.applied_at && ` · Applied ${formatDate(app.applied_at)}`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => openPrint("cv")}><Printer /> Print CV</Button>
          <Button variant="outline" onClick={() => openPrint("cover")}><Printer /> Print letter</Button>
          <Button variant="secondary" disabled={!dirty || saveM.isPending} onClick={() => saveM.mutate()}>
            {saveM.isPending ? <Loader2 className="animate-spin" /> : dirty ? <Save /> : <Check />} {dirty ? "Save" : "Saved"}
          </Button>
        </div>
      </div>

      {/* Next action */}
      <div className="mb-8 rounded-2xl border border-primary/30 bg-primary-soft/60 p-5">
        {isDraft ? (
          <div className="flex flex-wrap items-center gap-4">
            <div className="mr-auto">
              <div className="font-semibold">Ready to apply?</div>
              <p className="text-sm text-muted-foreground">
                1. Open the company site and submit there. 2. Come back and confirm with "I applied" — this saves a snapshot of what you sent.
              </p>
            </div>
            <Button asChild variant="outline" className="bg-card">
              <a href={applyUrl} target="_blank" rel="noreferrer"><ExternalLink /> Apply on site</a>
            </Button>
            <Button disabled={appliedM.isPending} onClick={() => appliedM.mutate()}>
              {appliedM.isPending ? <Loader2 className="animate-spin" /> : <CheckCircle2 />} I applied
            </Button>
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-4">
            <CheckCircle2 className="size-6 text-primary" />
            <div className="mr-auto">
              <div className="font-semibold">Application submitted{app.applied_at && ` on ${formatDate(app.applied_at)}`}</div>
              <p className="text-sm text-muted-foreground">Prepare for the conversation with a practice interview based on what you sent.</p>
            </div>
            <Button asChild>
              <Link to="/interview/$applicationId" params={{ applicationId: String(app.id) }}><MessagesSquare /> Practice interview</Link>
            </Button>
          </div>
        )}
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_320px]">
        <Tabs defaultValue="cv">
          <TabsList>
            <TabsTrigger value="cv">CV</TabsTrigger>
            <TabsTrigger value="cover">Cover letter</TabsTrigger>
            <TabsTrigger value="preview">Preview</TabsTrigger>
          </TabsList>

          <TabsContent value="cv" className="mt-4 space-y-6">
            <Panel title="Header" icon={<PenLine className="size-4" />}>
              <div className="grid gap-4 md:grid-cols-2">
                <div><Label>Name</Label><Input className="mt-1.5" value={cv.name} onChange={(e) => setC("name", e.target.value)} /></div>
                <div><Label>Headline</Label><Input className="mt-1.5" value={cv.headline} onChange={(e) => setC("headline", e.target.value)} /></div>
              </div>
              <div className="mt-4"><Label>Summary</Label><Textarea className="mt-1.5" rows={4} value={cv.summary} onChange={(e) => setC("summary", e.target.value)} /></div>
              <div className="mt-4">
                <Label>Skills (comma separated)</Label>
                <Input className="mt-1.5" value={cv.skills.join(", ")} onChange={(e) => setC("skills", e.target.value.split(",").map((s) => s.trimStart()))} />
              </div>
            </Panel>
            <Panel title="Experience">
              <div className="space-y-5">
                {cv.experiences.map((x, i) => (
                  <div key={i}>
                    <div className="mb-1.5 text-sm font-semibold">{x.role} · <span className="font-normal text-muted-foreground">{x.company}</span></div>
                    <Textarea
                      rows={Math.max(3, x.bullets.length + 1)}
                      value={x.bullets.join("\n")}
                      onChange={(e) => setC("experiences", cv.experiences.map((y, j) => (j === i ? { ...y, bullets: e.target.value.split("\n") } : y)))}
                    />
                  </div>
                ))}
                <p className="text-xs text-muted-foreground">One bullet per line. Only include things you actually did.</p>
              </div>
            </Panel>
          </TabsContent>

          <TabsContent value="cover" className="mt-4">
            <Panel>
              <Textarea rows={22} className="font-[inherit] leading-relaxed" value={letter} onChange={(e) => setLetter(e.target.value)} />
            </Panel>
          </TabsContent>

          <TabsContent value="preview" className="mt-4 space-y-6">
            <div className="rounded-xl border bg-card p-10 shadow-card"><CVDocument cv={cv} /></div>
            <div className="rounded-xl border bg-card p-10 shadow-card"><CoverDocument cv={cv} letter={letter} /></div>
          </TabsContent>
        </Tabs>

        <aside className="space-y-6">
          {app.notes.missing_requirements.length > 0 && (
            <Panel title="Not claimed in your CV" icon={<AlertTriangle className="size-4 text-warning-foreground" />} className="border-warning/40">
              <ul className="space-y-1.5 text-sm">{app.notes.missing_requirements.map((x) => <li key={x}>{x}</li>)}</ul>
              <p className="mt-3 text-xs text-muted-foreground">Requirements you don't meet yet. Be ready to address them honestly.</p>
            </Panel>
          )}
          <Panel title="Keywords covered">
            <div className="flex flex-wrap gap-1.5">
              {app.notes.keywords_covered.map((k) => <span key={k} className="rounded-md bg-primary-soft px-2 py-0.5 text-xs text-accent-foreground">{k}</span>)}
            </div>
          </Panel>
          <Panel title="What was changed">
            <ul className="list-disc space-y-1.5 pl-4 text-sm text-foreground/80">{app.notes.changes.map((c) => <li key={c}>{c}</li>)}</ul>
          </Panel>
        </aside>
      </div>
    </div>
  );
}
