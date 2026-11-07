import { jsPDF } from "jspdf";
import type { TailoredCV } from "@/types";

export interface PdfFonts { regular: string; bold: string }
type Block = { text: string; size?: number; bold?: boolean; accent?: boolean; gap?: number; before?: number; indent?: number };
const MARGIN = 36; // points, approximately 12.7 mm
const BOTTOM = 841.89 - MARGIN;

export class CVTooLongError extends Error {
  constructor() {
    super("Your CV is too long for one readable A4 page. Shorten the summary or experience bullets, save, then download again. No content has been removed.");
  }
}

function newDocument(fonts: PdfFonts) {
  const doc = new jsPDF({ unit: "pt", format: "a4", compress: true });
  doc.addFileToVFS("Vera.ttf", fonts.regular);
  doc.addFileToVFS("VeraBd.ttf", fonts.bold);
  doc.addFont("Vera.ttf", "RadarSans", "normal");
  doc.addFont("VeraBd.ttf", "RadarSans", "bold");
  return doc;
}

const dateRange = (start: string | null, end: string | null) => start ? `${start} - ${end || "present"}` : (end || "");
const join = (items: (string | null | undefined)[]) => items.filter(Boolean).join(" | ");
const section = (text: string): Block => ({ text: text.toUpperCase(), bold: true, accent: true, size: 0.9, before: 8, gap: 3 });

function header(cv: TailoredCV): Block[] {
  const c = cv.contacts;
  return [
    { text: cv.name, bold: true, size: 2.05, gap: 3 },
    ...(cv.headline ? [{ text: cv.headline, size: 1.05, accent: true, gap: 4 }] : []),
    { text: join([c.email, c.phone, c.location]), size: 0.83, gap: 2 },
    { text: join([c.linkedin, c.github, c.website]), size: 0.8, gap: 4 },
  ];
}

function cvBlocks(cv: TailoredCV): Block[] {
  const blocks = header(cv);
  if (cv.summary.trim()) blocks.push(section("Profile"), { text: cv.summary });
  if (cv.experiences.length) {
    blocks.push(section("Experience"));
    for (const x of cv.experiences) {
      blocks.push({ text: join([x.role, x.company]), bold: true, before: 3, gap: 1 });
      blocks.push({ text: join([dateRange(x.start_date, x.end_date), x.location]), size: 0.85, gap: 2 });
      for (const bullet of x.bullets.filter((b) => b.trim())) blocks.push({ text: `• ${bullet}`, indent: 7, gap: 1 });
    }
  }
  if (cv.education.length) {
    blocks.push(section("Education"));
    for (const e of cv.education) {
      blocks.push({ text: join([e.degree, e.institution]), bold: true, before: 3, gap: 1 });
      blocks.push({ text: join([dateRange(e.start_date, e.end_date), e.location]), size: 0.85, gap: 1 });
      // Courses and grades often arrive as many short entries. Wrap them together
      // instead of spending a whole line on each fact; keep every entry verbatim.
      const details = e.details.filter((d) => d.trim());
      if (details.length) blocks.push({ text: details.join(" · "), gap: 1 });
    }
  }
  if (cv.projects.length) {
    blocks.push(section("Projects"));
    for (const p of cv.projects) {
      blocks.push({ text: p.name, bold: true, before: 3, gap: 1 });
      blocks.push({ text: p.description, gap: 1 });
      if (p.tools.length) blocks.push({ text: p.tools.join(", "), size: 0.85, gap: 1 });
      if (p.url) blocks.push({ text: p.url, size: 0.8, gap: 1 });
    }
  }
  if (cv.skills.length) blocks.push(section("Skills"), { text: cv.skills.join(" · ") });
  if (cv.languages.length) blocks.push(section("Languages"), { text: cv.languages.map((l) => `${l.language} (${l.level})`).join(" · ") });
  return blocks.filter((b) => b.text.trim());
}

function layout(doc: jsPDF, blocks: Block[], bodySize: number, compact: boolean) {
  let y = MARGIN;
  const rows: { text: string; x: number; y: number; size: number; bold: boolean; accent: boolean }[] = [];
  for (const block of blocks) {
    const size = bodySize * (block.size ?? 1);
    doc.setFont("RadarSans", block.bold ? "bold" : "normal");
    doc.setFontSize(size);
    const x = MARGIN + (block.indent ?? 0);
    const lines = doc.splitTextToSize(block.text, doc.internal.pageSize.getWidth() - MARGIN - x) as string[];
    y += (block.before ?? 0) * (compact ? 0.65 : 1);
    for (const text of lines) {
      rows.push({ text, x, y: y + size, size, bold: block.bold ?? false, accent: block.accent ?? false });
      y += size * (compact ? 1.16 : 1.24);
    }
    y += (block.gap ?? 2) * (compact ? 0.65 : 1);
  }
  return { rows, bottom: y };
}

function drawRow(doc: jsPDF, row: ReturnType<typeof layout>["rows"][number], y = row.y) {
  doc.setFont("RadarSans", row.bold ? "bold" : "normal");
  doc.setFontSize(row.size);
  if (row.accent) doc.setTextColor(0, 105, 80);
  else doc.setTextColor(25, 35, 35);
  doc.text(row.text, row.x, y);
}

export function createCVPdf(cv: TailoredCV, fonts: PdfFonts) {
  const doc = newDocument(fonts);
  const blocks = cvBlocks(cv);
  // Measure before drawing. Keep every fact; never clip, omit sections or silently add pages.
  for (const compact of [false, true]) {
    for (const size of [10.5, 10.25, 10, 9.75, 9.5]) {
      const measured = layout(doc, blocks, size, compact);
      if (measured.bottom <= BOTTOM) {
        for (const row of measured.rows) drawRow(doc, row);
        doc.setProperties({ title: `${cv.name} - CV`, author: cv.name });
        return doc;
      }
    }
  }
  throw new CVTooLongError();
}

export function createCoverPdf(cv: TailoredCV, letter: string, fonts: PdfFonts) {
  const doc = newDocument(fonts);
  const blocks = [...header(cv), ...letter.split(/\n\s*\n/).map((text): Block => ({ text, before: 10, gap: 2 }))];
  const measured = layout(doc, blocks, 10.5, false);
  let offset = 0;
  for (const row of measured.rows) {
    if (row.y - offset > BOTTOM - 5) {
      doc.addPage();
      offset = row.y - MARGIN - row.size;
    }
    drawRow(doc, row, row.y - offset);
  }
  doc.setProperties({ title: `${cv.name} - Cover letter`, author: cv.name });
  return doc;
}

export function pdfFilename(name: string, company: string | null, kind: "cv" | "cover") {
  const safe = (s: string) => s.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-zA-Z0-9_-]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 70);
  return `${safe(name) || "Candidate"}_${safe(company || "Application")}_${kind === "cv" ? "CV" : "Cover_Letter"}.pdf`;
}
