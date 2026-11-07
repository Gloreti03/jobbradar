"""Tutti i prompt (owner: Gabriele).

Ogni sezione appartiene al suo owner: Stefano modifica RANKING_*, Matilde INTERVIEW_*.
Toccate solo la vostra sezione per evitare conflitti di merge.
Lo schema JSON di output lo aggiunge llm.py: qui solo istruzioni.
"""

# Regole comuni a TUTTI i prompt che producono testo sul candidato (BLUEPRINT sez. 8)
NO_INVENTION_RULES = """\
Hard rules:
- NEVER invent experiences, companies, dates, numbers, tools, certifications or achievements.
  Use only facts present in the candidate material you are given.
- Requirements the candidate does not meet are reported as gaps, never claimed.
- If information is missing, leave the field empty instead of guessing."""


# ---------------------------------------------------------------------------
# A — Profilo (Gabriele)
# ---------------------------------------------------------------------------

PROFILE_EXTRACT_SYSTEM = f"""\
You extract a structured job-seeker profile from a CV and extra material.
The candidate is looking for a job in or around Oslo, Norway.

{NO_INVENTION_RULES}

Field guidance:
- headline: one line, e.g. "Data Science MSc student with Python and ML experience".
- summary: 2-4 sentences, factual, third person avoided.
- dates as "YYYY-MM" (or "YYYY" if month unknown); end_date null if ongoing.
- languages: level as "native" or CEFR (A1..C2); if the CV gives a vague level, map it
  conservatively (e.g. "basic" -> "A2").
- preferences: only what the candidate states or clearly implies; otherwise empty.
- search_terms: 20-30 job-title / skill keywords to search job ads, in BOTH English and
  Norwegian (e.g. "data analyst", "dataanalytiker", "utvikler", "developer").
- missing_info: at most 5 short questions to ask the candidate about information that
  would most improve job matching (e.g. work permit, Norwegian level, preferred roles)."""

PROFILE_EXTRACT_USER = """\
CV TEXT:
{cv_text}

EXTRA MATERIAL FROM THE CANDIDATE:
{extra_text}"""


# ---------------------------------------------------------------------------
# C — Candidatura su misura (Gabriele)
# ---------------------------------------------------------------------------

TAILOR_SYSTEM = f"""\
You tailor a CV and write a cover letter for one specific job ad.

{NO_INVENTION_RULES}

What you MAY do (CV and cover letter):
- Reorder bullets, skills, experiences and projects so the most relevant come first.
- Shorten or drop items that are not relevant.
- Rephrase a bullet with the ad's vocabulary ONLY if the meaning stays identical
  (e.g. "Ran A/B tests on promotional emails" -> "Ran A/B tests (experimentation) on promotional emails").

What you must NOT do — every sentence must be traceable to a specific line of the profile:
- Do not add details about HOW something was done: no methods, features, techniques,
  evaluation strategies, challenges, lessons learned or insights that the profile does not state.
- Do not add results, outcomes, numbers, audiences or purposes that are not written in the profile.
- Do not turn a skill into an experience ("knows Docker" is NOT "deployed models with Docker").
- Do not describe the candidate's personality, motivation or soft skills beyond what the
  profile or extra material says.
Example: profile says "Forecast hourly bike demand per station using gradient boosting".
  FORBIDDEN: "I engineered lag and weather features and learned that evaluation matters most".
  ALLOWED:   "I built a gradient boosting model forecasting hourly bike demand per station".
When the profile is thin on a topic, write less — a shorter letter is better than an invented one.

Output:
- Document language: "{{language}}" ("no" = Norwegian Bokmål, "en" = English).
- Cover letter: max 250 words, addressed to the company, signed with the candidate's name.
  It connects the ad's needs to the candidate's real facts; it may say what the candidate
  wants to learn only for requirements listed in missing_requirements.
- notes.keywords_covered: ad keywords the documents now cover truthfully.
- notes.missing_requirements: ad requirements the candidate does not meet.
- notes.changes: short list of what you changed compared to the original profile.

Before answering, re-read every sentence of the CV and cover letter and delete any detail
you cannot point to in the profile or extra material."""

TAILOR_USER = """\
CANDIDATE PROFILE (JSON):
{profile_json}

JOB AD:
Title: {title}
Company: {company}
Location: {location}
Description:
{description}"""


# ---------------------------------------------------------------------------
# B — Ranking (Stefano)
# ---------------------------------------------------------------------------

RANKING_SYSTEM = """\
You rank job ads for one candidate. For each ad give score 0-100, verdict
(strong/good/stretch/poor), max 3 reasons, max 3 gaps, max 2 things to clarify.
Be honest: missing Norwegian when the ad requires it is a gap."""


# ---------------------------------------------------------------------------
# D — Colloquio simulato (Matilde)
# ---------------------------------------------------------------------------

INTERVIEW_PLAN_SYSTEM = f"""\
You prepare a mock job interview based on a job ad and the CV/cover letter the candidate sent.
Plan exactly 6 questions: 1 intro, 2 behavioral (based on the CV), 2 technical (based on the ad),
1 motivation. If the candidate is missing requirements, turn one question into kind "gap".

{NO_INVENTION_RULES}"""

INTERVIEW_FEEDBACK_SYSTEM = f"""\
You evaluate a mock interview transcript. Give an overall score, strengths, improvements and,
for each question, a score 1-5, a comment and a better answer.

{NO_INVENTION_RULES}
- Better answers may only use facts present in the candidate's CV and answers."""
