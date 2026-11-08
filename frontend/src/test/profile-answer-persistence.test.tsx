import type { ReactNode } from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import fixture from "@/mocks/profile.json";
import type { ProfileOut } from "@/types";
import { DISCOVERY_QUESTIONS, readProfileAnswers } from "@/lib/profile-material";

const mocks = vi.hoisted(() => ({ updateProfile: vi.fn(), answerProfile: vi.fn() }));
vi.mock("@/api", async (original) => {
  const actual = await original<typeof import("@/api")>();
  return { ...actual, api: { ...actual.api, ...mocks } };
});
vi.mock("@tanstack/react-router", async (original) => {
  const actual = await original<typeof import("@tanstack/react-router")>();
  return { ...actual, Link: ({ children }: { children: ReactNode }) => <span>{children}</span> };
});
vi.mock("@/hooks/use-profile-query", () => ({
  useProfileQuery: () =>
    useQuery({ queryKey: ["profile"], queryFn: async () => fixture as ProfileOut, enabled: false }),
}));
import { Route } from "@/routes/profile";

function mount(data: ProfileOut) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(["profile"], data);
  const Page = Route.options.component!;
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <Page />
      </QueryClientProvider>,
    ),
  };
}

describe("Saved profile question fields", () => {
  it("keeps answered questions and discovery text visible after save and a fresh mount", async () => {
    let stored = structuredClone(fixture) as ProfileOut;
    const question = stored.profile.missing_info[0]!;
    mocks.updateProfile.mockImplementation(async (body) => {
      stored = { ...stored, ...body };
      return stored;
    });
    mocks.answerProfile.mockImplementation(async ({ answers }) => {
      stored = {
        ...stored,
        profile: { ...stored.profile, missing_info: [] },
        extra_text:
          stored.extra_text +
          "\n\n--- Answers to profile questions ---\n" +
          answers
            .map((a: { question: string; answer: string }) => `Q: ${a.question}\nA: ${a.answer}`)
            .join("\n"),
      };
      return stored;
    });
    const view = mount(stored);
    fireEvent.change(screen.getByLabelText(DISCOVERY_QUESTIONS[0]!), {
      target: { value: "Built a forecasting project" },
    });
    // The targeted question input has a visible placeholder in the existing UI.
    fireEvent.change(screen.getAllByPlaceholderText("Your answer")[0]!, {
      target: { value: "Available from June" },
    });
    fireEvent.click(screen.getAllByRole("button", { name: "Save changes" })[0]!);
    await waitFor(() => expect(mocks.answerProfile).toHaveBeenCalledOnce());
    await waitFor(() =>
      expect(screen.getByDisplayValue("Built a forecasting project")).toBeInTheDocument(),
    );
    expect(screen.getByDisplayValue("Available from June")).toBeInTheDocument();
    expect(screen.getByText(question)).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled(),
    );
    view.unmount();
    const refreshed = mount(stored);
    expect(screen.getByDisplayValue("Built a forecasting project")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Available from June")).toBeInTheDocument();
    // A different candidate must never inherit these answers.
    await act(async () => {
      refreshed.client.setQueryData(["profile"], { ...fixture, extra_text: "" });
    });
    await waitFor(() =>
      expect(screen.queryByDisplayValue("Built a forecasting project")).not.toBeInTheDocument(),
    );
  });

  it("reads only answer sections and restores the latest multiline answer", () => {
    const text =
      "--- exams.txt ---\nQ: Not a profile question\nA: Ignore\n" +
      "--- Answers to profile questions ---\nQ: Project?\nA: First\n" +
      "--- Answers to profile questions ---\nQ: Project?\nA: Updated\nSecond line\nQ: Availability?\nA: June\n" +
      "--- other.txt ---\nQ: Ignore too\nA: Ignore";
    expect(readProfileAnswers(text)).toEqual({
      "Project?": "Updated\nSecond line",
      "Availability?": "June",
    });
  });
});
