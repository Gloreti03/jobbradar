// Preserve imported source text verbatim while keeping personal notes editable.
export function splitProfileMaterial(text: string) {
  const marker = /(?:^|\n)--- [^\n]+ ---\r?\n/.exec(text);
  if (!marker) return { notes: text, documents: "" };
  return {
    notes: text.slice(0, marker.index).trimEnd(),
    documents: text.slice(marker.index).trimStart(),
  };
}

export function mergeAttachments(current: File[], incoming: File[]) {
  const files = [...current];
  for (const file of incoming) {
    if (
      !files.some(
        (f) => f.name === file.name && f.size === file.size && f.lastModified === file.lastModified,
      )
    ) {
      files.push(file);
    }
  }
  return files;
}

export const DISCOVERY_QUESTIONS = [
  "Which project or course did you enjoy most, and what did you personally do?",
  "What would you like to spend more time doing: analysing data, improving processes, building products, or working with people? Give an example.",
  "Which problem in an industry you care about would you like to help solve? You do not need to know the job title.",
];

// The backend persists Q&A sections in extra_text. Keep the latest answer for
// each question, including multiline answers, without reading imported files as Q&A.
export function readProfileAnswers(text: string): Record<string, string> {
  const answers: Record<string, string> = {};
  for (const section of text.split(/(?:^|\n)--- Answers to profile questions ---\r?\n/).slice(1)) {
    const body = section.split(/\n--- [^\n]+ ---\r?\n/)[0] ?? "";
    const entries = body.matchAll(/(?:^|\n)Q: ([^\n]+)\r?\nA: ([\s\S]*?)(?=\nQ: |$)/g);
    for (const entry of entries) {
      if (entry[1] && entry[2] !== undefined) answers[entry[1].trim()] = entry[2].trim();
    }
  }
  return answers;
}
