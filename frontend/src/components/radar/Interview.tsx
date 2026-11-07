// D — Mock interview, text mode (owner: Matilde).
// Flow: intro -> POST /interview/{id}/start -> 6 x POST /turn -> POST /feedback -> <Feedback/>.
// Resumes the latest interview (GET /interview/{id}) when the page is reopened.
import { Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Suspense, lazy, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ArrowLeft, Bot, CheckCircle2, Loader2, Lock, MessagesSquare, Mic, RotateCcw, Send, Sparkles, User } from "lucide-react";
import { api, isNotFound, qk } from "@/api";
import type { ApplicationOut, InterviewFeedback, InterviewOut, InterviewQuestion, TranscriptTurn } from "@/types";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import { EmptyState, ErrorState, LoadingState, Panel, formatDate } from "@/components/radar/shared";
import { Feedback } from "@/components/radar/Feedback";
import { cn } from "@/lib/utils";

// Loaded only when the user picks voice: keeps the ElevenLabs SDK out of the first page load (and of SSR).
const VoiceInterview = lazy(() => import("@/components/radar/VoiceInterview"));

const PLAN_PREVIEW: { kind: string; text: string }[] = [
  { kind: "Intro", text: "Who you are and why this role" },
  { kind: "Experience ×2", text: "Real situations from the CV you sent" },
  { kind: "Technical ×2", text: "Key requirements of the job ad — one may be a gap you don't meet yet" },
  { kind: "Motivation", text: "Why this company, what you want to learn" },
];

export function Interview({ app }: { app: ApplicationOut }) {
  const unlocked = app.status !== "draft" && app.snapshot != null;
  const existing = useQuery({
    queryKey: qk.interview(app.id),
    queryFn: async () => {
      try {
        return await api.getInterview(app.id);
      } catch (e) {
        if (isNotFound(e)) return null; // no interview yet
        throw e;
      }
    },
    enabled: unlocked,
    retry: false,
    refetchOnWindowFocus: false,
  });

  if (!unlocked) {
    return (
      <EmptyState
        icon={<Lock className="size-6" />}
        title="Apply first, then practice"
        body='The mock interview is based on the CV and cover letter you actually sent. Submit on the company site, then press "I applied".'
        action={
          <Button asChild>
            <Link to="/applications/$id" params={{ id: String(app.id) }}>Go to application</Link>
          </Button>
        }
      />
    );
  }
  if (existing.isPending) return <LoadingState label="Loading interview…" />;
  if (existing.isError) return <ErrorState error={existing.error} onRetry={() => existing.refetch()} />;
  return <InterviewSession app={app} initial={existing.data} />;
}

function InterviewSession({ app, initial }: { app: ApplicationOut; initial: InterviewOut | null }) {
  const qc = useQueryClient();
  const [plan, setPlan] = useState<InterviewQuestion[]>(initial?.plan ?? []);
  const [transcript, setTranscript] = useState<TranscriptTurn[]>(initial?.transcript ?? []);
  const [feedback, setFeedback] = useState<InterviewFeedback | null>(initial?.feedback ?? null);
  const [draft, setDraft] = useState("");
  const [voice, setVoice] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const started = plan.length > 0;
  const answered = transcript.filter((t) => t.role === "candidate").length;
  const done = started && answered >= plan.length;
  const current = plan[answered];

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [transcript.length]);

  const startM = useMutation({
    mutationFn: () => api.startInterview(app.id, "text"),
    onSuccess: (r) => {
      setPlan(r.plan);
      setTranscript([{ role: "interviewer", content: r.message, question_id: r.plan[0]?.id ?? null }]);
      setFeedback(null);
      setDraft("");
      qc.invalidateQueries({ queryKey: qk.interview(app.id) });
    },
    onError: (e) => toast.error(`Couldn't start the interview: ${e.message}`),
  });

  const turnM = useMutation({
    mutationFn: (answer: string) => api.interviewTurn(app.id, answer),
    onMutate: (answer) => {
      // show the answer right away
      setTranscript((t) => [...t, { role: "candidate", content: answer, question_id: current?.id ?? null }]);
      setDraft("");
    },
    onSuccess: (r) => {
      const next = plan[r.question_index];
      setTranscript((t) => [...t, { role: "interviewer", content: r.message, question_id: r.done ? null : next?.id ?? null }]);
    },
    onError: (e, answer) => {
      setTranscript((t) => t.slice(0, -1)); // remove the optimistic answer
      setDraft(answer);
      toast.error(`Couldn't send your answer: ${e.message}`);
    },
  });

  const feedbackM = useMutation({
    mutationFn: () => api.interviewFeedback(app.id),
    onSuccess: (f) => {
      setFeedback(f);
      qc.invalidateQueries({ queryKey: qk.interview(app.id) });
    },
    onError: (e) => toast.error(`Couldn't get the feedback: ${e.message}`),
  });

  const send = () => {
    const answer = draft.trim();
    if (!answer || turnM.isPending || done) return;
    turnM.mutate(answer);
  };

  const header = (
    <div className="mb-6">
      <Link
        to="/applications/$id"
        params={{ id: String(app.id) }}
        className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Back to application
      </Link>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Interview practice</h1>
          <p className="mt-1 text-muted-foreground">
            {app.job.title} · {app.job.company ?? "Unknown company"}
            {app.applied_at && ` · Applied ${formatDate(app.applied_at)}`}
          </p>
        </div>
        {started && !voice && (
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => setVoice(true)}>
              <Mic /> Voice interview
            </Button>
            <Button variant="outline" disabled={startM.isPending} onClick={() => startM.mutate()}>
              {startM.isPending ? <Loader2 className="animate-spin" /> : <RotateCcw />} New text interview
            </Button>
          </div>
        )}
      </div>
    </div>
  );

  // --- voice mode (ElevenLabs)
  if (voice) {
    return (
      <div>
        {header}
        <Suspense fallback={<LoadingState label="Loading voice interview…" />}>
          <VoiceInterview
            app={app}
            onUseText={() => setVoice(false)}
            onFeedback={(r) => {
              setPlan(r.plan);
              setTranscript(r.transcript);
              setFeedback(r.feedback);
              setVoice(false);
              qc.invalidateQueries({ queryKey: qk.interview(app.id) });
            }}
          />
        </Suspense>
      </div>
    );
  }

  // --- 1. not started yet
  if (!started) {
    return (
      <div>
        {header}
        <Panel className="mx-auto max-w-2xl">
          <div className="mb-4 flex items-center gap-3">
            <div className="rounded-full bg-primary-soft p-3 text-primary">
              <MessagesSquare className="size-6" />
            </div>
            <div>
              <h2 className="text-lg font-semibold">A 6-question mock interview</h2>
              <p className="text-sm text-muted-foreground">
                Built from this job ad and the CV and cover letter you sent. Type your answers as you would say them.
              </p>
            </div>
          </div>
          <ul className="mb-6 space-y-2 text-sm">
            {PLAN_PREVIEW.map((p) => (
              <li key={p.kind} className="flex gap-3">
                <span className="w-28 shrink-0 font-semibold">{p.kind}</span>
                <span className="text-muted-foreground">{p.text}</span>
              </li>
            ))}
          </ul>
          <Button size="lg" className="w-full" disabled={startM.isPending} onClick={() => startM.mutate()}>
            {startM.isPending ? (
              <>
                <Loader2 className="animate-spin" /> Preparing questions from your CV and the job ad…
              </>
            ) : (
              <>
                <MessagesSquare /> Start text interview
              </>
            )}
          </Button>
          <Button size="lg" variant="outline" className="mt-3 w-full" disabled={startM.isPending} onClick={() => setVoice(true)}>
            <Mic /> Start voice interview
          </Button>
          <p className="mt-3 text-center text-xs text-muted-foreground">At the end you get a score and a stronger answer for every question.</p>
        </Panel>
      </div>
    );
  }

  // --- 3. feedback
  if (feedback) {
    return (
      <div>
        {header}
        <Feedback feedback={feedback} plan={plan} transcript={transcript} />
      </div>
    );
  }

  // --- 2. conversation
  return (
    <div>
      {header}
      <div className="mx-auto max-w-3xl">
        <div className="mb-4">
          <div className="mb-1.5 flex justify-between text-sm text-muted-foreground">
            <span>{done ? "All questions answered" : `Question ${answered + 1} of ${plan.length}`}</span>
            {current && !done && <span className="truncate pl-4">Focus: {current.focus}</span>}
          </div>
          <Progress value={(answered / plan.length) * 100} />
        </div>

        <Panel className="p-0">
          <div className="max-h-[55vh] min-h-[300px] space-y-4 overflow-y-auto p-6">
            {transcript.map((t, i) => (
              <Bubble key={i} turn={t} />
            ))}
            {turnM.isPending && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Bot className="size-4" /> <Loader2 className="size-4 animate-spin" /> Interviewer is thinking…
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="border-t p-4">
            {done ? (
              <div className="flex flex-wrap items-center gap-3">
                <CheckCircle2 className="size-5 text-primary" />
                <span className="mr-auto text-sm font-medium">Interview complete.</span>
                <Button disabled={feedbackM.isPending} onClick={() => feedbackM.mutate()}>
                  {feedbackM.isPending ? (
                    <>
                      <Loader2 className="animate-spin" /> Evaluating your answers (about 10–15 s)…
                    </>
                  ) : (
                    <>
                      <Sparkles /> Get my feedback
                    </>
                  )}
                </Button>
              </div>
            ) : (
              <>
                <Textarea
                  rows={3}
                  value={draft}
                  placeholder="Type your answer…"
                  disabled={turnM.isPending}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                      e.preventDefault();
                      send();
                    }
                  }}
                />
                <div className="mt-2 flex flex-wrap items-center gap-3">
                  <span className="mr-auto text-xs text-muted-foreground">Ctrl + Enter to send</span>
                  {answered > 0 && (
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={feedbackM.isPending || turnM.isPending}
                      onClick={() => feedbackM.mutate()}
                    >
                      {feedbackM.isPending ? <Loader2 className="animate-spin" /> : null} Finish now and get feedback
                    </Button>
                  )}
                  <Button disabled={!draft.trim() || turnM.isPending} onClick={send}>
                    <Send /> Send
                  </Button>
                </div>
              </>
            )}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function Bubble({ turn }: { turn: TranscriptTurn }) {
  const me = turn.role === "candidate";
  return (
    <div className={cn("flex gap-3", me && "flex-row-reverse")}>
      <div
        className={cn(
          "flex size-8 shrink-0 items-center justify-center rounded-full",
          me ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground",
        )}
      >
        {me ? <User className="size-4" /> : <Bot className="size-4" />}
      </div>
      <div
        className={cn(
          "max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
          me ? "rounded-tr-sm bg-primary text-primary-foreground" : "rounded-tl-sm bg-muted",
        )}
      >
        {turn.content}
      </div>
    </div>
  );
}
