/**
 * Single data-access layer. Pages only import from here.
 * VITE_USE_MOCKS=true  -> in-browser demo store seeded from src/mocks fixtures.
 * VITE_USE_MOCKS=false -> FastAPI at VITE_API_URL (default http://localhost:8000).
 * A failed real call always surfaces as ApiError — never falls back to mocks.
 */
import type {
  ApplicationOut,
  ApplicationPatch,
  JobDetail,
  JobOut,
  ProfileOut,
  ProfileAnswers,
  ProfileUpdate,
  RadarRequest,
  RadarResponse,
  TailoredCV,
} from "./types";
import profileFixture from "./mocks/profile.json";
import jobsFixture from "./mocks/jobs.json";
import radarFixture from "./mocks/radar_response.json";
import applicationFixture from "./mocks/application.json";

export const USE_MOCKS = String(import.meta.env["VITE_USE_MOCKS"] ?? "true") !== "false";
export const API_URL = (import.meta.env["VITE_API_URL"] as string | undefined) ?? "http://localhost:8000";

export type ApiErrorKind = "not_found" | "network" | "server" | "client";
export class ApiError extends Error {
  constructor(public kind: ApiErrorKind, message: string, public status?: number) {
    super(message);
  }
}
export const isNotFound = (e: unknown) => e instanceof ApiError && e.kind === "not_found";

// ---------------------------------------------------------------- real API
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    const isForm = init?.body instanceof FormData;
    const headers = new Headers(init?.headers);
    if (!isForm) headers.set("Content-Type", "application/json");
    res = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError("network", `Can't reach the RADAR server at ${API_URL}. Is it running?`);
  }
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.error) msg = body.error;
      else if (body?.detail) msg = typeof body.detail === "string" ? body.detail : msg;
    } catch {
      /* non-JSON error body */
    }
    const kind: ApiErrorKind = res.status === 404 ? "not_found" : res.status >= 500 ? "server" : "client";
    throw new ApiError(kind, msg, res.status);
  }
  return (await res.json()) as T;
}

const real = {
  getProfile: () => request<ProfileOut>("/profile"),
  uploadProfile: (cv: File, extraFiles: File[], extraText: string) => {
    const fd = new FormData();
    fd.append("cv", cv);
    extraFiles.forEach((f) => fd.append("extra_files", f));
    fd.append("extra_text", extraText);
    return request<ProfileOut>("/profile/upload", { method: "POST", body: fd });
  },
  updateProfile: (body: ProfileUpdate) =>
    request<ProfileOut>("/profile", { method: "PUT", body: JSON.stringify(body) }),
  answerProfile: (body: ProfileAnswers) =>
    request<ProfileOut>("/profile/answers", { method: "POST", body: JSON.stringify(body) }),
  scanRadar: (body: RadarRequest) =>
    request<RadarResponse>("/radar", { method: "POST", body: JSON.stringify(body) }),
  getJob: (id: number) => request<JobDetail>(`/jobs/${id}`),
  listApplications: () => request<ApplicationOut[]>("/applications"),
  getApplication: (id: number) => request<ApplicationOut>(`/applications/${id}`),
  createApplication: (job_id: number) =>
    request<ApplicationOut>("/applications", { method: "POST", body: JSON.stringify({ job_id }) }),
  patchApplication: (id: number, patch: ApplicationPatch) =>
    request<ApplicationOut>(`/applications/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  markApplied: (id: number) => request<ApplicationOut>(`/applications/${id}/applied`, { method: "POST" }),
};

// ---------------------------------------------------------------- mock store
type MockState = {
  profile: ProfileOut | null;
  applications: ApplicationOut[];
  lastRadar: RadarResponse | null;
};
const KEY = "radar_demo_state_v1";
const clone = <T>(x: T): T => JSON.parse(JSON.stringify(x));
const seed = (withProfile: boolean): MockState => ({
  profile: withProfile ? clone(profileFixture as unknown as ProfileOut) : null,
  applications: [clone(applicationFixture as unknown as ApplicationOut)],
  lastRadar: null,
});
function load(): MockState {
  if (typeof window === "undefined") return seed(true);
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    /* ignore */
  }
  return seed(true);
}
function save(s: MockState) {
  if (typeof window !== "undefined") localStorage.setItem(KEY, JSON.stringify(s));
}
const delay = (ms = 350) => new Promise((r) => setTimeout(r, ms));
const now = () => new Date().toISOString();
const jobs = jobsFixture as unknown as JobOut[];

/** Demo-only controls for testing first-use vs populated profile. */
export const demo = {
  setProfileState(state: "empty" | "populated") {
    const s = load();
    s.profile = state === "populated" ? clone(profileFixture as unknown as ProfileOut) : null;
    save(s);
  },
  reset() {
    save(seed(true));
  },
};

function tailorFromProfile(p: ProfileOut["profile"]): TailoredCV {
  // Only facts already in the profile — nothing invented.
  return clone({
    name: p.name,
    headline: p.headline,
    contacts: p.contacts,
    summary: p.summary,
    skills: p.skills,
    experiences: p.experiences,
    education: p.education,
    projects: p.projects,
    languages: p.languages,
  });
}

const mock = {
  async getProfile(): Promise<ProfileOut> {
    await delay();
    const s = load();
    if (!s.profile) throw new ApiError("not_found", "No profile yet", 404);
    return s.profile;
  },
  async uploadProfile(_cv: File, _extra: File[], extraText: string): Promise<ProfileOut> {
    await delay(1400);
    const s = load();
    // Demo: the uploaded CV is "parsed" into the fixture profile.
    s.profile = { ...clone(profileFixture as unknown as ProfileOut), extra_text: extraText, updated_at: now() };
    save(s);
    return s.profile;
  },
  async updateProfile(body: ProfileUpdate): Promise<ProfileOut> {
    await delay();
    const s = load();
    if (!s.profile) throw new ApiError("not_found", "No profile yet", 404);
    s.profile = {
      ...s.profile,
      profile: body.profile,
      extra_text: body.extra_text ?? s.profile.extra_text,
      updated_at: now(),
    };
    save(s);
    return s.profile;
  },
  async answerProfile(body: ProfileAnswers): Promise<ProfileOut> {
    await delay(1000);
    const s = load();
    if (!s.profile) throw new ApiError("not_found", "No profile yet", 404);
    const answers = body.answers.filter((a) => a.answer.trim());
    if (!answers.length) throw new ApiError("client", "Write at least one answer", 422);
    const answered = new Set(answers.map((a) => a.question.trim().toLowerCase()));
    s.profile.profile.missing_info = s.profile.profile.missing_info.filter((q) => !answered.has(q.trim().toLowerCase()));
    const transcript = answers.map((a) => `Q: ${a.question}\nA: ${a.answer.trim()}`).join("\n");
    s.profile.extra_text = [s.profile.extra_text, `--- Answers to profile questions ---\n${transcript}`].filter(Boolean).join("\n\n");
    s.profile.updated_at = now();
    // Demo mode stores answers, but does not pretend to run AI or infer new roles.
    save(s);
    return s.profile;
  },
  async scanRadar(body: RadarRequest): Promise<RadarResponse> {
    await delay(1800);
    const s = load();
    if (!s.profile) throw new ApiError("client", "Create your profile before scanning", 400);
    const base = radarFixture as unknown as RadarResponse;
    const ref = new Date(base.generated_at).getTime();
    const windows = [3, 7, 14, 30];
    const pick = (days: number) =>
      base.results.filter((r) => {
        if (body.english_only && (r.job.language !== "en" || r.job.norwegian_required)) return false;
        if (!r.job.posted_at) return true; // date unknown: kept, labelled as such
        return ref - new Date(r.job.posted_at).getTime() <= days * 86400000;
      });
    let used: number = body.days;
    let results = pick(used);
    // Mirror backend: widen the window when too few dated results.
    while (results.filter((r) => r.job.posted_at).length < 3 && used < 30) {
      used = windows[windows.indexOf(used) + 1] ?? 30;
      results = pick(used);
    }
    const res: RadarResponse = {
      ...clone(base),
      days_requested: body.days,
      days_used: used,
      widened: used > body.days,
      results: clone(results).sort((a, b) => b.match.score - a.match.score),
      generated_at: now(),
    };
    s.lastRadar = res;
    save(s);
    return res;
  },
  async getJob(id: number): Promise<JobDetail> {
    await delay();
    const s = load();
    const job = jobs.find((j) => j.id === id);
    if (!job) throw new ApiError("not_found", "Job not found", 404);
    const match = (radarFixture as unknown as RadarResponse).results.find((r) => r.job.id === id)?.match ?? null;
    const app = s.applications.find((a) => a.job_id === id);
    return { job: clone(job), match: clone(match), application: app ? { id: app.id, status: app.status } : null };
  },
  async listApplications(): Promise<ApplicationOut[]> {
    await delay();
    return load().applications;
  },
  async getApplication(id: number): Promise<ApplicationOut> {
    await delay(200);
    const a = load().applications.find((x) => x.id === id);
    if (!a) throw new ApiError("not_found", "Application not found", 404);
    return a;
  },
  async createApplication(job_id: number): Promise<ApplicationOut> {
    await delay(1600);
    const s = load();
    if (!s.profile) throw new ApiError("client", "Create your profile first", 400);
    const existing = s.applications.find((a) => a.job_id === job_id);
    if (existing) return existing;
    const job = jobs.find((j) => j.id === job_id);
    if (!job) throw new ApiError("not_found", "Job not found", 404);
    const p = s.profile.profile;
    const match = (radarFixture as unknown as RadarResponse).results.find((r) => r.job.id === job_id)?.match;
    const app: ApplicationOut = {
      id: Math.max(0, ...s.applications.map((a) => a.id)) + 1,
      job_id,
      job: clone(job),
      status: "draft",
      language: job.language === "no" ? "no" : "en",
      cv: tailorFromProfile(p),
      cover_letter: `Dear ${job.company ?? "hiring"} team,\n\nI am applying for the ${job.title} position.\n\n${p.summary}\n\n[Demo draft — in real mode the backend writes a tailored letter using only facts from your profile. Edit freely before applying.]\n\nKind regards,\n${p.name}`,
      notes: {
        keywords_covered: p.skills.slice(0, 5),
        missing_requirements: match?.gaps ?? [],
        changes: ["Demo: CV copied from your profile without changes"],
      },
      snapshot: null,
      created_at: now(),
      applied_at: null,
    };
    s.applications.push(app);
    save(s);
    return app;
  },
  async patchApplication(id: number, patch: ApplicationPatch): Promise<ApplicationOut> {
    await delay(300);
    const s = load();
    const i = s.applications.findIndex((a) => a.id === id);
    if (i < 0) throw new ApiError("not_found", "Application not found", 404);
    const a = s.applications[i]!;
    if (patch.cv) a.cv = patch.cv;
    if (patch.cover_letter != null) a.cover_letter = patch.cover_letter;
    if (patch.status) a.status = patch.status;
    save(s);
    return a;
  },
  async markApplied(id: number): Promise<ApplicationOut> {
    await delay(500);
    const s = load();
    const a = s.applications.find((x) => x.id === id);
    if (!a) throw new ApiError("not_found", "Application not found", 404);
    const at = now();
    a.status = "applied";
    a.applied_at = at;
    a.snapshot = { job: clone(a.job), cv: clone(a.cv), cover_letter: a.cover_letter, applied_at: at };
    save(s);
    return a;
  },
};

export const api = USE_MOCKS ? mock : real;

export const qk = {
  profile: ["profile"] as const,
  job: (id: number) => ["job", id] as const,
  applications: ["applications"] as const,
  application: (id: number) => ["application", id] as const,
};
