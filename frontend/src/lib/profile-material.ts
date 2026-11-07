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
    if (!files.some((f) => f.name === file.name && f.size === file.size && f.lastModified === file.lastModified)) {
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
