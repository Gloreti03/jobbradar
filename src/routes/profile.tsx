import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  ArrowRight,
  FileUp,
  HelpCircle,
  Loader2,
  Plus,
  Save,
  Sparkles,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";
import { api, isNotFound, qk } from "@/api";
import type { Profile, ProfileOut } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { useProfileQuery } from "@/hooks/use-profile-query";
import { ErrorState, LoadingState, PageHeader, Panel } from "@/components/radar/shared";
import { formatDate } from "@/lib/format-date";
import {
  DISCOVERY_QUESTIONS,
  mergeAttachments,
  splitProfileMaterial,
} from "@/lib/profile-material";
import { saveProfileWithAnswers } from "@/lib/save-profile";
import { cacheUploadedProfile } from "@/lib/upload-profile-cache";
import { DocumentWarnings } from "@/components/radar/DocumentWarnings";

export const Route = createFileRoute("/profile")({
  head: () => ({
    meta: [
      { title: "Profile — JobbRadar" },
      { name: "description", content: "Upload your CV and set your job preferences." },
      { property: "og:title", content: "Profile — JobbRadar" },
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

function UploadScreen({
  firstUse,
  onDone,
}: {
  firstUse?: boolean;
  onDone?: (profile: ProfileOut) => void;
}) {
  const qc = useQueryClient();
  const [cv, setCv] = useState<File | null>(null);
  const [extra, setExtra] = useState<File[]>([]);
  const [text, setText] = useState("");
  const m = useMutation({
    mutationFn: () => api.uploadProfile(cv!, extra, text),
    onSuccess: async (p) => {
      await cacheUploadedProfile(qc, p);
      toast.success("Profile created from your CV");
      if (p.warnings?.length)
        toast.warning("Your documents need a review. Check the notices on your profile.");
      onDone?.(p);
    },
    onError: (e) => toast.error(e.message),
  });

  return (
    <div className={firstUse ? "mx-auto max-w-3xl pt-2" : ""}>
      {firstUse && (
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex size-14 items-center justify-center rounded-2xl bg-primary-soft text-primary">
            <FileUp className="size-7" />
          </div>
          <div className="eyebrow mb-4 justify-center">EVERY NEXT CHAPTER STARTS SOMEWHERE</div>
          <h1 className="text-4xl font-semibold tracking-[-1.8px] sm:text-5xl">
            Let's put you on the radar.
          </h1>
          <p className="mx-auto mt-4 max-w-md text-sm leading-relaxed text-muted-foreground">
            Start with your CV. Add the projects, interests and experiences that make your story
            yours. Then explore where it could take you.
          </p>
        </div>
      )}
      {firstUse && (
        <div className="mb-5 grid grid-cols-3 gap-3">
          {["Your experience", "Your interests", "Your next move"].map((label, i) => (
            <div key={label} className="rounded-xl border bg-card p-4">
              <span className="font-mono text-[10px] text-primary">0{i + 1}</span>
              <p className="mt-2 text-xs font-semibold">{label}</p>
            </div>
          ))}
        </div>
      )}
      <Panel>
        <div className="space-y-6">
          <label className="flex cursor-pointer flex-col items-center rounded-xl border border-dashed border-primary/40 bg-primary-soft/40 px-6 py-12 text-center transition-colors hover:border-primary hover:bg-primary-soft">
            <span className="mb-4 grid size-14 place-items-center rounded-2xl border border-primary/15 bg-card text-primary">
              <UploadCloud className="size-6" />
            </span>
            <span className="font-medium">{cv ? cv.name : "Choose your CV (PDF)"}</span>
            <span className="mt-1 text-sm text-muted-foreground">
              {cv ? "Click to replace" : "Required"}
            </span>
            <input
              type="file"
              accept=".pdf,application/pdf"
              className="hidden"
              onChange={(e) => setCv(e.target.files?.[0] ?? null)}
            />
          </label>

          <div>
            <Label>Additional documents (optional)</Label>
            <p className="mb-2 text-xs text-muted-foreground">
              Add certificates, transcripts or projects together or one at a time. PDF, TXT or MD;
              up to 10 MB per file.
            </p>
            <Input
              aria-label="Add additional documents"
              type="file"
              multiple
              accept=".pdf,.txt,.md"
              disabled={m.isPending}
              onChange={(e) => {
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
              }}
            />
            {extra.length > 0 && (
              <ul className="mt-2 space-y-1">
                {extra.map((file, i) => (
                  <li
                    key={`${file.name}-${file.lastModified}-${file.size}`}
                    className="flex items-center justify-between gap-2 rounded-md bg-muted px-3 py-1 text-sm"
                  >
                    <span className="min-w-0 truncate">{file.name}</span>
                    <Button
                      variant="ghost"
                      size="icon"
                      disabled={m.isPending}
                      aria-label={`Remove ${file.name}`}
                      onClick={() => setExtra((previous) => previous.filter((_, j) => j !== i))}
                    >
                      <X />
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <Label htmlFor="extra">Anything else we should know? (optional)</Label>
            <Textarea
              id="extra"
              className="mt-2"
              rows={3}
              placeholder="E.g. industries you prefer, visa situation, availability…"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </div>

          <Button
            size="lg"
            className="w-full"
            disabled={!cv || m.isPending}
            onClick={() => m.mutate()}
          >
            {m.isPending ? (
              <>
                <Loader2 className="animate-spin" /> Reading your CV…
              </>
            ) : (
              <>
                <Sparkles /> Build my profile
              </>
            )}
          </Button>
        </div>
      </Panel>
    </div>
  );
}

function ListEditor({
  label,
  items,
  onChange,
  placeholder,
}: {
  label: string;
  items: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
}) {
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
          <span
            key={it}
            className="inline-flex items-center gap-1 rounded-md bg-secondary px-2 py-1 text-sm"
          >
            {it}
            <button
              aria-label={`Remove ${it}`}
              onClick={() => onChange(items.filter((x) => x !== it))}
              className="text-muted-foreground hover:text-destructive"
            >
              <X className="size-3" />
            </button>
          </span>
        ))}
      </div>
      <div className="mt-2 flex gap-2">
        <Input
          value={draft}
          placeholder={placeholder ?? "Add…"}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), add())}
        />
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
  const [uploadWarnings, setUploadWarnings] = useState<string[]>(data.warnings ?? []);
  useEffect(() => {
    setP(data.profile);
    setExtraText(splitProfileMaterial(data.extra_text).notes);
  }, [data]);
  useEffect(() => {
    if (data.warnings?.length) setUploadWarnings(data.warnings);
  }, [data.warnings]);

  const set = <K extends keyof Profile>(k: K, v: Profile[K]) => setP((x) => ({ ...x, [k]: v }));
  const setPref = <K extends keyof Profile["preferences"]>(k: K, v: Profile["preferences"][K]) =>
    setP((x) => ({ ...x, preferences: { ...x.preferences, [k]: v } }));
  const dirty =
    JSON.stringify(p) !== JSON.stringify(data.profile) ||
    extraText !== material.notes ||
    Object.values(answers).some(Boolean) ||
    Object.values(discovery).some(Boolean);

  const save = useMutation({
    mutationFn: () => {
      const text = [extraText, material.documents].filter(Boolean).join("\n\n");
      return saveProfileWithAnswers(api, p, text, answers, discovery);
    },
    onSuccess: (d) => {
      qc.setQueryData(qk.profile, d);
      setAnswers({});
      setDiscovery({});
      qc.invalidateQueries({ queryKey: ["job"] });
      qc.setQueryData(["radar", "last"], null);
      toast.success("Profile saved", {
        description: "Run Radar again to see matches based on your updated profile.",
        duration: 7000,
      });
    },
    onError: (e) => toast.error(`Couldn't save: ${e.message}`),
  });

  return (
    <fieldset disabled={save.isPending} className="min-w-0">
      <PageHeader
        title="Your story, in focus."
        subtitle="The experience you bring. The things that move you. This is where your search begins."
        actions={
          <>
            <Button variant="outline" onClick={() => setReupload((v) => !v)}>
              <FileUp /> {reupload ? "Cancel" : "Upload new CV"}
            </Button>
            <Button disabled={!dirty || save.isPending} onClick={() => save.mutate()}>
              {save.isPending ? <Loader2 className="animate-spin" /> : <Save />}{" "}
              {save.isPending ? "Saving…" : "Save changes"}
            </Button>
          </>
        }
      />

      <div className="profile-banner">
        <div className="profile-avatar" aria-hidden="true">
          {p.name
            .split(/\s+/)
            .slice(0, 2)
            .map((part) => part[0])
            .join("") || "R"}
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="text-xl font-semibold tracking-tight">{p.name || "Your profile"}</h2>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{p.headline}</p>
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[9px] text-primary">
            <span>{p.skills.length} SKILLS</span>
            <span>{p.projects.length} PROJECTS</span>
            <span>UPDATED {formatDate(data.updated_at)}</span>
          </div>
        </div>
      </div>

      {reupload && (
        <div className="mb-8">
          <UploadScreen
            onDone={(updated) => {
              setAnswers({});
              setDiscovery({});
              setUploadWarnings(updated.warnings ?? []);
              setReupload(false);
            }}
          />
        </div>
      )}

      <DocumentWarnings warnings={uploadWarnings} />

      {p.missing_info.length > 0 && (
        <details className="radar-panel questions-panel mb-4">
          <summary className="flex list-none items-center gap-3">
            <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-primary-soft text-primary">
              <HelpCircle className="size-5" />
            </span>
            <span className="flex-1">
              <span className="block text-sm font-semibold">
                A few details. A clearer direction.
              </span>
              <span className="mt-1 block text-xs text-muted-foreground">
                {p.missing_info.length} questions to sharpen your profile
              </span>
            </span>
            <Plus className="size-4 text-primary" />
          </summary>
          <div className="mt-6 space-y-4 border-t pt-5">
            {p.missing_info.map((q, i) => (
              <div key={q}>
                <Label className="text-foreground">{q}</Label>
                <Input
                  className="mt-1.5 bg-card"
                  value={answers[i] ?? ""}
                  onChange={(e) => setAnswers((a) => ({ ...a, [i]: e.target.value }))}
                  placeholder="Your answer"
                />
              </div>
            ))}
            <p className="text-xs text-muted-foreground">
              Save changes to update your profile and search preferences from these answers. This
              can take a few seconds.
            </p>
          </div>
        </details>
      )}

      <details className="radar-panel mb-6">
        <summary className="flex list-none items-center gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-info-soft text-info-foreground">
            <Sparkles className="size-5" />
          </span>
          <span className="flex-1">
            <span className="block text-sm font-semibold">
              There might be a path you haven't thought of.
            </span>
            <span className="mt-1 block text-xs text-muted-foreground">
              Explore your interests, beyond job titles
            </span>
          </span>
          <Plus className="size-4 text-info-foreground" />
        </summary>
        <p className="mb-4 mt-6 border-t pt-5 text-sm text-muted-foreground">
          Tell us what you enjoy doing, even if you do not know the job title. Save changes to
          refine your profile and search preferences, then run JobbRadar again. Interests are not
          treated as demonstrated skills.
        </p>
        <div className="space-y-4">
          {DISCOVERY_QUESTIONS.map((question, i) => (
            <div key={question}>
              <Label htmlFor={`discovery-${i}`}>{question}</Label>
              <Textarea
                id={`discovery-${i}`}
                className="mt-1.5"
                rows={2}
                placeholder="A concrete example is helpful…"
                value={discovery[i] ?? ""}
                onChange={(e) => setDiscovery((previous) => ({ ...previous, [i]: e.target.value }))}
              />
            </div>
          ))}
        </div>
      </details>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Panel title="Summary">
            <div className="space-y-4">
              <div>
                <Label>Headline</Label>
                <Input
                  className="mt-1.5"
                  value={p.headline}
                  onChange={(e) => set("headline", e.target.value)}
                />
              </div>
              <div>
                <Label>Summary</Label>
                <Textarea
                  className="mt-1.5"
                  rows={4}
                  value={p.summary}
                  onChange={(e) => set("summary", e.target.value)}
                />
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
                        {x.location && ` · ${x.location}`} · {x.start_date ?? "?"} –{" "}
                        {x.end_date ?? "present"}
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="Remove experience"
                      onClick={() =>
                        set(
                          "experiences",
                          p.experiences.filter((_, j) => j !== i),
                        )
                      }
                    >
                      <Trash2 />
                    </Button>
                  </div>
                  <Textarea
                    className="mt-3 text-sm"
                    rows={Math.max(2, x.bullets.length)}
                    value={x.bullets.join("\n")}
                    onChange={(e) =>
                      set(
                        "experiences",
                        p.experiences.map((y, j) =>
                          j === i ? { ...y, bullets: e.target.value.split("\n") } : y,
                        ),
                      )
                    }
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
                  <span className="text-muted-foreground">
                    ({e.start_date ?? "?"} – {e.end_date ?? "present"})
                  </span>
                </div>
              ))}
              <div className="my-4 border-t" />
              {p.projects.map((pr, i) => (
                <div key={i} className="text-sm">
                  <span className="font-semibold">{pr.name}</span> —{" "}
                  <span className="text-muted-foreground">{pr.description}</span>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        <div className="space-y-6">
          <Panel title="Preferences">
            <div className="space-y-5">
              <ListEditor
                label="Target roles"
                items={p.preferences.roles}
                onChange={(v) => setPref("roles", v)}
              />
              <ListEditor
                label="Industries & interests"
                items={p.preferences.industries ?? []}
                onChange={(v) => setPref("industries", v)}
                placeholder="E.g. aviation, energy, technology"
              />
              <ListEditor
                label="Cities"
                items={p.preferences.cities}
                onChange={(v) => setPref("cities", v)}
              />
              <div>
                <Label>Seniority</Label>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {SENIORITY.map((s) => (
                    <Button
                      key={s}
                      size="sm"
                      variant={p.preferences.seniority === s ? "default" : "outline"}
                      onClick={() => setPref("seniority", s)}
                      className="capitalize"
                    >
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
                      <Button
                        key={m}
                        size="sm"
                        variant={on ? "default" : "outline"}
                        className="capitalize"
                        onClick={() =>
                          setPref(
                            "work_modes",
                            on
                              ? p.preferences.work_modes.filter((x) => x !== m)
                              : [...p.preferences.work_modes, m],
                          )
                        }
                      >
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
            <Textarea
              rows={4}
              value={extraText}
              onChange={(e) => setExtraText(e.target.value)}
              placeholder="Extra context for matching and applications"
            />
            {material.documents && (
              <details className="mt-3">
                <summary className="cursor-pointer text-sm font-medium">
                  Imported document text
                </summary>
                <p className="my-2 text-xs text-muted-foreground">
                  Check that this text is readable before relying on it. If it is garbled, paste the
                  correct information into your notes and ask for the document to be reprocessed.
                </p>
                <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words rounded-md bg-muted p-2 text-xs">
                  {material.documents}
                </pre>
              </details>
            )}
          </Panel>

          <Panel title="Search terms">
            <div className="flex flex-wrap gap-1">
              {p.search_terms.map((t) => (
                <span
                  key={t}
                  className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground"
                >
                  {t}
                </span>
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
      {dirty && (
        <div className="profile-savebar">
          <div>
            <p className="text-sm font-semibold">Your next move starts with a clear profile.</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {save.isPending
                ? "Reviewing your updates. This may take a few seconds."
                : "Save your changes before running a new scan."}
            </p>
          </div>
          <Button disabled={save.isPending} onClick={() => save.mutate()}>
            {save.isPending ? <Loader2 className="animate-spin" /> : <Save />}
            {save.isPending ? "Saving…" : "Save changes"}
          </Button>
        </div>
      )}
    </fieldset>
  );
}
