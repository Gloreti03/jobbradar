# RADAR — Blueprint di progetto (hackathon Oslo, 7–8 nov 2026)

> Questo file va nella root di entrambi i repo. Ognuno dei 4 lo dà a Claude Code come contesto.
> Descrive **cosa costruiamo, come è organizzato e chi fa cosa**. Il codice lo scrivono Claude Code e Lovable (frontend) seguendo questo file.
> Regola d'oro: prima il percorso completo A → B → C → D funzionante, poi le rifiniture.

**Team:** Gabriele (fondamenta + profilo + CV) · Stefano (Radar) · Andrea (frontend) · Matilde (estensione + colloquio)

---

## 0. Stasera (venerdì): studio e preparazione

Tutti: leggere questo file per intero, controllare il regolamento dell'hackathon (se vieta codice scritto prima dell'inizio, stasera **niente codice**, solo account e prove), avere Python 3.11+, Node 20+, Git, VS Code con Claude Code.

| Chi | Stasera |
|---|---|
| **Gabriele** | Crea su GitHub il repo `radar` e invita tutti; crea la API key DeepSeek (platform.deepseek.com) e la condivide in privato |
| **Stefano** | Apre nel browser `https://pam-stilling-feed.nav.no/api/publicToken` e verifica che restituisca un token; legge la documentazione del feed NAV; prepara una lista di 15–20 aziende di Oslo con la loro pagina carriere (e su che sistema sono: Teamtailor, Greenhouse, Lever, Ashby) |
| **Andrea** | Account Lovable; fa una prova di progetto collegato a GitHub; studia le sezioni 4, 6 e 9 |
| **Matilde** | Account ElevenLabs e un Agent di prova; in Opera attiva `opera://extensions` → Developer mode; studia le sezioni 6, 9 e la parte colloquio |

---

## 1. Il prodotto in 5 righe

Webapp + estensione browser (Opera/Chromium) per chi cerca lavoro a Oslo.
**A** l'utente carica CV e materiale su di sé → **B** preme *Radar* e riceve gli annunci aperti di recente più adatti a lui, con motivi e lacune → **C** sceglie un annuncio e l'app prepara CV e cover letter su misura, che l'utente invia da solo sul sito dell'azienda → **D** l'annuncio viene segnato come "candidato" e si sblocca un colloquio simulato basato su quell'annuncio e sui documenti inviati.

Fuori scope: login, invio automatico delle candidature, app mobile, scraping di LinkedIn e Finn.no.

---

## 2. Stack

| Parte | Tecnologia |
|---|---|
| Backend + database | **Python 3.11+**, **FastAPI**, **SQLAlchemy 2** + **Pydantic**, **SQLite** (`backend/radar.db`), avvio con `uvicorn` sulla porta **8000** |
| AI | **DeepSeek API** (compatibile OpenAI) con SDK Python `openai` e `base_url=https://api.deepseek.com`. Variabili in `.env`: `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `MODEL_SMART=deepseek-v4-pro` (profilo, CV, colloquio), `MODEL_FAST=deepseek-flash` (ranking, import). Output sempre in JSON (`response_format={"type": "json_object"}`) validato da Pydantic |
| Frontend | **Lovable** (plausibilmente): genera React + Vite + Tailwind in TypeScript, collegato a un repo GitHub. Si sviluppa in locale sulla porta **5173**, rifiniture con Claude Code |
| Estensione | JavaScript, Manifest V3 (funziona su Opera e Chrome) |
| Voce (bonus) | ElevenLabs Agents: SDK React nel frontend, URL firmato generato dal backend |
| PDF | Pagina HTML di stampa nel frontend → "Salva come PDF" |
| Segreti | `backend/.env` (mai nel frontend, mai su GitHub) |

Un solo utente demo, nessuna autenticazione. **La demo gira in locale su un solo laptop** (backend + frontend + estensione).

**Note Lovable (importanti)**
- Lovable crea **un suo repo** GitHub: il frontend vive quindi in un secondo repo, `radar-frontend`. Il repo `radar` contiene backend, estensione e `fixtures/`.
- Lovable **non** deve creare backend o database propri (niente Supabase di Lovable): parla solo con il nostro FastAPI.
- L'anteprima online di Lovable non riesce a chiamare il backend sul vostro computer: per collegare il backend vero si clona `radar-frontend` e lo si avvia in locale (`npm run dev`). Con i mock l'anteprima di Lovable funziona.

---

## 3. Architettura

```
 Estensione ──POST /jobs/import──┐
                                 ▼
 Frontend (Lovable, :5173) ◀── JSON ──▶ Backend FastAPI (:8000) ──▶ SQLite (radar.db)
 (pagine A-B-C-D)                        │        │
                                         │        ├──▶ DeepSeek API (profilo, ranking, CV, colloquio)
                                         │        └──▶ ElevenLabs (URL firmato per la voce)
                                         ▼
                               Radar: scanner a provider
                               NAV · Teamtailor · Greenhouse · Lever · Ashby
```

**Flusso:** CV PDF → profilo strutturato (JSON) → Radar (scansione senza AI → filtri → ranking AI sui migliori ~40) → candidatura su misura → "I applied" (si salva una **fotografia** di annuncio + documenti inviati) → colloquio simulato → feedback.

---

## 4. Struttura dei repo

```
radar/                          (repo 1: backend + estensione)
├─ BLUEPRINT.md
├─ fixtures/                    DATI FINTI CONDIVISI (sezione 9) — formato ufficiale delle API
│  ├─ profile.json
│  ├─ jobs.json
│  ├─ radar_response.json
│  ├─ application.json
│  └─ interview.json
├─ backend/
│  ├─ .env                      chiavi (non committare) — .env.example sì
│  ├─ requirements.txt
│  ├─ main.py                   app FastAPI, CORS (localhost:5173 + estensione), include i router
│  ├─ db.py                     engine SQLite, sessione, creazione tabelle
│  ├─ models.py                 tabelle (sezione 5)
│  ├─ schemas.py                modelli Pydantic di richieste/risposte = CONTRATTO
│  ├─ llm.py                    unico punto di accesso a DeepSeek (JSON strutturato)
│  ├─ prompts.py                tutti i prompt
│  ├─ routers/
│  │  ├─ profile.py             A                       (Gabriele)
│  │  ├─ applications.py        C                       (Gabriele)
│  │  ├─ radar.py               B                       (Stefano)
│  │  ├─ jobs.py                B: dettaglio annuncio   (Stefano)
│  │  ├─ imports.py             import dall'estensione  (Matilde)
│  │  ├─ tracking.py            "I applied" + snapshot  (Matilde)
│  │  ├─ interview.py           D                       (Matilde)
│  │  └─ voice.py               D: URL firmato          (Matilde)
│  ├─ radar/
│  │  ├─ scanner.py             orchestratore: chiama i provider, normalizza, deduplica, salva
│  │  ├─ filters.py             recenti, località, parole chiave, lingua
│  │  ├─ ranking.py             ranking AI sui candidati filtrati
│  │  ├─ liveness.py            controlla che l'annuncio sia ancora aperto
│  │  ├─ companies.yml          aziende di Oslo da seguire + fonte di ciascuna
│  │  └─ providers/
│  │     ├─ base.py             il "contratto" di un provider
│  │     ├─ nav.py              feed ufficiale NAV
│  │     ├─ teamtailor.py       feed RSS pubblici
│  │     ├─ greenhouse.py
│  │     ├─ lever.py
│  │     └─ ashby.py
│  ├─ services/
│  │  ├─ profile_extract.py     CV PDF → profilo                     (Gabriele)
│  │  ├─ tailor.py              profilo + annuncio → CV + lettera    (Gabriele)
│  │  └─ interview.py           piano domande, turni, feedback       (Matilde)
│  ├─ scripts/
│  │  └─ scan.py                scansione da terminale; --dump salva il seed, --load-seed lo carica
│  └─ data/
│     └─ seed_jobs.json         annunci reali salvati (committato: serve a tutti)
└─ extension/
   ├─ manifest.json
   ├─ popup.html
   └─ popup.js

radar-frontend/                 (repo 2: creato da Lovable)
├─ BLUEPRINT.md                 copia di questo file
├─ .env                         VITE_API_URL=http://localhost:8000 · VITE_USE_MOCKS=true|false
└─ src/
   ├─ api.ts                    tutte le chiamate al backend + interruttore mock/reale
   ├─ mocks/                    copia dei JSON di radar/fixtures/
   ├─ App.tsx                   router + barra di navigazione
   ├─ pages/  Profile · Radar · Job · Applications · ApplicationEditor
   │          PrintCV · PrintCover · Interview
   └─ components/  JobCard · RadarButton · VoiceInterview · Feedback
```

Lovable non vede file fuori dal suo repo: i JSON di `fixtures/` vanno **copiati** in `src/mocks/`. Se Gabriele cambia una fixture, avvisa e si ricopia.

---

## 5. Modello dati (SQLite)

Tutti i campi JSON e delle API sono in **snake_case**.

| Tabella | Campi principali |
|---|---|
| **profiles** | id, data (JSON del profilo), extra_text, updated_at |
| **jobs** | id, source, source_id (unico con source), title, company, location, description, url, apply_url, **posted_at**, expires_at, discovered_at, status (active/inactive), language (no/en), norwegian_required |
| **matches** | profile_id, job_id, score 0–100, verdict (strong/good/stretch/poor), reasons, gaps, to_clarify |
| **applications** | id, job_id, status (draft/applied/interviewing/rejected/offer), cv (JSON), cover_letter, notes (keywords coperte, requisiti mancanti, modifiche), **snapshot** (JSON), applied_at |
| **interviews** | id, application_id, mode (text/voice), plan, transcript, feedback |

**Profilo (JSON):** nome, headline, contatti, sommario, skills, tools, lingue con livello, esperienze (ruolo, azienda, date, bullet), formazione, progetti, preferenze (ruoli, città, seniority, modalità di lavoro), **search_terms** (20–30 parole chiave in inglese + norvegese), **missing_info** (max 5 domande da fare all'utente).

**Annuncio normalizzato** (ciò che ogni provider deve restituire): title, url, company, location, description (se disponibile), posted_at (se disponibile), source, source_id.

"Recente" = `posted_at` (data di pubblicazione), **non** quando l'abbiamo trovato. Se una fonte non dà la data di pubblicazione, l'annuncio resta con data sconosciuta: si mostra "date unknown" e va in coda, non si usa `discovered_at` al suo posto.

Ogni membro ha il suo `radar.db` locale: per avere gli stessi annunci si usa `scan.py --load-seed`.

**Stati della candidatura:** `draft` alla creazione → `applied` con "I applied" → `interviewing`, `rejected`, `offer` cambiati a mano dall'utente nel tracker. Il colloquio simulato si sblocca da `applied` in poi.

---

## 6. API (contratto tra frontend e backend)

| Metodo | Endpoint | Cosa fa | Owner |
|---|---|---|---|
| GET/PUT | `/profile` | legge / salva profilo e preferenze | Gabriele |
| POST | `/profile/upload` | CV PDF + file extra + testo → profilo | Gabriele |
| GET/POST | `/applications` | lista / crea candidatura da job_id (genera CV + lettera) | Gabriele |
| GET/PATCH | `/applications/{id}` | legge / salva modifiche a CV, lettera, stato | Gabriele |
| POST | `/radar` | parametri: days (3/7/14/30), english_only, refresh → lista dei 15 migliori con score, motivi, lacune | Stefano |
| GET | `/jobs/{id}` | annuncio + match + eventuale candidatura | Stefano |
| POST | `/jobs/import` | annuncio catturato dall'estensione (URL, testo, JSON-LD) → job_id | Matilde |
| POST | `/applications/{id}/applied` | segna come inviata + salva snapshot | Matilde |
| POST | `/interview/{application_id}/start` | piano di 6 domande + primo messaggio | Matilde |
| POST | `/interview/{application_id}/turn` | risposta del candidato → domanda successiva | Matilde |
| POST | `/interview/{application_id}/feedback` | valutazione finale | Matilde |
| GET | `/voice/signed-url` | URL firmato ElevenLabs | Matilde |

Errori sempre come `{ "error": "messaggio" }`. I modelli Pydantic in `schemas.py` sono il contratto: chi li cambia lo dice nel gruppo. Le risposte reali devono avere **esattamente** la stessa forma dei file in `fixtures/`.

---

## 7. Radar

Principi di architettura:

1. **Provider a plugin.** Un file per ogni fonte in `radar/providers/`, tutti con lo stesso contratto: ricevono la configurazione e restituiscono una lista di annunci normalizzati. Aggiungere una fonte = aggiungere un file.
2. **Scansione senza AI.** I provider usano solo API e feed pubblici senza login: nessun token AI speso qui.
3. **Configurazione in YAML** (`companies.yml`): aziende di Oslo da seguire con careers URL e tipo di fonte (Teamtailor è molto diffuso in Norvegia; poi Greenhouse, Lever, Ashby).
4. **Filtri prima dell'AI:** finestra temporale (`posted_at` ultimi N giorni) → località (Oslo/area Oslo/Norvegia/remote; annuncio senza località = passa) → parole chiave sul titolo, positive e negative, prese dal profilo → deduplica per URL e per titolo+azienda.
5. **Liveness:** prima di spendere token si verifica che l'annuncio sia ancora aperto (per NAV basta `status = ACTIVE` e scadenza non passata; per le altre fonti si controlla l'URL).
6. **Solo alla fine l'AI:** ranking su ~40 candidati, a gruppi di 10 in parallelo.

**Fonti, in ordine di priorità**
- **NAV** (feed ufficiale degli annunci in Norvegia): token pubblico di prova da `pam-stilling-feed.nav.no/api/publicToken` (ruota: se arriva un 401 lo si riprende), feed su `/api/v1/feed`, partenza da una data con header `If-Modified-Since`, paginazione con `next_url`, dettaglio di ogni annuncio tramite il suo `url`. Tenere solo `status = ACTIVE`, filtrare per comune (Oslo e dintorni). Non contiene Finn.no. Non salvare i contatti delle persone. **Prima cosa da verificare sabato:** che il feed parta davvero da annunci recenti.
- **Teamtailor:** feed RSS pubblico `https://<azienda>.teamtailor.com/jobs.rss`.
- **Greenhouse / Lever / Ashby:** API pubbliche delle job board aziendali.

**Cosa calcoliamo per ogni annuncio:** lingua dell'annuncio (no/en) e flag "norvegese probabilmente richiesto". Diventa un badge e un filtro "English-friendly only", e ci serve nel pitch.

**Output del ranking per annuncio:** score 0–100, verdetto, max 3 motivi, max 3 lacune, max 2 cose da chiarire. Se i risultati recenti sono pochi, si allarga automaticamente a 14 e poi a 30 giorni, e la UI lo dice.

La scansione completa si lancia da terminale (`scripts/scan.py`); il pulsante Radar fa un aggiornamento leggero e poi lavora sul database.

---

## 8. Regole valide per tutti (anche per Claude Code e Lovable)

- **Mai inventare** esperienze, aziende, date, numeri, strumenti o certificazioni nel CV, nella lettera o nel feedback del colloquio. I requisiti mancanti si mostrano come "lacune", non si dichiarano.
- Lingua dei documenti: norvegese solo se l'annuncio è in norvegese **e** il candidato ha norvegese ≥ B2; altrimenti inglese.
- Tutte le chiamate a DeepSeek passano da `llm.py`, sempre con output JSON validato da Pydantic (se la validazione fallisce, un nuovo tentativo con l'errore nel prompt).
- Chiavi solo in `backend/.env`. Il frontend e l'estensione parlano solo con il nostro backend.
- Ogni attesa AI (10–30 s) mostra in UI cosa sta succedendo.
- Testi dell'interfaccia in inglese.
- Ognuno modifica **solo i propri file** (sezione 10). Per toccare `schemas.py`, `models.py`, `api.ts` o `fixtures/` si avvisa il gruppo.
- Git: un branch per persona, merge su `main` ai checkpoint (lo fa Gabriele per `radar`, Andrea per `radar-frontend`).

---

## 9. Lavorare in parallelo: dati finti (proxy) e collegamento

Nessuno aspetta gli altri. **Ognuno costruisce il proprio pezzo contro dati finti** con la stessa forma di quelli veri; quando il pezzo dell'altro è pronto si sostituisce il finto con il vero senza riscrivere nulla.

**Base comune — `fixtures/`** (la crea Gabriele nella prima ora, partendo da `schemas.py`): un profilo di esempio, 10–20 annunci di esempio, una risposta del Radar, una candidatura con CV e lettera, un colloquio con piano, transcript e feedback. Sono **il formato ufficiale**: se un'API reale restituisce qualcosa di diverso da questi file, è un bug dell'API.

**Proxy di ciascuno**

| Chi | Cosa usa come finto finché l'altro non è pronto | Come si collega dopo |
|---|---|---|
| **Gabriele** | Ogni endpoint nasce come **stub** che restituisce il file di `fixtures/` corrispondente (così frontend ed estensione hanno subito un backend che risponde). Per generare la candidatura usa `fixtures/jobs.json` invece degli annunci del Radar | Sostituisce gli stub uno a uno con la logica vera; la forma della risposta non cambia |
| **Stefano** | Lavora su `fixtures/profile.json` invece del profilo vero e, finché i provider non vanno, su `fixtures/jobs.json` / `data/seed_jobs.json`. `/radar` all'inizio restituisce `fixtures/radar_response.json` | Legge il profilo dal database; il ranking lavora sugli annunci scansionati |
| **Andrea** | Tutto il frontend gira con **`VITE_USE_MOCKS=true`**: `api.ts` restituisce i JSON di `src/mocks/` con un piccolo ritardo finto (per vedere gli stati di caricamento) | `VITE_USE_MOCKS=false` e frontend avviato in locale: `api.ts` chiama il backend vero, le pagine non cambiano |
| **Matilde** | Colloquio e feedback su `fixtures/application.json` (candidatura finta già `applied`). Estensione puntata allo stub di `/jobs/import`, che risponde con un job_id finto. Voce provata prima nell'anteprima dell'agente ElevenLabs | Il colloquio legge snapshot reali; l'estensione salva annunci veri nel DB |

**Collegamento:** a ogni checkpoint (sezione 11) si spengono i mock delle parti pronte. Alle 19 di sabato tutto deve girare con `VITE_USE_MOCKS=false`. I mock restano come rete di sicurezza per la demo.

---

## 10. Divisione dei ruoli

### Gabriele — Fondamenta, Profilo (A), Candidatura (C, backend) · *merge captain*
**File:** `main.py`, `db.py`, `models.py`, `schemas.py`, `llm.py`, `prompts.py`, `routers/profile.py`, `routers/applications.py`, `services/profile_extract.py`, `services/tailor.py`, `requirements.txt`, `.env.example`, cartella `fixtures/`.
**Consegna:** nella prima ora backend avviabile con modelli, schemi, `fixtures/` e **tutti gli endpoint come stub** (anche quelli degli altri, che poi li sostituiscono nei propri file); poi CV PDF → profilo corretto in < 30 s (DeepSeek accetta solo testo: il testo del PDF si estrae con `pypdf` e si manda al modello); generazione CV + lettera senza invenzioni, con elenco "cosa ho cambiato" e "requisiti mancanti".
**Proxy:** stub sulle fixtures (sezione 9).
**Extra:** ai checkpoint fa il merge su `main` del repo `radar`, spegne i mock delle parti pronte e prova il percorso completo.

### Stefano — Radar (B)
**File:** tutta la cartella `backend/radar/`, `routers/radar.py`, `routers/jobs.py`, `scripts/scan.py`, `data/seed_jobs.json`.
**Consegna:** entro il checkpoint delle 11, ≥ 200 annunci reali e attivi dell'area di Oslo nel database e `seed_jobs.json` committato; provider NAV, poi Teamtailor, poi gli altri; filtri, deduplica, liveness, ranking; `/radar` risponde in < 25 s.
**Proxy:** profilo finto e annunci finti finché i provider non vanno (sezione 9).
**Extra:** qualità del ranking provata su 3 profili del team; numeri per il pitch (annunci scansionati, % che richiede norvegese).

### Andrea — Frontend e design (Lovable) · *merge del repo frontend*
**File:** tutto `radar-frontend/` tranne `Interview`, `VoiceInterview`, `Feedback`.
**Consegna:** pagine Profile (upload, riepilogo, preferenze, domande mancanti), Radar (pulsante animato, filtri giorni/English-only, card con score, motivi, lacune e badge norvegese), Job, Applications (tracker a colonne per stato, stato modificabile a mano), ApplicationEditor (modifica CV e lettera, pulsanti PDF, "Apply on site", "I applied"), PrintCV/PrintCover (A4, una pagina, pulito). Interruttore mock/reale in `api.ts`.
**Proxy:** tutto con `VITE_USE_MOCKS=true` fin dalla prima ora (sezione 9).
**Extra:** nei prompt a Lovable incollare le sezioni 4, 6 e 9 e i JSON delle fixtures; vietare a Lovable backend e database propri. Slide del pitch domenica mattina.

### Matilde — Estensione, tracking, colloquio (D), voce
**File:** `extension/`, `routers/imports.py`, `routers/tracking.py`, `routers/interview.py`, `routers/voice.py`, `services/interview.py`; nel repo frontend `Interview`, `VoiceInterview`, `Feedback` (su un suo branch).
**Consegna, in quest'ordine:** "I applied" con snapshot → colloquio **testuale** (6 domande: 1 intro, 2 comportamentali sul CV, 2 tecniche sull'annuncio, 1 motivazione; una diventa "lacuna" se mancano requisiti) → feedback (punteggio, punti forti, miglioramenti, risposta migliore per ogni domanda, solo con fatti veri) → estensione (legge JSON-LD `JobPosting` se c'è, altrimenti il testo, manda tutto a `/jobs/import` sul backend e apre la pagina dell'annuncio nel frontend) → voce, **solo** quando il testo funziona.
**Proxy:** candidatura finta, stub di `/jobs/import`, anteprima dell'agente ElevenLabs (sezione 9).

### Chi aspetta chi
Una sola dipendenza vera: nella prima ora Gabriele pubblica `schemas.py`, `models.py`, `llm.py`, `fixtures/` e gli stub. Nel frattempo Stefano prova il feed NAV, Andrea imposta Lovable, Matilde prepara l'estensione e l'agente ElevenLabs. Dopo, ognuno lavora sui propri proxy.

---

## 11. Checkpoint (adattare agli orari reali)

| Quando | Deve funzionare |
|---|---|
| **Sab 10:00** | `fixtures/` e stub pubblicati; tutti avviano backend e frontend |
| **Sab 11:00 — GO/NO-GO Radar** | Annunci reali nel DB e seed committato, oppure piano B deciso. Frontend naviga tutte le pagine con i mock |
| **Sab 13:00** | Collegati: CV caricato → profilo salvato → Radar mostra risultati personalizzati con motivi |
| **Sab 16:00** | Collegati: Radar → scelgo un annuncio → CV + lettera nell'editor → PDF stampabile |
| **Sab 19:00** | Percorso completo A→B→C→D reale (mock spenti) con colloquio testuale e feedback; l'estensione importa un annuncio |
| **Sab 22:00** | Stop alle nuove funzioni (eccetto la voce). Si dorme |
| **Dom mattina** | Scansione fresca sul laptop della demo, profilo demo caricato, voce finita o tagliata, bugfix |
| **Dom ~11:30** | Code freeze, prova della demo ×3, video di backup |

Se siete in ritardo, si taglia in quest'ordine: fonti extra oltre NAV → voce → domande sulle info mancanti → PDF della lettera. **Mai** il percorso A→D testuale.

---

## 12. Piani B

| Problema | Piano B |
|---|---|
| Feed NAV non dà annunci recenti o il token non va | `seed_jobs.json` salvato appena funziona + provider Teamtailor/Greenhouse sulle aziende di Oslo; in demo: "catalogo limitato di annunci reali" |
| Pochi annunci in inglese | Allargamento a 14/30 giorni + badge norvegese → diventa un insight del pitch |
| AI lenta | Modello veloce per il ranking, gruppi paralleli, meno candidati; Radar pre-eseguito prima della demo |
| PDF del CV illeggibile | Incollare il testo del CV nel campo "altro su di te" |
| Lovable non collabora | Si scarica il codice dal repo `radar-frontend` e si continua in VS Code con Claude Code |
| Un pezzo non è pronto per la demo | Quella parte resta sui mock e si mostra comunque il flusso |
| Voce non parte | Modalità testo, sempre pronta |
| Wi-Fi lento | Hotspot + video di backup |

---

## 13. Demo (3 minuti)

Problema (studenti internazionali a Oslo, CV sempre uguale, non sanno quali annunci richiedono il norvegese) → profilo già caricato → **Radar**: "N annunci degli ultimi 7 giorni, ecco i 15 migliori" → una card: score, motivi, lacune, badge norvegese → CV e lettera su misura, "non inventa nulla, ecco cosa manca" → PDF, "I applied" → colloquio simulato (2 scambi) + feedback → estensione su una pagina carriere → chiusura: architettura a provider, prossime fonti.

---

## 14. Come usare questo file con Claude Code

Primo messaggio a Claude Code, uguale per tutti tranne il nome:

> Leggi `BLUEPRINT.md`. Sono **<Stefano>**. Costruisci solo i file assegnati a me nella sezione 10, rispettando struttura (sez. 4), modello dati (sez. 5), API (sez. 6), regole (sez. 8) e il lavoro con i dati finti (sez. 9). Non modificare file di altri; se serve cambiare un contratto condiviso, fermati e chiedimelo. Parti dalla consegna più urgente del mio ruolo, usando i proxy finché gli altri pezzi non sono pronti, e dimmi come testarla.
