"use strict";
const grid = document.querySelector("#coverGrid");
const searchInput = document.querySelector("#searchInput");
const emptyState = document.querySelector("#emptyState");
const showMore = document.querySelector("#showMore");
let activeSeries = "ALL", activeStyle = "All styles", query = "", visibleLimit = 9;
const seriesOrder = ["BLEACH", "NARUTO", "DRAGON BALL", "BLACK CLOVER", "DIGIMON", "SWORD ART ONLINE", "ONE PIECE", "JUJUTSU KAISEN", "SOUL EATER", "OTHER"];
const seriesOptions = ["ALL", ...seriesOrder.filter(series => COVERS.some(video => video.series === series))];
const styleOptions = ["All styles", ...new Set(["English covers", "Acoustic", "Orchestral", ...COVERS.map(video => video.style)])].filter(style => style.toLocaleLowerCase() !== "pop rock");
document.querySelector("#year").textContent = new Date().getFullYear();
function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function renderControls() {
  for (const [selector, options, active, setActive] of [
    ["#seriesFilters", seriesOptions, activeSeries, value => {activeSeries=value;}],
    ["#styleFilters", styleOptions, activeStyle, value => {activeStyle=value;}]
  ]) {
    const container = document.querySelector(selector);
    container.replaceChildren();
    for (const option of options) {
      const button = document.createElement("button");
      button.type = "button"; button.textContent = option;
      button.className = "filter-button" + (option===active ? " active" : "");
      button.setAttribute("aria-pressed", String(option===active));
      button.addEventListener("click", () => {
        setActive(option); visibleLimit=9; renderControls(); renderCovers();
        [...container.children].find(b=>b.textContent===option)?.focus({preventScroll:true});
      });
      container.append(button);
    }
  }
}
function renderCovers() {
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const matches = COVERS.filter(item =>
    (activeSeries === "ALL" || item.series === activeSeries) &&
    (activeStyle === "All styles" || item.style === activeStyle) &&
    [item.title,item.rawTitle || "",item.anime,item.style,item.series].join(" ").toLocaleLowerCase().includes(normalizedQuery)
  );
  const shown = matches.slice(0,visibleLimit);
  grid.innerHTML = shown.map(item => `
    <a class="cover-card" href="https://www.youtube.com/watch?v=${encodeURIComponent(item.youtubeId)}" target="_blank" rel="noopener noreferrer">
      <div class="cover-art"><img src="https://i.ytimg.com/vi/${encodeURIComponent(item.youtubeId)}/hqdefault.jpg" alt="${escapeHtml(item.title)} — ${escapeHtml(item.anime)}" width="480" height="360" loading="lazy"><span class="play-pill" aria-hidden="true">▶ WATCH</span></div>
      <div class="cover-meta"><p class="category">${escapeHtml(item.style)}</p><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.anime)}</p></div>
    </a>`).join("");
  emptyState.hidden = matches.length !== 0;
  showMore.hidden = shown.length >= matches.length;
  showMore.textContent = `More covers (${matches.length - shown.length}) ↓`;
  document.querySelector("#resultCount").textContent = `${shown.length} of ${matches.length} covers`;
}
searchInput.addEventListener("input", e => {query=e.target.value;visibleLimit=9;renderCovers();});
showMore.addEventListener("click", () => {const previousCount=grid.children.length;visibleLimit+=9;renderCovers();grid.children[previousCount]?.focus({preventScroll:true});});
document.querySelector("#resetFilters").addEventListener("click", () => {
  activeSeries="ALL";activeStyle="All styles";query="";visibleLimit=9;searchInput.value="";
  renderControls();renderCovers();searchInput.focus({preventScroll:true});
});
function renderLatestUpload() {
  const latest = COVERS[0];
  if (!latest) return;
  const feature = document.querySelector(".hero-feature");
  feature.href = `https://www.youtube.com/watch?v=${encodeURIComponent(latest.youtubeId)}`;
  feature.setAttribute("aria-label", `Watch ${latest.title} — ${latest.style} on YouTube`);
  const thumbnail = feature.querySelector("img");
  thumbnail.src = `https://i.ytimg.com/vi/${encodeURIComponent(latest.youtubeId)}/hqdefault.jpg`;
  thumbnail.alt = `${latest.title} — ${latest.anime}`;
  feature.querySelector("strong").textContent = latest.title;
  feature.querySelector("small").textContent = `${latest.anime} · ${latest.style}`;
}
renderLatestUpload();renderControls();renderCovers();

// Shared website visit count. Only the production site records a visit.
async function updateVisitCounter() {
  const output = document.querySelector("#visitCount");
  if (!output) return;
  const storageKey = "ppnj:last-counted-visit";
  const counterKey = "poppunknojutsu_github_io_visits_20261021_9e8bf73a";
  const visitWindow = 30 * 60 * 1000;
  const update = async () => {
    const now = Date.now();
    let lastVisit = null;
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored !== null && Number.isFinite(Number(stored))) lastVisit = Number(stored);
    } catch (_) { /* Counting can still work when browser storage is disabled. */ }
    const recentlyCounted = lastVisit !== null && now >= lastVisit && now - lastVisit < visitWindow;
    const action = location.hostname === "poppunknojutsu.github.io" && !recentlyCounted ? "hit" : "get";
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch(`https://countapi.mileshilliard.com/api/v1/${action}/${counterKey}`, {
        signal: controller.signal, cache: "no-store", credentials: "omit", referrerPolicy: "no-referrer"
      });
      if (!response.ok) throw new Error("Visit counter unavailable");
      const data = await response.json();
      const count = Number(data.value);
      if (!/^\d+$/.test(String(data.value)) || !Number.isSafeInteger(count)) throw new Error("Invalid visit count");
      output.textContent = new Intl.NumberFormat().format(count);
      if (action === "hit") {
        try { localStorage.setItem(storageKey, String(now)); } catch (_) { /* Storage is optional. */ }
      }
    } finally {
      clearTimeout(timeout);
    }
  };
  try {
    // Coordinate open tabs where supported, avoiding simultaneous duplicate counts.
    if (typeof navigator !== "undefined" && navigator.locks?.request) {
      await navigator.locks.request("ppnj-visit-counter", update);
    } else {
      await update();
    }
  } catch (_) {
    output.textContent = "—";
    output.closest(".site-visits").title = "Visit count temporarily unavailable. Please check again later.";
  }
}
updateVisitCounter();
