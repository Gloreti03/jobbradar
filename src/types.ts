// Mirrors backend schemas.py exactly (snake_case). Do not rename fields.

export type JobSource = "nav" | "teamtailor" | "greenhouse" | "lever" | "ashby" | "extension" | "fixture";
export type JobStatus = "active" | "inactive";
export type JobLanguage = "no" | "en";
export type Verdict = "strong" | "good" | "stretch" | "poor";
export type ApplicationStatus = "draft" | "applied" | "interviewing" | "rejected" | "offer";
export type DocLanguage = "en" | "no";

export interface Contacts {
  email: string | null;
  phone: string | null;
  location: string | null;
  linkedin: string | null;
  github: string | null;
  website: string | null;
}
export interface LanguageSkill { language: string; level: string }
export interface Experience {
  role: string;
  company: string;
  location: string | null;
  start_date: string | null;
  end_date: string | null;
  bullets: string[];
}
export interface Education {
  degree: string;
  institution: string;
  location: string | null;
  start_date: string | null;
  end_date: string | null;
  details: string[];
}
export interface Project { name: string; description: string; tools: string[]; url: string | null }
export interface Preferences {
  roles: string[];
  cities: string[];
  seniority: string | null;
  work_modes: string[];
  industries?: string[];
}
export interface Profile {
  name: string;
  headline: string;
  contacts: Contacts;
  summary: string;
  skills: string[];
  tools: string[];
  languages: LanguageSkill[];
  experiences: Experience[];
  education: Education[];
  projects: Project[];
  preferences: Preferences;
  search_terms: string[];
  missing_info: string[];
}
export interface ProfileOut { id: number; profile: Profile; extra_text: string; updated_at: string; warnings?: string[]; reset?: boolean }
export interface ProfileUpdate { profile: Profile; extra_text?: string | null }
export interface MissingInfoAnswer { question: string; answer: string }
export interface ProfileAnswers { answers: MissingInfoAnswer[] }

export interface JobOut {
  id: number;
  source: JobSource;
  source_id: string;
  title: string;
  company: string | null;
  location: string | null;
  description: string | null;
  url: string;
  apply_url: string | null;
  posted_at: string | null; // null = "Date unknown" — never substitute discovered_at
  expires_at: string | null;
  discovered_at: string;
  status: JobStatus;
  language: JobLanguage | null;
  norwegian_required: boolean | null;
}
export interface MatchOut {
  score: number;
  verdict: Verdict;
  reasons: string[];
  gaps: string[];
  to_clarify: string[];
}
export interface RadarRequest { days: 3 | 7 | 14 | 30; english_only: boolean; refresh: boolean }
export interface RadarResult { job: JobOut; match: MatchOut }
export interface RadarFunnel {
  total: number;
  recent: number;
  location: number;
  language: number;
  keywords: number;
  deduplicated: number;
  live: number;
  ranked: number;
}
export interface RadarResponse {
  days_requested: number;
  days_used: number;
  widened: boolean;
  scanned_count: number;
  candidates_count: number;
  results: RadarResult[];
  generated_at: string;
  funnel?: RadarFunnel | null;
}
export interface ApplicationRef { id: number; status: ApplicationStatus }
export interface JobDetail { job: JobOut; match: MatchOut | null; application: ApplicationRef | null }

export interface TailoredCV {
  name: string;
  headline: string;
  contacts: Contacts;
  summary: string;
  skills: string[];
  experiences: Experience[];
  education: Education[];
  projects: Project[];
  languages: LanguageSkill[];
}
export interface RequirementMatch {
  requirement: string;
  importance: "required" | "nice_to_have";
  status: "met" | "partial" | "missing";
  evidence: string[];
}
export interface ApplicationNotes {
  keywords_covered: string[];
  missing_requirements: string[];
  changes: string[];
  requirement_map?: RequirementMatch[];
}
export interface Snapshot { job: JobOut; cv: TailoredCV; cover_letter: string; applied_at: string }
export interface ApplicationPatch {
  cv?: TailoredCV | null;
  cover_letter?: string | null;
  status?: ApplicationStatus | null;
}
export interface ApplicationOut {
  id: number;
  job_id: number;
  job: JobOut;
  status: ApplicationStatus;
  language: DocLanguage;
  cv: TailoredCV;
  cover_letter: string;
  notes: ApplicationNotes;
  snapshot: Snapshot | null;
  created_at: string;
  applied_at: string | null;
}

export const APPLICATION_STATUSES: ApplicationStatus[] = ["draft", "applied", "interviewing", "rejected", "offer"];

// ---------------------------------------------------------------- D — Mock interview (Matilde)
export type InterviewMode = "text" | "voice";
export type QuestionKind = "intro" | "behavioral" | "technical" | "motivation" | "gap";
export interface InterviewQuestion { id: number; kind: QuestionKind; question: string; focus: string }
export interface TranscriptTurn { role: "interviewer" | "candidate"; content: string; question_id: number | null }
export interface QuestionFeedback {
  question_id: number;
  question: string;
  score: number; // 1..5
  comment: string;
  better_answer: string; // only true facts from the CV / answers
}
export interface InterviewFeedback {
  overall_score: number; // 0..100
  summary: string;
  strengths: string[];
  improvements: string[];
  questions: QuestionFeedback[];
}
export interface InterviewStartResponse {
  interview_id: number;
  application_id: number;
  mode: InterviewMode;
  plan: InterviewQuestion[]; // 6 questions
  message: string; // interviewer's first message
  question_index: number; // 0-based
}
export interface InterviewTurnResponse {
  interview_id: number;
  message: string; // next question, or the closing message
  question_index: number;
  done: boolean; // true after the 6th answer -> ask for feedback
}
export interface InterviewOut {
  id: number;
  application_id: number;
  mode: InterviewMode;
  plan: InterviewQuestion[];
  transcript: TranscriptTurn[];
  feedback: InterviewFeedback | null;
}
export interface SignedUrlResponse { signed_url: string }
/** One message of the ElevenLabs voice call (body of POST /interview/{id}/voice-transcript). */
export interface VoiceTurn { role: "interviewer" | "candidate"; content: string }
