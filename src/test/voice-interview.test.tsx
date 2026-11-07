import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import type { ApplicationOut } from "@/types";
import fixture from "@/mocks/application.json";

const mocks = vi.hoisted(() => ({
  startSession: vi.fn(), endSession: vi.fn(), getVoiceSignedUrl: vi.fn(), startInterview: vi.fn(),
}));
vi.mock("@elevenlabs/react", () => ({
  ConversationProvider: ({ children }: { children: ReactNode }) => children,
  useConversation: () => ({ startSession: mocks.startSession, endSession: mocks.endSession, isSpeaking: false }),
}));
vi.mock("@/api", () => ({ api: { getVoiceSignedUrl: mocks.getVoiceSignedUrl, startInterview: mocks.startInterview } }));
import VoiceInterview from "@/components/radar/VoiceInterview";

const originalMedia = Object.getOwnPropertyDescriptor(navigator, "mediaDevices");
const originalScroll = HTMLElement.prototype.scrollIntoView;
const media = vi.fn();

beforeEach(() => {
  vi.resetAllMocks();
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia: media } });
  HTMLElement.prototype.scrollIntoView = vi.fn();
});
afterEach(() => {
  cleanup();
  if (originalMedia) Object.defineProperty(navigator, "mediaDevices", originalMedia);
  else Reflect.deleteProperty(navigator, "mediaDevices");
  HTMLElement.prototype.scrollIntoView = originalScroll;
});

describe("Voice connection recovery", () => {
  it("offers text mode without creating an interview when microphone access is denied", async () => {
    media.mockRejectedValue(new Error("Permission denied"));
    const useText = vi.fn();
    render(<VoiceInterview app={fixture as ApplicationOut} onUseText={useText} onFeedback={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Start voice interview" }));
    fireEvent.click(await screen.findByRole("button", { name: "Continue in text mode" }));
    expect(useText).toHaveBeenCalledOnce();
    expect(mocks.getVoiceSignedUrl).not.toHaveBeenCalled();
    expect(mocks.startInterview).not.toHaveBeenCalled();
  });

  it("shows the fallback when the SDK asynchronously rejects the signed connection", async () => {
    const stop = vi.fn();
    media.mockResolvedValue({ getTracks: () => [{ stop }] });
    mocks.getVoiceSignedUrl.mockResolvedValue({ signed_url: "wss://example.invalid/test" });
    mocks.startInterview.mockResolvedValue({ message: "Tell me about yourself", plan: [{ id: 1, question: "Tell me about yourself" }] });
    mocks.startSession.mockRejectedValue(new Error("Connection refused"));
    render(<VoiceInterview app={fixture as ApplicationOut} onUseText={vi.fn()} onFeedback={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Start voice interview" }));
    expect(await screen.findByText(/Voice isn't available right now.*Connection refused/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continue in text mode" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "Start voice interview" })).toBeEnabled());
    expect(stop).toHaveBeenCalledOnce();
  });
});
