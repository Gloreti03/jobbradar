import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { ArrowRight, FileUp, HelpCircle, Loader2, Plus, Save, Sparkles, Trash2, UploadCloud, X } from "lucide-react";
import { api, isNotFound, qk } from "@/api";
import type { Profile, ProfileOut } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { useProfileQuery } from "@/components/radar/AppShell";
import { ErrorState, LoadingState, PageHeader, Panel, formatDate } from "@/components/radar/shared";
import { DISCOVERY_QUESTIONS, mergeAttachments, splitProfileMaterial } from "@/lib/profile-material";

export const Route = createFileRoute("/profile")({
  head: () => ({
    meta: [
      { title: "Profile — RADAR" },
      { name: "description", content: "Upload your CV and set your job preferences." },
      { property: "og:title", content: "Profile — RADAR" },
      { property: "og:description", content: "Upload your CV and set your job preferences." },
    ],
  }),
  component: ProfilePage,
});

function ProfilePage() {
  const q = useProfileQuery();
  if (q.isPending) return <LoadingState label="Loading your profile…" />;
  if (q.isError && isNotFound(q.error)) return <UploadScreen firstUse />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  return <ProfileEditor data={q.data} />;
}

function UploadScreen({ firstUse, onDone }: { firstUse?: boolean; onDone?: () => void }) {
  const qc = useQueryClient();
  const [cv, setCv] = useState<File | null>(null);
  const [extra, setExtra] = useState<File[]>([]);
  const [text, setText] = useState("");
  const m = useMutation({
    mutationFn: () => api.uploadProfile(cv!, extra, text),
    onSuccess: (p) => {
      qc.setQueryData(qk.profile, p);
      toast.success("Profile created from your CV");
      onDone?.();
    },
    onError: (e) => toast.error(e.message),
  });

  return (
    <div className={firstUse ? "mx-auto max-w-2xl pt-6" : ""}>
      {firstUse && (
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex size-14 items-center justify-center rounded-2xl bg-primary-soft text-primary">
            <FileUp className="size-7" />
          </div>
          <h1 className="text-3xl font-semibold tracking-tight">Upload your CV to get started</h1>
          <p className="mx-auto mt-2 max-w-md text-muted-foreground">
            RADAR reads your CV to build a profile, then scans Oslo job postings for roles that fit you. Radar unlocks once your profile is ready.
          </p>
        </div>
      )}
      <Panel>
        <div className="space-y-6">
          <label className="flex cursor-pointer flex-col items-center rounded-xl border-2 border-dashed border-primary/30 bg-primary-soft/40 px-6 py-10 text-center transition-colors hover:border-primary/60">
            <UploadCloud className="mb-3 size-8 text-primary" />
            <span className="font-medium">{cv ? cv.name : "Choose your CV (PDF)"}</span>
            <span className="mt-1 text-sm text-muted-foreground">{cv ? "Click to replace" : "Required"}</span>
            <input type="file" accept=".pdf,application/pdf" className="hidden" onChange={(e) => setCv(e.target.files?.[0] ?? null)} />
          </label>

          <div>
            <Label>Additional documents (optional)</Label>
            <p className="mb-2 text-xs text-muted-foreground">Add certificates, transcripts or projects together or one at a time. PDF, TXT or MD; up to 10 MB per file.</p>
            <Input aria-label="Add additional documents" type="file" multiple accept=".pdf,.txt,.md" disabled={m.isPending} onChange={(e) => {
              const incoming = Array.from(e.target.files ?? []);
              const valid = incoming.filter((f) => {
                if (!/\.(pdf|txt|md)$/i.test(f.name) || f.size > 10 * 1024 * 1024) {
                  toast.error(`${f.name}: choose a PDF, TXT or MD file up to 10 MB.`);
                  return false;
                }
                return true;
              });
              setExtra((previous) => mergeAttachments(previous, valid));
              e.target.value = "";
            }} />
            {extra.length > 0 && <ul className="mt-2 space-y-1">
              {extra.map((file, i) => <li key={`${file.name}-${file.lastModified}-${file.size}`} className="flex items-center justify-between gap-2 rounded-md bg-muted px-3 py-1 text-sm">
                <span className="min-w-0 truncate">{file.name}</span>
                <Button variant="ghost" size="icon" disabled={m.isPending} aria-label={`Remove ${file.name}`} onClick={() => setExtra((previous) => previous.filter((_, j) => j !== i))}><X /></Button>
              </li>)}
            </ul>}
          </div>

          <div>
            <Label htmlFor="extra">Anything else we should know? (optional)</Label>
            <Textarea id="extra" className="mt-2" rows={3} placeholder="E.g. industries you prefer, visa situation, availability…" value={text} onChange={(e) => setText(e.target.value)} />
          </div>

          <Button size="lg" className="w-full" disabled={!cv || m.isPending} onClick={() => m.mutate()}>
            {m.isPending ? <><Loader2 className="animate-spin" /> Reading your CV…</> : <><Sparkles /> Build my profile</>}
          </Button>
        </div>
      </Panel>
    </div>
  );
}

function ListEditor({ label, items, onChange, placeholder }: { label: string; items: string[]; onChange: (v: string[]) => void; placeholder?: string }) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const v = draft.trim();
    if (v && !items.includes(v)) onChange([...items, v]);
    setDraft("");
  };
  return (
    <div>
      <Label>{label}</Label>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {items.map((it) => (
          <span key={it} className="inline-flex items-center gap-1 rounded-md bg-secondary px-2 py-1 text-sm">
            {it}
            <button aria-label={`Remove ${it}`} onClick={() => onChange(items.filter((x) => x !== it))} className="text-muted-foreground hover:text-destructive">
              <X className="size-3" />
            </button>
          </span>
        ))}
      </div>
      <div className="mt-2 flex gap-2">
        <Input value={draft} placeholder={placeholder ?? "Add…"} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), add())} />
        <Button variant="outline" size="icon" onClick={add} aria-label={`Add ${label}`}>
          <Plus />
        </Button>
      </div>
    </div>
  );
}

const WORK_MODES = ["onsite", "hybrid", "remote"];
const SENIORITY = ["intern", "junior", "mid", "senior"];

function ProfileEditor({ data }: { data: ProfileOut }) {
  const qc = useQueryClient();
  const [p, setP] = useState<Profile>(data.profile);
  const material = splitProfileMaterial(data.extra_text);
  const [extraText, setExtraText] = useState(material.notes);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [discovery, setDiscovery] = useState<Record<number, string>>({});
  const [reupload, setReupload] = useState(false);
  useEffect(() => {
    setP(data.profile);
    setExtraText(splitProfileMaterial(data.extra_text).notes);
  }, [data]);

  const set = <K extends keyof Profile>(k: K, v: Profile[K]) => setP((x) => ({ ...x, [k]: v }));
  const setPref = <K extends keyof Profile["preferences"]>(k: K, v: Profile["preferences"][K]) => setP((x) => ({ ...x, preferences: { ...x.preferences, [k]: v } }));
  const dirty = JSON.stringify(p) !== JSON.stringify(data.profile) || extraText !== material.notes || Object.values(answers).some(Boolean) || Object.values(discovery).some(Boolean);

  const save = useMutation({
    mutationFn: () => {
      const answered = p.missing_info
        .map((q, i) => (answers[i]?.trim() ? `Q: ${q}\nA: ${answers[i].trim()}` : null))
        .filter(Boolean) as string[];
      const missing = p.missing_info.filter((_, i) => !answers[i]?.trim());
      const discoveryAnswers = DISCOVERY_QUESTIONS.map((q, i) => discovery[i]?.trim() ? `Q: ${q}\nA: ${discovery[i].trim()}` : "");
      const text = [extraText, ...answered, ...discoveryAnswers, material.documents].filter(Boolean).join("\n\n");
      return api.updateProfile({ profile: { ...p, missing_info: missing }, extra_text: text });
    },
    onSuccess: (d) => {
      qc.setQueryData(qk.profile, d);
      setAnswers({});
      setDiscovery({});
      toast.success("Profile saved");
    },
    onError: (e) => toast.error(`Couldn't save: ${e.message}`),
  });

  return (
    <div>
      <PageHeader
        title={p.name || "Your profile"}
        subtitle={<>Built from your CV · last updated {formatDate(data.updated_at)}. Review it — Radar matches jobs against exactly this.</>}
        actions={
          <>
            <Button variant="outline" onClick={() => setReupload((v) => !v)}>
              <FileUp /> {reupload ? "Cancel" : "Upload new CV"}
            </Button>
            <Button disabled={!dirty || save.isPending} onClick={() => save.mutate()}>
              {save.isPending ? <Loader2 className="animate-spin" /> : <Save />} Save changes
            </Button>
          </>
        }
      />

      {reupload && (
        <div className="mb-8">
          <UploadScreen onDone={() => setReupload(false)} />
        </div>
      )}

      {p.missing_info.length > 0 && (
        <Panel className="mb-6 border-warning/40 bg-warning-soft/50" title="A few questions to improve your matches" icon={<HelpCircle className="size-4 text-warning-foreground" />}>
          <div className="space-y-4">
            {p.missing_info.map((q, i) => (
              <div key={q}>
                <Label className="text-foreground">{q}</Label>
                <Input className="mt-1.5 bg-card" value={answers[i] ?? ""} onChange={(e) => setAnswers((a) => ({ ...a, [i]: e.target.value }))} placeholder="Your answer" />
              </div>
            ))}
            <p className="text-xs text-muted-foreground">Answers are saved with your additional information when you click Save changes.</p>
          </div>
        </Panel>
      )}

      <Panel className="mb-6" title="Explore directions you might not have considered" icon={<Sparkles className="size-4 text-primary" />}>
        <p className="mb-4 text-sm text-muted-foreground">Tell us what you enjoy doing, even if you do not know the job title. Your answers are saved as additional context; they do not add unverified skills to your CV.</p>
        <div className="space-y-4">
          {DISCOVERY_QUESTIONS.map((question, i) => <div key={question}>
            <Label htmlFor={`discovery-${i}`}>{question}</Label>
            <Textarea id={`discovery-${i}`} className="mt-1.5" rows={2} placeholder="A concrete example is helpful…" value={discovery[i] ?? ""} onChange={(e) => setDiscovery((previous) => ({ ...previous, [i]: e.target.value }))} />
          </div>)}
        </div>
      </Panel>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Panel title="Summary">
            <div className="space-y-4">
              <div>
                <Label>Headline</Label>
                <Input className="mt-1.5" value={p.headline} onChange={(e) => set("headline", e.target.value)} />
              </div>
              <div>
                <Label>Summary</Label>
                <Textarea className="mt-1.5" rows={4} value={p.summary} onChange={(e) => set("summary", e.target.value)} />
              </div>
            </div>
          </Panel>

          <Panel title="Skills & tools">
            <div className="grid gap-6 md:grid-cols-2">
              <ListEditor label="Skills" items={p.skills} onChange={(v) => set("skills", v)} />
              <ListEditor label="Tools" items={p.tools} onChange={(v) => set("tools", v)} />
            </div>
          </Panel>

          <Panel title="Experience">
            <div className="space-y-5">
              {p.experiences.map((x, i) => (
                <div key={i} className="rounded-lg border p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="font-semibold">{x.role}</div>
                      <div className="text-sm text-muted-foreground">
                        {x.company}
                        {x.location && ` · ${x.location}`} · {x.start_date ?? "?"} – {x.end_date ?? "present"}
                      </div>
                    </div>
                    <Button variant="ghost" size="icon" aria-label="Remove experience" onClick={() => set("experiences", p.experiences.filter((_, j) => j !== i))}>
                      <Trash2 />
                    </Button>
                  </div>
                  <Textarea
                    className="mt-3 text-sm"
                    rows={Math.max(2, x.bullets.length)}
                    value={x.bullets.join("\n")}
                    onChange={(e) => set("experiences", p.experiences.map((y, j) => (j === i ? { ...y, bullets: e.target.value.split("\n") } : y)))}
                  />
                  <p className="mt-1 text-xs text-muted-foreground">One bullet per line.</p>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Education & projects">
            <div className="space-y-3">
              {p.education.map((e, i) => (
                <div key={i} className="text-sm">
                  <span className="font-semibold">{e.degree}</span> · {e.institution}{" "}
                  <span className="text-muted-foreground">({e.start_date ?? "?"} – {e.end_date ?? "present"})</span>
                </div>
              ))}
              <div className="my-4 border-t" />
              {p.projects.map((pr, i) => (
                <div key={i} className="text-sm">
                  <span className="font-semibold">{pr.name}</span> — <span className="text-muted-foreground">{pr.description}</span>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        <div className="space-y-6">
          <Panel title="Preferences">
            <div className="space-y-5">
              <ListEditor label="Target roles" items={p.preferences.roles} onChange={(v) => setPref("roles", v)} />
              <ListEditor label="Cities" items={p.preferences.cities} onChange={(v) => setPref("cities", v)} />
              <div>
                <Label>Seniority</Label>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {SENIORITY.map((s) => (
                    <Button key={s} size="sm" variant={p.preferences.seniority === s ? "default" : "outline"} onClick={() => setPref("seniority", s)} className="capitalize">
                      {s}
                    </Button>
                  ))}
                </div>
              </div>
              <div>
                <Label>Work modes</Label>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {WORK_MODES.map((m) => {
                    const on = p.preferences.work_modes.includes(m);
                    return (
                      <Button key={m} size="sm" variant={on ? "default" : "outline"} className="capitalize" onClick={() => setPref("work_modes", on ? p.preferences.work_modes.filter((x) => x !== m) : [...p.preferences.work_modes, m])}>
                        {m}
                      </Button>
                    );
                  })}
                </div>
              </div>
            </div>
          </Panel>

          <Panel title="Languages">
            <ul className="space-y-1.5 text-sm">
              {p.languages.map((l) => (
                <li key={l.language} className="flex justify-between">
                  <span>{l.language}</span>
                  <span className="font-mono text-muted-foreground">{l.level}</span>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title="Additional information">
            <Textarea rows={4} value={extraText} onChange={(e) => setExtraText(e.target.value)} placeholder="Extra context for matching and applications" />
            {material.documents && <details className="mt-3">
              <summary className="cursor-pointer text-sm font-medium">Imported document text</summary>
              <p className="my-2 text-xs text-muted-foreground">Check that this text is readable before relying on it. If it is garbled, paste the correct information into your notes and ask for the document to be reprocessed.</p>
              <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words rounded-md bg-muted p-2 text-xs">{material.documents}</pre>
            </details>}
          </Panel>

          <Panel title="Search terms">
            <div className="flex flex-wrap gap-1">
              {p.search_terms.map((t) => (
                <span key={t} className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">{t}</span>
              ))}
            </div>
          </Panel>

          <Button asChild size="lg" className="w-full">
            <Link to="/radar">
              Scan for jobs <ArrowRight />
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
