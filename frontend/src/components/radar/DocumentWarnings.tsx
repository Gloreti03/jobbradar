import { AlertTriangle } from "lucide-react";

export function DocumentWarnings({ warnings = [] }: { warnings?: string[] }) {
  if (!warnings.length) return null;
  return <div role="alert" className="mb-6 rounded-xl border border-warning/40 bg-warning-soft p-5">
    <div className="flex items-center gap-2 text-sm font-semibold text-warning-foreground"><AlertTriangle className="size-4" /> Some material needs your attention</div>
    <ul className="mt-3 list-disc space-y-2 pl-5 text-xs leading-relaxed text-warning-foreground">{warnings.map((warning, i) => <li key={i}>{warning}</li>)}</ul>
    <p className="mt-3 text-xs text-warning-foreground">Review your profile against the original documents, especially course names and grades read with OCR. If a file could not be read, paste its text when uploading again.</p>
  </div>;
}
