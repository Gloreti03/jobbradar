import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import type { ApplicationOut } from "@/types";
import fixture from "@/mocks/application.json";
import interview from "@/mocks/interview.json";

const mocks = vi.hoisted(() => ({
  startSession: vi.fn(), endSession: vi.fn(), getVoiceSignedUrl: vi.fn(), startInterview: vi.fn(),
  setMuted: vi.fn(), saveVoiceTranscript: vi.fn(), interviewFeedback: vi.fn(),
  muted: true, speaking: false,
  onMutedChange: undefined as undefined | ((muted: boolean) => void),
  callbacks: {} as { onMessage?: (value: { message: string; source: string }) => void; onDisconnect?: () => void },
}));
vi.mock("@elevenlabs/react", () => ({
  ConversationProvider: ({ children, isMuted, onMutedChange }: { children: ReactNode; isMuted: boolean; onMutedChange: (value: boolean) => void }) => {
    mocks.muted = isMuted;
    mocks.onMutedChange = onMutedChange;
    return children;
  },
  useConversation: (options: typeof mocks.callbacks) => {
    mocks.callbacks = options;
    return { startSession: mocks.startSession, endSession: mocks.endSession, isSpeaking: mocks.speaking, isMuted: mocks.muted,
      setMuted: (value: boolean) => { mocks.setMuted(value); mocks.onMutedChange?.(value); } };
  },
}));
vi.mock("@/api", () => ({ api: { getVoiceSignedUrl: mocks.getVoiceSignedUrl, startInterview: mocks.startInterview,
  saveVoiceTranscript: mocks.saveVoiceTranscript, interviewFeedback: mocks.interviewFeedback } }));
import VoiceInterview from "@/components/radar/VoiceInterview";

const originalMedia = Object.getOwnPropertyDescriptor(navigator, "mediaDevices");
const originalScroll = HTMLElement.prototype.scrollIntoView;
const media = vi.fn();

beforeEach(() => {
  vi.resetAllMocks();
  mocks.muted = true;
  mocks.speaking = false;
  vi.stubGlobal("SpeechRecognition", undefined);
  vi.stubGlobal("webkitSpeechRecognition", undefined);
  Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia: media } });
  HTMLElement.prototype.scrollIntoView = vi.fn();
});
afterEach(() => {
  cleanup();
  if (originalMedia) Object.defineProperty(navigator, "mediaDevices", originalMedia);
  else Reflect.deleteProperty(navigator, "mediaDevices");
  HTMLElement.prototype.scrollIntoView = originalScroll;
  vi.unstubAllGlobals();
});

async function connect(props = { app: fixture as ApplicationOut, onUseText: vi.fn(), onFeedback: vi.fn() }) {
  media.mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] });
  mocks.getVoiceSignedUrl.mockResolvedValue({ signed_url: "wss://example.invalid/test" });
  mocks.startInterview.mockResolvedValue({ message: "First question", plan: interview.plan });
  mocks.startSession.mockResolvedValue("test-call");
  const view = render(<VoiceInterview {...props} />);
  fireEvent.click(screen.getByRole("button", { name: "Start voice interview" }));
  await screen.findByRole("button", { name: "Start answer" });
  return { ...view, props };
}

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

  it("starts muted, prevents talking over the agent and works without browser captions", async () => {
    mocks.speaking = true;
    const { rerender, props } = await connect();
    expect(mocks.setMuted).toHaveBeenLastCalledWith(true);
    expect(screen.getByRole("button", { name: "Start answer" })).toBeDisabled();
    mocks.speaking = false;
    rerender(<VoiceInterview {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Start answer" }));
    expect(mocks.setMuted).toHaveBeenLastCalledWith(false);
    fireEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(mocks.setMuted).toHaveBeenLastCalledWith(true);
    expect(screen.queryByRole("status", { name: "Your live captions" })).not.toBeInTheDocument();
  });

  it("removes agent emotion tags from the screen and saved transcript while preserving user text", async () => {
    await connect();
    act(() => mocks.callbacks.onMessage?.({ message: "[thoughtful] [warm, friendly] First question", source: "ai" }));
    act(() => mocks.callbacks.onMessage?.({ message: "[my note] I used Python", source: "user" }));
    expect(screen.getByText("First question")).toBeInTheDocument();
    expect(screen.queryByText(/thoughtful/)).not.toBeInTheDocument();
    expect(screen.getByText("[my note] I used Python")).toBeInTheDocument();
    mocks.saveVoiceTranscript.mockResolvedValue(interview);
    mocks.interviewFeedback.mockResolvedValue(interview.feedback);
    fireEvent.click(screen.getByRole("button", { name: "End interview" }));
    fireEvent.click(screen.getByRole("button", { name: "Get my feedback" }));
    await waitFor(() => expect(mocks.saveVoiceTranscript).toHaveBeenCalledWith(fixture.id, [
      { role: "interviewer", content: "First question" }, { role: "candidate", content: "[my note] I used Python" },
    ]));
  });

  it("shows provisional Chrome captions but only saves the final ElevenLabs messages", async () => {
    const recognizers: FakeRecognition[] = [];
    class FakeRecognition {
      lang = ""; continuous = false; interimResults = false;
      onresult: ((event: { results: { transcript: string }[][] }) => void) | null = null;
      onerror: (() => void) | null = null;
      onend: (() => void) | null = null;
      start = vi.fn(); stop = vi.fn();
      constructor() { recognizers.push(this); }
    }
    vi.stubGlobal("webkitSpeechRecognition", FakeRecognition);
    await connect();
    fireEvent.click(screen.getByRole("button", { name: "Start answer" }));
    const rec = recognizers[0]!;
    expect(rec.lang).toBe("en-US");
    expect(rec.start).toHaveBeenCalledOnce();
    act(() => rec.onresult?.({ results: [[{ transcript: "Temporary browser words" }]] }));
    expect(screen.getByRole("status", { name: "Your live captions" })).toHaveTextContent("Temporary browser words");
    fireEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(rec.stop).toHaveBeenCalledOnce();
    act(() => mocks.callbacks.onMessage?.({ message: "Official ElevenLabs answer", source: "user" }));
    expect(screen.queryByText("Temporary browser words")).not.toBeInTheDocument();
    expect(screen.getByText("Official ElevenLabs answer")).toBeInTheDocument();
    mocks.saveVoiceTranscript.mockResolvedValue(interview);
    mocks.interviewFeedback.mockResolvedValue(interview.feedback);
    fireEvent.click(screen.getByRole("button", { name: "End interview" }));
    fireEvent.click(screen.getByRole("button", { name: "Get my feedback" }));
    await waitFor(() => expect(mocks.saveVoiceTranscript).toHaveBeenCalledWith(fixture.id, [
      { role: "candidate", content: "Official ElevenLabs answer" },
    ]));
  });
});
