import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import application from "@/mocks/application.json";
import type { TailoredCV } from "@/types";
import { createCVPdf, createCoverPdf, CVTooLongError, pdfFilename } from "@/lib/document-pdf";

const fonts = {
  regular: readFileSync(resolve("src/assets/fonts/Vera.ttf")).toString("base64"),
  bold: readFileSync(resolve("src/assets/fonts/VeraBd.ttf")).toString("base64"),
};
const cv = application.cv as TailoredCV;
const qaDir = process.env["RADAR_PDF_QA_DIR"];

describe("Downloadable documents", () => {
  it("fits the complete example CV on exactly one A4 page", () => {
    const doc = createCVPdf(cv, fonts);
    expect(doc.getNumberOfPages()).toBe(1);
    expect(doc.internal.pageSize.getWidth()).toBeCloseTo(595.28, 1);
    expect(doc.internal.pageSize.getHeight()).toBeCloseTo(841.89, 1);
    if (qaDir)
      writeFileSync(resolve(qaDir, "fixture-cv.pdf"), new Uint8Array(doc.output("arraybuffer")));
  });

  it("requires editing an oversized CV instead of clipping it or adding a second page", () => {
    const tooLong = structuredClone(cv);
    tooLong.summary = "A detailed description of an extensive professional career. ".repeat(500);
    expect(() => createCVPdf(tooLong, fonts)).toThrow(CVTooLongError);
    expect(tooLong.summary).toContain("professional career");
  });

  it("fits many short course and grade entries without changing the CV", () => {
    const courseHeavy = structuredClone(cv);
    courseHeavy.education[0]!.details = Array.from(
      { length: 30 },
      (_, i) => `Course ${i + 1} (30/30)`,
    );
    const before = JSON.stringify(courseHeavy);
    expect(createCVPdf(courseHeavy, fonts).getNumberOfPages()).toBe(1);
    expect(JSON.stringify(courseHeavy)).toBe(before);
  });

  it("creates a downloadable PDF cover letter", () => {
    const doc = createCoverPdf(cv, application.cover_letter, fonts);
    expect(doc.getNumberOfPages()).toBe(1);
    expect(doc.output().startsWith("%PDF-")).toBe(true);
    if (qaDir)
      writeFileSync(resolve(qaDir, "fixture-cover.pdf"), new Uint8Array(doc.output("arraybuffer")));
  });

  it("produces safe, descriptive filenames", () => {
    expect(pdfFilename("André / Test", "Øslo: Company", "cv")).toBe(
      "Andre_Test_slo_Company_CV.pdf",
    );
    expect(pdfFilename("", null, "cover")).toBe("Candidate_Application_Cover_Letter.pdf");
  });

  if (qaDir && existsSync(resolve(qaDir, "application.json"))) {
    it("fits the latest local application CV on one page without changing the source data", () => {
      const actual = JSON.parse(readFileSync(resolve(qaDir, "application.json"), "utf8"));
      const before = JSON.stringify(actual.cv);
      const doc = createCVPdf(actual.cv, fonts);
      expect(doc.getNumberOfPages()).toBe(1);
      expect(JSON.stringify(actual.cv)).toBe(before);
      writeFileSync(resolve(qaDir, "actual-cv.pdf"), new Uint8Array(doc.output("arraybuffer")));
      const cover = createCoverPdf(actual.cv, actual.cover_letter, fonts);
      writeFileSync(
        resolve(qaDir, "actual-cover.pdf"),
        new Uint8Array(cover.output("arraybuffer")),
      );
    });
  }
});
