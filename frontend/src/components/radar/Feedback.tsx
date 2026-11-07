// D — Interview feedback (owner: Matilde). Shows the evaluation returned by
// POST /interview/{application_id}/feedback. Better answers use only true facts from the CV.
import { Lightbulb, MessageSquareQuote, Sparkles, ThumbsUp, TrendingUp } from "lucide-react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Panel, Points, ScoreRing } from "@/components/radar/shared";
import { cn } from "@/lib/utils";
import type { InterviewFeedback, InterviewQuestion, TranscriptTurn } from "@/types";

const kindLabel: Record<InterviewQuestion["kind"], string> = {
  intro: "Intro",
  behavioral: "Experience",
  technical: "Technical",
  motivation: "Motivation",
  gap: "Gap",
};

function scoreTone(score: number) {
  if (score >= 4) return "bg-primary-soft text-accent-foreground";
  if (score === 3) return "bg-info-soft text-info-foreground";
  return "bg-warning-soft text-warning-foreground";
}

export function Feedback({
  feedback,
  plan,
  transcript,
}: {
  feedback: InterviewFeedback;
  plan: InterviewQuestion[];
  transcript: TranscriptTurn[];
}) {
  const answerOf = (questionId: number) =>
    transcript.find((t) => t.role === "candidate" && t.question_id === questionId)?.content;
  const kindOf = (questionId: number) => plan.find((q) => q.id === questionId)?.kind;

  return (
    <div className="space-y-6">
      <Panel>
        <div className="flex flex-wrap items-center gap-6">
          <ScoreRing score={feedback.overall_score} size={88} />
          <div className="min-w-0 flex-1">
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <Sparkles className="size-5 text-primary" /> Your interview feedback
            </h2>
            <p className="mt-1.5 text-foreground/80">{feedback.summary}</p>
          </div>
        </div>
        <div className="mt-6 grid gap-6 text-sm md:grid-cols-2">
          <Points icon={<ThumbsUp className="size-3.5" />} title="Strengths" items={feedback.strengths} tone="text-primary" />
          <Points
            icon={<TrendingUp className="size-3.5" />}
            title="To improve"
            items={feedback.improvements}
            tone="text-warning-foreground"
          />
        </div>
      </Panel>

      <Panel title="Question by question" icon={<MessageSquareQuote className="size-4" />}>
        <Accordion type="multiple" className="w-full">
          {feedback.questions.map((q) => {
            const kind = kindOf(q.question_id);
            const answer = answerOf(q.question_id);
            return (
              <AccordionItem key={q.question_id} value={String(q.question_id)}>
                <AccordionTrigger className="text-left hover:no-underline">
                  <div className="flex min-w-0 flex-1 items-start gap-3 pr-3">
                    <span className={cn("shrink-0 rounded-md px-2 py-0.5 font-mono text-xs font-semibold", scoreTone(q.score))}>
                      {q.score}/5
                    </span>
                    <span className="min-w-0">
                      {kind && (
                        <span className="mr-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          {kindLabel[kind]}
                        </span>
                      )}
                      <span className="font-medium">{q.question}</span>
                    </span>
                  </div>
                </AccordionTrigger>
                <AccordionContent className="space-y-4 text-sm">
                  {answer != null && (
                    <div>
                      <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Your answer</div>
                      <p className="text-foreground/80">{answer || "—"}</p>
                    </div>
                  )}
                  <div>
                    <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Comment</div>
                    <p>{q.comment}</p>
                  </div>
                  <div className="rounded-lg border border-primary/25 bg-primary-soft/50 p-4">
                    <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-primary">
                      <Lightbulb className="size-3.5" /> A stronger answer
                    </div>
                    <p className="leading-relaxed">{q.better_answer}</p>
                  </div>
                </AccordionContent>
              </AccordionItem>
            );
          })}
        </Accordion>
        <p className="mt-4 text-xs text-muted-foreground">
          Stronger answers are built only from facts in the CV and cover letter you sent and from what you said — nothing invented.
        </p>
      </Panel>
    </div>
  );
}
