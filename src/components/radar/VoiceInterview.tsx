// D — Voice mock interview with ElevenLabs (owner: Matilde).
// 1. POST /interview/{id}/start {mode: "voice"} -> same 6-question plan as the text interview
// 2. GET /voice/signed-url -> short-lived URL (the API key never leaves the backend)
// 3. ElevenLabs call: the agent asks the plan questions (dynamic variables)
// 4. POST /interview/{id}/voice-transcript + POST /interview/{id}/feedback -> <Feedback/>
// Microphone denied or voice unavailable -> the user can continue in text mode.
import { ConversationProvider, useConversation } from "@elevenlabs/react";
import { useEffect, useRef, useState } from "react";
import { Bot, Keyboard, Loader2, Mic, MicOff, PhoneOff, Sparkles, User } from "lucide-react";
import { api } from "@/api";
import type { ApplicationOut, InterviewFeedback, InterviewQuestion, TranscriptTurn, VoiceTurn } from "@/types";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/radar/shared";
import { cn } from "@/lib/utils";

export type VoiceResult = { plan: InterviewQuestion[]; transcript: TranscriptTurn[]; feedback: InterviewFeedback };

type Props = {
  app: ApplicationOut;
  onUseText: () => void;
  onFeedback: (result: VoiceResult) => void;
};

export default function VoiceInterview(props: Props) {
  return (
    <ConversationProvider>
      <VoiceCall {...props} />
    </ConversationProvider>
  );
}

type Phase = "ready" | "preparing" | "live" | "ended" | "evaluating";

function VoiceCall({ app, onUseText, onFeedback }: Props) {
  const [phase, setPhase] = useState<Phase>("ready");
  const [problem, setProblem] = useState<string | null>(null);
  const [plan, setPlan] = useState<InterviewQuestion[]>([]);
  const [turns, setTurns] = useState<VoiceTurn[]>([]);
  const turnsRef = useRef<VoiceTurn[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  const conversation = useConversation({
    onMessage: ({ message, source }) => {
      const text = message?.trim();
      if (!text) return;
      const turn: VoiceTurn = { role: source === "ai" ? "interviewer" : "candidate", content: text };
      turnsRef.current = [...turnsRef.current, turn];
      setTurns(turnsRef.current);
    },
    onDisconnect: () => setPhase((p) => (p === "live" || p === "preparing" ? "ended" : p)),
    onError: (message) => setProblem(`Voice connection problem: ${message}`),
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length]);

  // end the call if the user leaves the page
  useEffect(() => () => conversation.endSession(), []); // eslint-disable-line react-hooks/exhaustive-deps

  const answered = turns.filter((t) => t.role === "candidate").length;

  async function start() {
    setProblem(null);
    setPhase("preparing");
    // 1. microphone permission first: clear message if it is blocked
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((t) => t.stop());
    } catch {
      setPhase("ready");
      setProblem("Microphone access was blocked. Allow the microphone in your browser (icon in the address bar), or continue in text mode.");
      return;
    }
    try {
      // 2. signed URL first: if voice is not configured we do not create an interview
      const { signed_url } = await api.getVoiceSignedUrl();
      // 3. same plan as the text interview
      const started = await api.startInterview(app.id, "voice");
      setPlan(started.plan);
      turnsRef.current = [];
      setTurns([]);
      const firstName = (app.snapshot?.cv.name ?? app.cv.name ?? "").split(" ")[0] || "there";
      conversation.startSession({
        signedUrl: signed_url,
        dynamicVariables: {
          first_message: started.message,
          candidate_name: firstName,
          job_title: app.job.title,
          company: app.job.company ?? "the company",
          questions: started.plan.map((q, i) => `${i + 1}. ${q.question}`).join("\n"),
        },
      });
      setPhase("live");
    } catch (e) {
      setPhase("ready");
      setProblem(`Voice isn't available right now (${e instanceof Error ? e.message : String(e)}). You can continue in text mode.`);
    }
  }

  function hangUp() {
    conversation.endSession();
    setPhase("ended");
  }

  async function getFeedback() {
    setProblem(null);
    setPhase("evaluating");
    try {
      const saved = await api.saveVoiceTranscript(app.id, turnsRef.current);
      const feedback = await api.interviewFeedback(app.id);
      onFeedback({ plan: saved.plan, transcript: saved.transcript, feedback });
    } catch (e) {
      setPhase("ended");
      setProblem(`Couldn't get the feedback: ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  return (
    <Panel className="mx-auto max-w-3xl">
      <div className="mb-5 flex flex-wrap items-center gap-4">
        <div
          className={cn(
            "flex size-14 items-center justify-center rounded-full transition-colors",
            phase === "live" && conversation.isSpeaking && "bg-primary text-primary-foreground animate-pulse",
            phase === "live" && !conversation.isSpeaking && "bg-primary-soft text-primary",
            phase !== "live" && "bg-muted text-muted-foreground",
          )}
        >
          {phase === "live" ? <Mic className="size-6" /> : <MicOff className="size-6" />}
        </div>
        <div className="mr-auto">
          <h2 className="text-lg font-semibold">Voice interview</h2>
          <p className="text-sm text-muted-foreground">
            {phase === "ready" && "Talk with an AI interviewer. Same 6 questions as the text interview, based on what you sent."}
            {phase === "preparing" && "Preparing your questions and connecting…"}
            {phase === "live" &&
              (conversation.isSpeaking ? "The interviewer is speaking…" : "Listening — answer out loud.") +
                (plan.length ? ` · ${Math.min(answered, plan.length)} of ${plan.length} answered` : "")}
            {phase === "ended" && (answered ? "Call ended. Get your feedback on the answers you gave." : "Call ended before any answer.")}
            {phase === "evaluating" && "Evaluating your answers (about 10–15 s)…"}
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={onUseText} disabled={phase === "live" || phase === "evaluating"}>
          <Keyboard /> Use text instead
        </Button>
      </div>

      {problem && (
        <div className="mb-4 rounded-lg border border-warning/40 bg-warning-soft p-3 text-sm text-warning-foreground">
          {problem}
          <div className="mt-2">
            <Button size="sm" variant="outline" className="bg-card" onClick={onUseText}>
              <Keyboard /> Continue in text mode
            </Button>
          </div>
        </div>
      )}

      {turns.length > 0 && (
        <div className="mb-4 max-h-[45vh] space-y-3 overflow-y-auto rounded-lg border bg-muted/30 p-4">
          {turns.map((t, i) => (
            <div key={i} className={cn("flex gap-2 text-sm", t.role === "candidate" && "flex-row-reverse text-right")}>
              {t.role === "candidate" ? (
                <User className="mt-0.5 size-4 shrink-0 text-primary" />
              ) : (
                <Bot className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
              )}
              <p className={cn("max-w-[85%]", t.role === "candidate" ? "text-foreground" : "text-foreground/80")}>{t.content}</p>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        {(phase === "ready" || phase === "preparing") && (
          <Button size="lg" className="w-full" disabled={phase === "preparing"} onClick={start}>
            {phase === "preparing" ? (
              <>
                <Loader2 className="animate-spin" /> Connecting…
              </>
            ) : (
              <>
                <Mic /> Start voice interview
              </>
            )}
          </Button>
        )}
        {phase === "live" && (
          <Button size="lg" variant="destructive" className="w-full" onClick={hangUp}>
            <PhoneOff /> End interview
          </Button>
        )}
        {(phase === "ended" || phase === "evaluating") && (
          <>
            <Button size="lg" className="flex-1" disabled={!answered || phase === "evaluating"} onClick={getFeedback}>
              {phase === "evaluating" ? <Loader2 className="animate-spin" /> : <Sparkles />} Get my feedback
            </Button>
            <Button size="lg" variant="outline" disabled={phase === "evaluating"} onClick={start}>
              <Mic /> Try again
            </Button>
          </>
        )}
      </div>
      {phase === "ready" && (
        <p className="mt-3 text-center text-xs text-muted-foreground">
          Your browser will ask for the microphone. You can end the call any time and get feedback on the answers you gave.
        </p>
      )}
    </Panel>
  );
}
