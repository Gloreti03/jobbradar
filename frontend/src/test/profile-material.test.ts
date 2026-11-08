import { describe, expect, it } from "vitest";
import { mergeAttachments, splitProfileMaterial } from "@/lib/profile-material";

describe("Profile material", () => {
  it("keeps files selected in separate picker sessions and supports reselecting after removal", () => {
    const transcript = new File(["transcript"], "exams.pdf", { lastModified: 1 });
    const project = new File(["project"], "project.pdf", { lastModified: 2 });
    const selected = mergeAttachments([transcript], [project, transcript]);
    expect(selected).toEqual([transcript, project]);
    expect(
      mergeAttachments(
        selected.filter((f) => f !== transcript),
        [transcript],
      ),
    ).toEqual([project, transcript]);
  });

  it("preserves original imported text through a notes edit, including extraction corruption", () => {
    const source =
      "--- exams.pdf ---\n\u0004\u0005original\n--- project.txt ---\nProject description";
    const parts = splitProfileMaterial(`Aviation, tech\n\n${source}`);
    expect(parts.notes).toBe("Aviation, tech");
    expect(parts.documents).toBe(source);
    const afterSave = splitProfileMaterial(
      ["Automotive\n\nQ: Project?\nA: Forecasting", parts.documents].join("\n\n"),
    );
    expect(afterSave.notes).toContain("A: Forecasting");
    expect(afterSave.documents).toBe(source);
  });

  it("does not mistake ordinary notes or inline dashes for a document boundary", () => {
    const notes = "Interested in aviation --- especially planning --- and analytics.";
    expect(splitProfileMaterial(notes)).toEqual({ notes, documents: "" });
  });
});
