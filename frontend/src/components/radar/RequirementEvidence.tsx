import { CheckCircle2, CircleMinus, CircleX, FileCheck2 } from "lucide-react";
import type { RequirementMatch } from "@/types";
import { cn } from "@/lib/utils";
import { Panel } from "./shared";

const statuses = {
  met: {
    label: "Supported",
    Icon: CheckCircle2,
    tone: "text-emerald-800",
    background: "bg-emerald-50",
  },
  partial: {
    label: "Partially supported",
    Icon: CircleMinus,
    tone: "text-warning-foreground",
    background: "bg-warning-soft",
  },
  missing: {
    label: "Not evidenced",
    Icon: CircleX,
    tone: "text-muted-foreground",
    background: "bg-muted",
  },
};

export function RequirementEvidence({ items = [] }: { items?: RequirementMatch[] }) {
  if (!items.length)
    return (
      <Panel title="Why this CV fits" icon={<FileCheck2 className="size-4" />}>
        <p className="text-sm leading-relaxed text-muted-foreground">
          This draft has no requirement evidence map. Generate a new draft to see requirements
          linked to your experience.
        </p>
      </Panel>
    );
  return (
    <Panel title="Why this CV fits" icon={<FileCheck2 className="size-4" />}>
      <p className="mb-5 text-xs leading-relaxed text-muted-foreground">
        Requirements linked to evidence from the candidate material used to generate this draft.
        Review this analysis again after editing your documents.
      </p>
      <div className="mb-6 flex flex-wrap gap-2">
        {(["met", "partial", "missing"] as const).map((status) => (
          <span
            key={status}
            className={cn(
              "rounded-full px-3 py-1 text-[11px] font-semibold",
              statuses[status].background,
              statuses[status].tone,
            )}
          >
            {items.filter((item) => item.status === status).length}{" "}
            {statuses[status].label.toLowerCase()}
          </span>
        ))}
      </div>
      <ul className="space-y-5">
        {items.map((item, index) => {
          const { Icon, tone, label } = statuses[item.status];
          return (
            <li
              key={`${item.requirement}-${index}`}
              className="border-t pt-5 first:border-0 first:pt-0"
            >
              <div className="flex items-start gap-3">
                <Icon aria-hidden="true" className={cn("mt-0.5 size-4 shrink-0", tone)} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold leading-relaxed">{item.requirement}</p>
                  <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[10px]">
                    <span className={cn("font-semibold", tone)}>{label}</span>
                    <span className="text-muted-foreground">
                      · {item.importance === "required" ? "Required" : "Nice to have"}
                    </span>
                  </div>
                  {item.evidence.length > 0 ? (
                    item.evidence.map((quote, i) => (
                      <blockquote
                        key={i}
                        className="mt-3 border-l-2 border-emerald-800/25 pl-3 text-xs leading-relaxed text-foreground/80"
                      >
                        “{quote}”
                      </blockquote>
                    ))
                  ) : (
                    <p className="mt-2 text-xs text-muted-foreground">
                      No supporting quote was supplied.
                    </p>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}
