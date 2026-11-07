import { ChevronDown, SlidersHorizontal } from "lucide-react";
import type { RadarFunnel } from "@/types";

const stages: { key: keyof RadarFunnel; label: string }[] = [
  { key: "total", label: "Catalogue" }, { key: "recent", label: "Recent" },
  { key: "location", label: "Location" }, { key: "language", label: "Language" },
  { key: "keywords", label: "Keywords" }, { key: "deduplicated", label: "Unique" },
  { key: "live", label: "Still open" }, { key: "ranked", label: "Ranked" },
];

export function ScanFunnel({ funnel, resultCount = 0 }: { funnel?: RadarFunnel | null | undefined; resultCount?: number }) {
  if (!funnel) return null;
  const inconsistentRanked = funnel.ranked === 0 && resultCount > 0;
  const visibleStages = inconsistentRanked ? stages.filter(({ key }) => key !== "ranked") : stages;
  return <details className="mb-6 rounded-xl border bg-card p-5">
    <summary className="flex list-none items-center gap-3 text-xs font-semibold"><SlidersHorizontal className="size-4 text-primary" /><span className="flex-1">How this scan was narrowed</span><ChevronDown className="size-4 text-muted-foreground" /></summary>
    <p className="mb-5 mt-4 text-xs leading-relaxed text-muted-foreground">Openings remaining after each step. These are the counts for this scan, not estimates.</p>
    <ol className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      {visibleStages.map(({ key, label }, index) => <li key={key} className="min-w-0"><div className="mb-2 flex items-center gap-2 text-[10px] text-muted-foreground"><span className="font-mono opacity-60">0{index + 1}</span>{label}</div><div className="text-lg font-semibold">{funnel[key].toLocaleString()}</div><div aria-hidden="true" className="mt-2 h-1 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-primary/70" style={{ width: `${funnel.total > 0 ? Math.min(100, Math.max(0, funnel[key] / funnel.total * 100)) : 0}%` }} /></div></li>)}
    </ol>
    {inconsistentRanked && <p className="mt-4 text-xs text-muted-foreground">The ranking count is temporarily unavailable. Your opportunities are shown below.</p>}
  </details>;
}
