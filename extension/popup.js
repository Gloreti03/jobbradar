// JobbRadar extension popup: reads the job ad on the current tab (JSON-LD JobPosting if present,
// otherwise the visible text), sends it to POST /jobs/import on our backend and opens the
// job page in the frontend. The extension talks ONLY to our backend (BLUEPRINT sec. 8).

const DEFAULTS = { api: "http://localhost:8000", app: "http://localhost:5173" };
const JOB_PAGE = (app, id) => `${app}/jobs/${id}`; // frontend route of the job page

const $ = (id) => document.getElementById(id);
let captured = null;

// Runs INSIDE the web page (injected with chrome.scripting): must be self-contained.
function capturePage() {
  const findPosting = (data) => {
    if (Array.isArray(data)) {
      for (const item of data) {
        const found = findPosting(item);
        if (found) return found;
      }
      return null;
    }
    if (!data || typeof data !== "object") return null;
    const type = data["@type"];
    if (type === "JobPosting" || (Array.isArray(type) && type.includes("JobPosting"))) return data;
    if (data["@graph"]) return findPosting(data["@graph"]);
    return null;
  };

  let jsonLd = null;
  for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
    try {
      jsonLd = findPosting(JSON.parse(script.textContent));
      if (jsonLd) break;
    } catch (_) { /* invalid JSON-LD: ignore */ }
  }

  const meta = (name) =>
    document.querySelector(`meta[property="${name}"], meta[name="${name}"]`)?.content?.trim() || null;
  const h1 = document.querySelector("h1")?.innerText?.trim() || null;
  const main = document.querySelector("main, [role=main], article") || document.body;

  return {
    url: location.href,
    title: h1 || meta("og:title") || document.title || null,
    company: meta("og:site_name"),
    location: null,
    text: (main.innerText || "").slice(0, 20000),
    json_ld: jsonLd,
  };
}

async function settings() {
  try {
    const saved = await chrome.storage.local.get(["api", "app"]);
    return { ...DEFAULTS, ...saved };
  } catch (_) {
    return DEFAULTS;
  }
}

function setStatus(text, kind = "") {
  $("status").textContent = text;
  $("status").className = kind;
}

function showJob(job) {
  const posting = job.json_ld || {};
  const title = posting.title || job.title || "(no title found)";
  const org = posting.hiringOrganization;
  const company = (Array.isArray(org) ? org[0] : org)?.name || job.company || "";
  $("job").innerHTML = "";
  const b = document.createElement("b");
  b.textContent = title;
  const small = document.createElement("span");
  small.className = "muted";
  small.textContent = [company, job.json_ld ? "structured data found" : "page text only"].filter(Boolean).join(" · ");
  $("job").append(b, small);
}

async function init() {
  const s = await settings();
  $("api").value = s.api;
  $("app").value = s.app;
  for (const id of ["api", "app"]) {
    $(id).addEventListener("change", () => chrome.storage.local.set({ [id]: $(id).value.replace(/\/+$/, "") }));
  }

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !/^https?:/.test(tab.url || "")) {
    $("job").innerHTML = '<span class="muted">Open a job ad page first.</span>';
    return;
  }
  try {
    const [{ result }] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: capturePage });
    captured = result;
    showJob(captured);
    $("save").disabled = false;
  } catch (err) {
    $("job").innerHTML = '<span class="error">Cannot read this page.</span>';
    setStatus(String(err.message || err), "error");
  }
}

async function save() {
  if (!captured) return;
  $("save").disabled = true;
  setStatus("Saving to JobbRadar…");
  const api = $("api").value.replace(/\/+$/, "");
  const app = $("app").value.replace(/\/+$/, "");
  try {
    const resp = await fetch(`${api}/jobs/import`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(captured),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.error || `Backend error ${resp.status}`);
    setStatus(data.created ? "Saved! Opening JobbRadar…" : "Already in JobbRadar. Opening…", "ok");
    chrome.tabs.create({ url: JOB_PAGE(app, data.job_id) });
  } catch (err) {
    const msg = err instanceof TypeError ? `Backend not reachable at ${api}` : err.message;
    setStatus(msg, "error");
    $("save").disabled = false;
  }
}

$("save").addEventListener("click", save);
init();
