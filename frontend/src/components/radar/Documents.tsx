import type { TailoredCV } from "@/types";

const range = (a: string | null, b: string | null) => `${a ?? ""}${a || b ? " – " : ""}${b ?? (a ? "present" : "")}`;

export function CVDocument({ cv }: { cv: TailoredCV }) {
  const c = cv.contacts;
  const contacts = [c.email, c.phone, c.location, c.linkedin, c.github, c.website].filter(Boolean);
  return (
    <article className="text-[10.5pt] leading-snug">
      <header className="border-b pb-3">
        <h1 className="text-[22pt] font-bold leading-tight">{cv.name}</h1>
        {cv.headline && <p className="mt-1 text-[11pt] text-primary">{cv.headline}</p>}
        <p className="mt-1.5 break-words text-[9pt] text-muted-foreground">{contacts.join("  ·  ")}</p>
      </header>
      {cv.summary && <Section title="Profile"><p>{cv.summary}</p></Section>}
      {cv.experiences.length > 0 && (
        <Section title="Experience">
          {cv.experiences.map((x, i) => (
            <div key={i} className="mb-2.5 break-inside-avoid">
              <div className="flex justify-between gap-4">
                <strong>{x.role} · {x.company}</strong>
                <span className="shrink-0 text-[9pt] text-muted-foreground">{range(x.start_date, x.end_date)}</span>
              </div>
              {x.location && <div className="text-[9pt] text-muted-foreground">{x.location}</div>}
              <ul className="mt-1 list-disc pl-5">{x.bullets.filter(Boolean).map((b, j) => <li key={j}>{b}</li>)}</ul>
            </div>
          ))}
        </Section>
      )}
      {cv.education.length > 0 && (
        <Section title="Education">
          {cv.education.map((e, i) => (
            <div key={i} className="mb-2 break-inside-avoid">
              <div className="flex justify-between gap-4">
                <strong>{e.degree} · {e.institution}</strong>
                <span className="shrink-0 text-[9pt] text-muted-foreground">{range(e.start_date, e.end_date)}</span>
              </div>
              {e.details.length > 0 && <ul className="list-disc pl-5">{e.details.map((d, j) => <li key={j}>{d}</li>)}</ul>}
            </div>
          ))}
        </Section>
      )}
      {cv.projects.length > 0 && (
        <Section title="Projects">
          {cv.projects.map((p, i) => (
            <div key={i} className="mb-1.5 break-inside-avoid">
              <strong>{p.name}</strong> — {p.description}
              {p.tools.length > 0 && <span className="text-muted-foreground"> ({p.tools.join(", ")})</span>}
            </div>
          ))}
        </Section>
      )}
      <div className="grid grid-cols-2 gap-6">
        {cv.skills.length > 0 && <Section title="Skills"><p>{cv.skills.join(" · ")}</p></Section>}
        {cv.languages.length > 0 && (
          <Section title="Languages"><p>{cv.languages.map((l) => `${l.language} (${l.level})`).join(" · ")}</p></Section>
        )}
      </div>
    </article>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-4">
      <h2 className="mb-1.5 text-[9pt] font-bold uppercase tracking-[0.15em] text-primary">{title}</h2>
      {children}
    </section>
  );
}

export function CoverDocument({ cv, letter }: { cv: TailoredCV; letter: string }) {
  const c = cv.contacts;
  return (
    <article className="text-[11pt] leading-relaxed">
      <header className="mb-8 border-b pb-3">
        <h1 className="text-[18pt] font-bold">{cv.name}</h1>
        <p className="text-[9pt] text-muted-foreground">{[c.email, c.phone, c.location].filter(Boolean).join("  ·  ")}</p>
      </header>
      <div className="whitespace-pre-wrap break-words">{letter}</div>
    </article>
  );
}
