import { describe, expect, it, vi } from "vitest";
import sample from "@/mocks/profile.json";
import type { ProfileAnswers, ProfileOut, ProfileUpdate } from "@/types";
import { saveProfileWithAnswers } from "@/lib/save-profile";
import { DISCOVERY_QUESTIONS } from "@/lib/profile-material";

describe("Profile answer integration", () => {
  it("saves manual edits before applying answers and displays the updated backend profile", async () => {
    const original = structuredClone(sample) as ProfileOut;
    const profile = { ...original.profile, headline: "My edited headline" };
    const steps: string[] = [];
    const updated = { ...original, profile: { ...profile, search_terms: ["operations analyst"] } };
    const client = {
      updateProfile: vi.fn(async (body: ProfileUpdate) => {
        steps.push("save");
        expect(body.profile.headline).toBe("My edited headline");
        expect(body.profile.missing_info).toContain(profile.missing_info[0]);
        expect(body.profile.missing_info).toContain(DISCOVERY_QUESTIONS[0]);
        expect(body.extra_text).toBe("Personal notes and imported documents");
        return { ...original, profile: body.profile };
      }),
      answerProfile: vi.fn(async (body: ProfileAnswers) => {
        steps.push("answers");
        expect(body.answers).toEqual([
          { question: profile.missing_info[0], answer: "EU citizen" },
          {
            question: DISCOVERY_QUESTIONS[0],
            answer: "I enjoyed optimising the supply chain project",
          },
        ]);
        return updated;
      }),
    };
    const result = await saveProfileWithAnswers(
      client,
      profile,
      "Personal notes and imported documents",
      { 0: " EU citizen " },
      { 0: "I enjoyed optimising the supply chain project" },
    );
    expect(steps).toEqual(["save", "answers"]);
    expect(result).toBe(updated);
    expect(original.profile.headline).not.toBe(profile.headline);
  });

  it("does not invoke AI when the user only edits their profile", async () => {
    const current = structuredClone(sample) as ProfileOut;
    const client = { updateProfile: vi.fn(async () => current), answerProfile: vi.fn() };
    expect(await saveProfileWithAnswers(client, current.profile, "Notes", {}, {})).toBe(current);
    expect(client.answerProfile).not.toHaveBeenCalled();
  });

  it("does not submit answers when saving manual changes fails", async () => {
    const current = structuredClone(sample) as ProfileOut;
    const answers = { 0: "Full time" };
    const client = {
      updateProfile: vi.fn(async () => {
        throw new Error("Offline");
      }),
      answerProfile: vi.fn(),
    };
    await expect(
      saveProfileWithAnswers(client, current.profile, "Notes", answers, {}),
    ).rejects.toThrow("Offline");
    expect(client.answerProfile).not.toHaveBeenCalled();
    expect(answers[0]).toBe("Full time");
  });

  it("surfaces a failed AI update without clearing the user's answers", async () => {
    const current = structuredClone(sample) as ProfileOut;
    const answers = { 0: "Full time" };
    const client = {
      updateProfile: vi.fn(async () => current),
      answerProfile: vi.fn(async () => {
        throw new Error("Please retry");
      }),
    };
    await expect(
      saveProfileWithAnswers(client, current.profile, "Notes", answers, {}),
    ).rejects.toThrow("Please retry");
    expect(answers[0]).toBe("Full time");
  });
});
