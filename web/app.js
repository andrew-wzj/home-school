"use strict";
// Home School front end: plain JS, hash routes, no build step.
//   #/            Today
//   #/lesson/L5   Lesson (optional ?seg=L5-2)
//   #/hw/hw1      Assignment (optional ?q=Q4)
//   #/settings    Settings

const $ = (s, r = document) => r.querySelector(s);
let S = null;          // server state
let L = "en";          // UI language
let view = { page: "today" };
let player = null;     // YouTube player
let ytReady = null;

// ---------- helpers ----------
function t(k, v = {}) {
  const s = (STRINGS[L] && STRINGS[L][k]) || STRINGS.en[k] || k;
  return s.replace(/\{(\w+)\}/g, (_, n) => (v[n] !== undefined ? v[n] : ""));
}
function tr(o) { return o ? (o[L] || o.en || "") : ""; }
function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function mmss(sec) { sec = Math.max(0, Math.round(sec)); return Math.floor(sec / 60) + ":" + String(sec % 60).padStart(2, "0"); }
function shortDate(iso) {
  const d = new Date(iso + "T00:00:00");
  return L === "zh" ? (d.getMonth() + 1) + "月" + d.getDate() + "日"
    : d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}
function dueText(days) {
  if (days < 0) return t("overdue", { n: -days });
  if (days === 0) return t("today");
  if (days === 1) return t("tomorrow");
  return t("inDays", { n: days });
}
async function api(path, body) {
  const opt = body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json", "X-Home-School": "1" }, body: JSON.stringify(body)
  };
  const r = await fetch(path, opt);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}
function toast(msg) {
  const el = document.createElement("div");
  el.className = "toast"; el.textContent = msg; el.setAttribute("role", "status");
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 2600);
}
async function copyText(text, btn) {
  try { await navigator.clipboard.writeText(text); }
  catch (e) {
    const ta = document.createElement("textarea"); ta.value = text; document.body.appendChild(ta);
    ta.select(); document.execCommand("copy"); ta.remove();
  }
  if (btn) { const old = btn.textContent; btn.textContent = t("copied"); setTimeout(() => (btn.textContent = old), 1500); }
}
const lectures = () => S.course.lectures;
const lecture = id => lectures().find(l => l.id === id);
const moduleOf = id => S.course.modules.find(m => m.lectures.includes(id));
const segDone = id => !!S.watched[id];
const store = {
  get(k) { try { return JSON.parse(localStorage.getItem("hs." + k)); } catch (e) { return null; } },
  set(k, v) { v == null ? localStorage.removeItem("hs." + k) : localStorage.setItem("hs." + k, JSON.stringify(v)); },
};
const icon = {
  back: '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M10 3L5 8l5 5"/></svg>',
  clock: '<svg width="16" height="16" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><circle cx="9" cy="10" r="6.5"/><path d="M9 6.5V10l2.2 1.6M7 1.8h4"/></svg>',
  gear: '<svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><circle cx="10" cy="10" r="2.6"/><path d="M10 1.8v2.4M10 15.8v2.4M1.8 10h2.4M15.8 10h2.4M4.2 4.2l1.7 1.7M14.1 14.1l1.7 1.7M4.2 15.8l1.7-1.7M14.1 5.9l1.7-1.7"/></svg>',
  done: '<svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="#2E7D4F" stroke-width="2" aria-hidden="true"><circle cx="10" cy="10" r="8"/><path d="M6.5 10.2l2.4 2.3 4.6-4.8"/></svg>',
  cur: '<svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="#2B56C4" stroke-width="2" aria-hidden="true"><circle cx="10" cy="10" r="8"/><path d="M8.5 6.8l4.5 3.2-4.5 3.2z" fill="#2B56C4"/></svg>',
  todo: '<svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="#8A8984" stroke-width="2" aria-hidden="true"><circle cx="10" cy="10" r="8"/></svg>',
};

// ---------- session timer & breaks ----------
function session() { return store.get("session"); }
function elapsedMin(s) {
  if (!s) return 0;
  const now = Date.now();
  return (now - s.start - s.breakMs - (s.breakStart ? now - s.breakStart : 0)) / 60000;
}
async function startSession(lectureId, planned) {
  const r = await api("/api/session/start", { lecture_id: lectureId, planned });
  store.set("session", { id: r.id, lecture: lectureId, planned, start: Date.now(), breakMs: 0, breakStart: null, cycles: 0, breaks: 0 });
  if (S.settings.focus && "Notification" in window && Notification.permission === "default") {
    Notification.requestPermission().catch(() => {});
  }
}
async function finishSession() {
  const s = session();
  if (!s) return;
  if (s.breakStart) endBreak();
  const cur = session();
  await api("/api/session/end", { id: cur.id, actual_min: Math.round(elapsedMin(cur) * 10) / 10, breaks: cur.breaks });
  store.set("session", null);
  toast(t("timer", { e: Math.round(elapsedMin(cur)), p: cur.planned }));
  location.hash = "#/";
}
function startBreak() {
  const s = session();
  s.breakStart = Date.now(); store.set("session", s);
  if (player && player.pauseVideo) try { player.pauseVideo(); } catch (e) {}
  if (document.hidden && "Notification" in window && Notification.permission === "granted") {
    new Notification(t("brand"), { body: t("breakNotify", { n: S.settings.break_len }) });
  }
  renderOverlay();
}
function endBreak() {
  const s = session();
  if (!s || !s.breakStart) return;
  s.breakMs += Date.now() - s.breakStart; s.breakStart = null; s.breaks += 1;
  store.set("session", s);
  renderOverlay();
}
function renderOverlay() {
  const s = session(), box = $("#overlay");
  if (!s || !s.breakStart) { box.innerHTML = ""; return; }
  const left = S.settings.break_len * 60 - (Date.now() - s.breakStart) / 1000;
  if (!box.firstChild) {
    box.innerHTML = `<div class="overlay" role="dialog" aria-modal="true" aria-labelledby="brk">
      <div id="brk" style="font-size:20px;font-weight:700">${esc(t("breakTitle"))}</div>
      <div class="clock" id="brkclock">${mmss(left)}</div>
      <div>${esc(t("breakBody"))}</div>
      <button class="btn ghost" id="skipbrk">${esc(t("skipBreak"))}</button></div>`;
    $("#skipbrk").onclick = endBreak;
  } else {
    $("#brkclock").textContent = mmss(left);
  }
}
function tick() {
  const s = session();
  if (s && S) {
    if (s.breakStart) {
      const left = S.settings.break_len * 60 - (Date.now() - s.breakStart) / 1000;
      if (left <= 0 || !S.settings.focus) endBreak(); else renderOverlay();
    } else {
      const due = Math.floor(elapsedMin(s) / S.settings.break_every);
      if (due > s.cycles) {
        s.cycles = due; store.set("session", s);
        if (S.settings.focus) startBreak();
      }
    }
    const tm = $("#timer");
    if (tm) tm.innerHTML = timerText(s);
  }
  if (view.page === "hw") tickQuestion();
}
function timerText(s) {
  const e = elapsedMin(s);
  let out = icon.clock + " " + esc(t("timer", { e: Math.floor(e), p: s.planned }));
  if (S.settings.focus) {
    const next = (s.cycles + 1) * S.settings.break_every - e;
    out += " · " + esc(t("breakIn", { n: Math.max(0, Math.ceil(next)) }));
  }
  return out;
}

// ---------- top bar ----------
function renderBar(crumb) {
  const f = S.settings.focus;
  const s = session();
  let timer = "";
  if (view.page === "lesson") {
    timer = s
      ? `<div class="timer" id="timer" aria-live="off">${timerText(s)}</div><button class="pill" id="finish">${esc(t("finish"))}</button>`
      : `<span class="small muted">${esc(t("notTiming"))}</span><button class="pill" id="starttimer">${esc(t("startTimer"))}</button>`;
  }
  $("#bar").innerHTML = `
    <a class="brand" href="#/"><span class="mark">学</span><b>${esc(t("brand"))}</b></a>
    ${crumb ? `<a class="pill" href="#/" style="border:0;padding:0 6px">${icon.back}${esc(t("back"))}</a><span class="crumb">${crumb}</span>`
      : `<span class="crumb">${esc(S.course.code)} ${esc(tr(S.course.title))}</span>`}
    <div class="right">
      ${timer}
      <button class="pill" id="focus" aria-pressed="${f}" title="${esc(t("focusAria"))}"><span class="track"><i></i></span><span>${esc(f ? t("focusOn") : t("focusOff"))}</span></button>
      <a class="pill" href="#/settings" aria-label="${esc(t("settings"))}" style="padding:0 12px">${icon.gear}</a>
      <button class="pill" id="lang" aria-label="${esc(t("langAria"))}" style="min-width:44px;justify-content:center">${esc(t("langBtn"))}</button>
    </div>`;
  $("#focus").onclick = async () => { await saveSetting("focus", !S.settings.focus); };
  $("#lang").onclick = async () => { await saveSetting("lang", L === "en" ? "zh" : "en"); };
  if ($("#finish")) $("#finish").onclick = finishSession;
  if ($("#starttimer")) $("#starttimer").onclick = () => confirmStart(view.id, S.suggested.minutes, () => render());
}
async function saveSetting(k, v) {
  await api("/api/settings", { [k]: v });
  await load();
  render();
}

// ---------- start dialog (phone reminder) ----------
function confirmStart(lectureId, planned, after) {
  const go = async () => { await startSession(lectureId, planned); after(); };
  if (!S.settings.focus) return go();
  const d = document.createElement("dialog");
  d.innerHTML = `<form method="dialog"><h2 style="font-size:18px">${esc(t("dndTitle"))}</h2><p style="margin:0">${esc(t("dndBody"))}</p>
    <div class="row"><button class="btn" value="go">${esc(t("dndGo"))}</button><button class="btn ghost" value="cancel">${esc(t("cancel"))}</button></div></form>`;
  document.body.appendChild(d);
  d.addEventListener("close", () => { const v = d.returnValue; d.remove(); if (v === "go") go(); });
  d.showModal();
}

// ---------- stuck dialog ----------
function openStuck(ref, question, minutes, done) {
  const d = document.createElement("dialog");
  d.innerHTML = `<form method="dialog">
    <h2 style="font-size:18px">${esc(t("stuckTitle"))}</h2>
    <label class="f">${esc(t("stuckWhat"))}<input type="text" name="q" value="${esc(question)}" required></label>
    <label class="f">${esc(t("stuckMin"))}<input type="number" name="m" min="0" step="1" value="${Math.round(minutes)}"></label>
    <label class="f">${esc(t("stuckDesc"))}<textarea name="d" style="min-height:90px"></textarea></label>
    <div class="row"><button class="btn" value="save">${esc(t("save"))}</button><button class="btn ghost" value="cancel" formnovalidate>${esc(t("cancel"))}</button></div></form>`;
  document.body.appendChild(d);
  d.addEventListener("close", async () => {
    const f = d.querySelector("form");
    const v = d.returnValue, q = f.q.value.trim(), m = Number(f.m.value) || 0, desc = f.d.value.trim();
    d.remove();
    if (v === "save" && q) {
      await api("/api/stuck", { ref, question: q, minutes: m, description: desc });
      toast(t("savedOk"));
      if (done) done();
    }
  });
  d.showModal();
}

// ---------- Today ----------
function renderToday() {
  renderBar("");
  const p = S.today, s = session();
  let card;
  if (!p) {
    card = `<div class="card big"><h1 class="bigq">${esc(t("allDone"))}</h1></div>`;
  } else {
    const lec = lecture(p.lecture);
    const partial = lec.segments.some(x => segDone(x.id));
    const nSeg = p.segments.length;
    const steps = [
      { name: t("prep"), det: p.pages === "all" ? t("prepDetailAll") : t("prepDetail", { p: p.pages }), m: p.steps.prep },
      { name: p.has_video ? t("watch") : t("read"), det: p.has_video ? t(nSeg === 1 ? "watchDetail" : "watchDetailN", { n: nSeg }) : t("readDetail"), m: p.steps.watch },
      { name: t("quiz"), det: t("quizDetail"), m: p.steps.quiz },
    ];
    const basis = S.suggested.basis === "default" ? t("basisDefault") : t("basisHistory");
    const resume = s && s.lecture === p.lecture;
    card = `<div class="card big">
      <div style="display:flex;flex-direction:column;gap:6px">
        <div class="small muted">${esc(shortDate(S.date))}${partial ? " · " + esc(t("partOf", { id: lec.id })) : ""}</div>
        <h1 class="bigq">${esc(lec.id)} · ${esc(tr(lec.title))}</h1>
        <div class="row" style="gap:8px">
          <span class="chip blue" title="${esc(basis)}">${esc(t("suggested", { m: S.suggested.minutes }))}</span>
          ${S.settings.focus ? `<span class="chip">${esc(t("breaks", { n: S.settings.break_every }))}</span><span class="chip">${esc(t("phone"))}</span>` : ""}
        </div>
      </div>
      <ol class="steps">${steps.map((x, i) => `<li><div class="num">${i + 1}</div><div class="name">${esc(x.name)}</div><div class="det">${esc(x.det)}</div><div class="m">${esc(t("min", { n: x.m }))}</div></li>`).join("")}</ol>
      <div class="row"><button class="btn" id="start" style="padding:0 32px">${esc(resume ? t("resume") : t("start"))}</button></div>
    </div>`;
  }

  const ls = S.last_stuck;
  const stuckCard = ls ? `<div class="card" style="flex-direction:row;flex-wrap:wrap;align-items:center;gap:12px">
      <div class="small muted">${esc(t("lastStuck"))}</div>
      <div style="flex:1">${esc(ls.ref.toUpperCase())} · ${esc(ls.question)} · ${esc(t("min", { n: Math.round(ls.minutes) }))}</div>
      <a href="${lecture(ls.ref) ? "#/lesson/" + esc(ls.ref) : "#/hw/" + esc(ls.ref) + "?q=" + encodeURIComponent(ls.question)}">${esc(t("retry"))}</a></div>` : "";

  const note = S.note ? `<div class="card" style="gap:4px"><div class="small muted">${esc(t("progress"))}</div><div>${esc(S.note)}</div></div>` : "";

  const firstOpen = S.due.find(d => !d.done);
  const due = S.due.map(d => {
    const cls = d.done ? "green" : (d === firstOpen ? "orange" : "");
    return `<a class="between" href="#/hw/${esc(d.id)}" style="text-decoration:none;color:inherit;align-items:center">
      <span>${esc(d.name)}</span><span class="chip ${cls}" title="${esc(shortDate(d.date))}">${esc(d.done ? t("done") : dueText(d.days))}</span></a>`;
  }).join("");

  const w = S.week;
  const week = w.planned
    ? `<div style="font-size:28px;font-weight:700">${w.done} / ${w.planned}</div><div class="meter"><i style="width:${Math.round(100 * w.done / w.planned)}%"></i></div>`
    : `<div class="muted small">${esc(t("weekNone"))}</div>`;

  const outline = lectures().map(l => {
    const n = l.segments.filter(x => segDone(x.id)).length;
    const chip = n === l.segments.length ? `<span class="chip green">${esc(t("done"))}</span>` : (n ? `<span class="chip blue">${n} / ${l.segments.length}</span>` : "");
    return `<li><a href="#/lesson/${esc(l.id)}"><span class="when">${esc(shortDate(S.schedule[l.id]).replace(/^\w+, /, ""))}</span><span class="t">${esc(l.id)} · ${esc(tr(l.title))}</span>${chip}</a></li>`;
  }).join("");

  $("#app").innerHTML = `<main>
    <section class="col-main">${card}${stuckCard}${note}</section>
    <aside class="col-side">
      <div class="card" style="gap:14px"><h2>${esc(t("due"))}</h2>${due}</div>
      <div class="card" style="gap:10px"><h2>${esc(t("week"))}</h2>${week}</div>
      <div class="card" style="gap:6px"><h2>${esc(t("outline"))}</h2><ul class="outline">${outline}</ul></div>
    </aside></main>`;

  if ($("#start")) $("#start").onclick = () => {
    const go = () => { location.hash = "#/lesson/" + p.lecture + "?seg=" + p.segments[0]; };
    if (s && s.lecture === p.lecture) return go();
    confirmStart(p.lecture, S.suggested.minutes, go);
  };
}

// ---------- Lesson ----------
function loadYT() {
  if (ytReady) return ytReady;
  ytReady = new Promise(res => {
    if (window.YT && window.YT.Player) return res();
    window.onYouTubeIframeAPIReady = res;
    const sc = document.createElement("script"); sc.src = "https://www.youtube.com/iframe_api";
    sc.onerror = () => res("fail");
    document.head.appendChild(sc);
  });
  return ytReady;
}
function lessonTarget(lec) { return lec.target; }

function renderLesson(id, params) {
  const lec = lecture(id);
  if (!lec) { location.hash = "#/"; return; }
  const mod = moduleOf(id);
  const segs = lec.segments;
  let cur = segs.find(x => x.id === params.get("seg")) || segs.find(x => !segDone(x.id)) || segs[0];
  view.seg = cur.id;
  view.segOpened = Date.now();
  renderBar(`<strong>${esc(lec.id)} · ${esc(tr(lec.title))}</strong> <span id="segof"></span>`);

  const target = lessonTarget(lec);
  const showQ = target.kind === "recall" ? { kind: "module", text: mod.question, note: t("answerAfter", { id: mod.answer_after }) }
    : { kind: target.kind, text: target.text, note: target.kind === "module" ? t("answerNow") : t("answerNow") };
  const qchip = showQ.kind === "module" ? t("moduleQ") : t("lectureQ");
  const hw = S.course.assignments.find(a => a.due_after.lecture === id) || S.course.assignments.find(a => a.lectures.includes(id));
  const draftKey = "draft." + target.ref;

  $("#app").innerHTML = `<main class="lesson">
    <section class="col-main">
      <div class="card qcard"><span class="chip solid">${esc(qchip)}</span>
        <div style="display:flex;flex-direction:column;gap:2px"><div>${esc(tr(showQ.text))}</div><div class="small muted">${esc(showQ.note)}</div></div></div>
      <div class="video" id="video"></div>
      <div class="card segs" id="segs"></div>
    </section>
    <aside class="col-side">
      <div class="card" style="gap:10px">
        <label for="answer" style="font-weight:700">${esc(t("answer"))}</label>
        ${target.kind === "recall" ? `<div class="small muted">${esc(tr(target.text))}</div>` : ""}
        <textarea id="answer" placeholder="${esc(t("placeholder"))}">${esc(store.get(draftKey) || "")}</textarea>
        <button class="btn" id="send">${esc(t("send"))}</button>
        <div id="result" aria-live="polite"></div>
      </div>
      <div class="card" style="gap:8px" id="points"></div>
      <div class="pair">
        <button class="btn ghost" id="stuck">${esc(t("stuck"))}</button>
        ${hw ? `<a class="btn line" href="#/hw/${esc(hw.id)}">${esc(t("homework"))}</a>` : ""}
      </div>
      <div class="pair"><button class="btn ghost sm" id="mark"></button><button class="btn ghost sm" id="next">${esc(t("nextSeg"))}</button></div>
    </aside></main>`;

  $("#answer").oninput = e => store.set(draftKey, e.target.value);
  $("#send").onclick = () => sendAnswer(lec, target);
  $("#stuck").onclick = () => {
    const seg = segs.find(x => x.id === view.seg);
    openStuck(lec.id, lec.id + " · " + tr(seg.title), (Date.now() - view.segOpened) / 60000);
  };
  $("#mark").onclick = async () => {
    const seg = view.seg, now = !segDone(seg);
    await api("/api/segment", { segment_id: seg, watched: now });
    if (now) S.watched[seg] = new Date().toISOString(); else delete S.watched[seg];
    updateLesson(lec);
  };
  $("#next").onclick = () => {
    const i = segs.findIndex(x => x.id === view.seg);
    if (i < segs.length - 1) selectSeg(lec, segs[i + 1].id);
  };
  $("#segs").onclick = e => { const b = e.target.closest("[data-seg]"); if (b) selectSeg(lec, b.dataset.seg); };

  mountVideo(lec, cur);
  updateLesson(lec);
  showLastAnswer(target.ref);
}

function selectSeg(lec, segId) {
  view.seg = segId; view.segOpened = Date.now();
  history.replaceState(null, "", "#/lesson/" + lec.id + "?seg=" + segId);
  const seg = lec.segments.find(x => x.id === segId);
  if (lec.video && player && player.loadVideoById) {
    player.loadVideoById({ videoId: lec.video.youtube, startSeconds: seg.start, endSeconds: seg.end });
  } else {
    mountVideo(lec, seg);
  }
  updateLesson(lec);
}

function updateLesson(lec) {
  const segs = lec.segments, i = segs.findIndex(x => x.id === view.seg), seg = segs[i];
  $("#segof").textContent = " " + t("segOf", { a: i + 1, b: segs.length });
  $("#segs").innerHTML = segs.map(x => {
    const state = x.id === view.seg ? "cur" : (segDone(x.id) ? "done" : "todo");
    const tm = x.start == null ? (x.pages === "all" ? t("openSlides") : t("slidesPages", { p: x.pages })) : mmss(x.start) + "–" + mmss(x.end) + " · p." + x.pages;
    return `<button class="seg ${state === "cur" ? "cur" : ""}" data-seg="${esc(x.id)}" aria-current="${state === "cur"}">
      ${segDone(x.id) && state !== "cur" ? icon.done : icon[state]}<span class="tt">${esc(tr(x.title))}</span><span class="tm">${esc(tm)}</span></button>`;
  }).join("");
  const read = !lec.video;
  $("#mark").textContent = segDone(seg.id) ? t("unmark") : (read ? t("markRead") : t("markDone"));
  $("#next").disabled = i >= segs.length - 1;
  const watchedSegs = segs.filter(x => segDone(x.id));
  const pts = watchedSegs.flatMap(x => (x.points && x.points[L]) || x.points.en);
  $("#points").innerHTML = `<div class="between"><h2>${esc(t("points"))}</h2>${segDone(seg.id) ? "" : `<span class="small muted">${esc(t("afterVideo"))}</span>`}</div>
    ${pts.length ? `<ul class="points">${pts.map(p => `<li>${esc(p)}</li>`).join("")}</ul>` : ""}`;
}

async function mountVideo(lec, seg) {
  const box = $("#video");
  player = null;
  if (!lec.video) {
    box.innerHTML = `<div class="reader"><div style="font-size:18px;font-weight:700">${esc(tr(seg.title))}</div>
      <div class="muted" style="max-width:520px">${esc(tr(seg.summary))}</div>
      <a class="btn" href="${esc(lec.slides)}" target="_blank" rel="noopener">${esc(t("openSlides"))}</a></div>`;
    return;
  }
  box.innerHTML = `<div class="frame"><div id="player"></div></div>`;
  const ok = await loadYT();
  const fail = () => {
    box.innerHTML = `<div class="fallback"><div>${esc(t("embedFail"))}</div>
      <a class="btn" target="_blank" rel="noopener" href="https://www.youtube.com/watch?v=${encodeURIComponent(lec.video.youtube)}&t=${seg.start}s">${esc(t("openYouTube"))} · ${mmss(seg.start)}</a>
      <a href="${esc(lec.slides)}" target="_blank" rel="noopener" style="color:#ECEBE6">${esc(t("openSlides"))}</a></div>`;
  };
  if (ok === "fail" || !$("#player")) return fail();
  const zh = L === "zh";
  player = new YT.Player("player", {
    videoId: lec.video.youtube,
    playerVars: { start: seg.start, end: seg.end, rel: 0, playsinline: 1, hl: zh ? "zh-CN" : "en",
      cc_load_policy: zh ? 1 : 0, cc_lang_pref: zh ? "zh-Hans" : "en" },
    events: {
      onStateChange: async e => {
        if (e.data === YT.PlayerState.ENDED && !segDone(view.seg)) {
          await api("/api/segment", { segment_id: view.seg, watched: true });
          S.watched[view.seg] = new Date().toISOString();
          updateLesson(lec);
          const all = lec.segments.every(x => segDone(x.id));
          toast(all ? t("lectureDone") : t("savedOk"));
        }
      },
      onError: fail,
    },
  });
}

async function sendAnswer(lec, target) {
  const text = $("#answer").value.trim();
  if (!text) return $("#answer").focus();
  const btn = $("#send");
  btn.disabled = true; btn.textContent = t("sending");
  const lecs = target.kind === "module" ? moduleOf(lec.id).lectures.map(lecture) : [lec];
  const points = lecs.flatMap(l => l.segments.flatMap(s => s.points.en));
  try {
    const r = await api("/api/answer", { ref: target.ref, question: tr(target.text), text, points });
    showResult(r);
  } catch (e) {
    $("#result").innerHTML = `<div class="alert">${esc(t("error", { e: e.message }))}</div>`;
  } finally {
    btn.disabled = false; btn.textContent = t("send");
  }
}
function showResult(r) {
  const box = $("#result");
  if (!r.sent && r.copy) {
    box.innerHTML = `<div class="small muted">${esc(t("noKey"))}</div><pre class="feedback" style="max-height:160px;overflow:auto">${esc(r.copy)}</pre>
      <button class="btn ghost sm" id="copyg">${esc(t("copy"))}</button>`;
    $("#copyg").onclick = e => copyText(r.copy, e.target);
    return;
  }
  const chip = r.verdict === "pass" ? `<span class="chip green">${esc(t("pass"))}</span>` : r.verdict === "not_yet" ? `<span class="chip orange">${esc(t("notYet"))}</span>` : "";
  const body = (r.feedback || "").replace(/^VERDICT:.*\n?/i, "").trim();
  box.innerHTML = `<div style="display:flex;flex-direction:column;gap:8px">${chip}<pre class="feedback">${esc(body)}</pre></div>`;
}
async function showLastAnswer(ref) {
  try {
    const rows = await api("/api/answers?ref=" + encodeURIComponent(ref));
    const last = rows.find(r => r.feedback);
    if (last && !$("#result").innerHTML) showResult({ sent: true, verdict: last.verdict, feedback: last.feedback });
  } catch (e) {}
}

// ---------- Assignment ----------
let HW = null;
async function renderHW(id, params) {
  HW = await api("/api/assignment/" + encodeURIComponent(id));
  const a = HW.assignment;
  const open = !HW.days || HW.days >= 0;
  renderBar(`<strong>${esc(a.name)} · ${esc(tr(a.title))}</strong> <span class="chip ${open ? "orange" : "orange"}" title="${esc(t("dueOn", { d: shortDate(HW.due) }))}">${esc(dueText(HW.days))}</span>`);
  const q = store.get("q." + id);
  if (!q && params.get("q")) store.set("q." + id, { q: params.get("q"), start: null, snooze: 0 });
  const starter = a.materials.find(m => m.starter);
  const testFile = starter ? "test_" + starter.label : null;
  const promptOpen = store.get("promptOpen") !== false;

  const concepts = a.concepts.map(c => {
    const st = (HW.mastery[c.en] || {}).status || "pending";
    return `<div class="concept"><div class="c">${esc(tr(c))}</div><div class="seg3" role="group" aria-label="${esc(tr(c))}">
      ${["passed", "retest", "pending"].map(k => `<button class="${k}" data-concept="${esc(c.en)}" data-status="${k}" aria-pressed="${st === k}">${esc(t(k))}</button>`).join("")}</div></div>`;
  }).join("");
  const nPassed = a.concepts.filter(c => (HW.mastery[c.en] || {}).status === "passed").length;

  const stuck = HW.stuck.length ? `<ul class="list">${HW.stuck.map(s => `<li><span>${esc(s.question)}</span><span class="muted">${esc(t("min", { n: Math.round(s.minutes) }))}</span>
      <span class="grow small muted">${esc(s.description || "")}</span>
      ${s.resolved_at ? `<span class="chip green">${esc(t("resolvedOn"))}</span>` : `<button class="btn ghost sm" data-resolve="${s.id}">${esc(t("resolve"))}</button>`}</li>`).join("")}</ul>`
    : `<div class="small muted">${esc(t("noStuck"))}</div>`;

  $("#app").innerHTML = `<main>
    <section class="col-main" style="flex-basis:480px">
      <div class="card">
        <h2>${esc(t("materials"))}</h2>
        <div class="links">${a.materials.map(m => `<a href="${esc(m.url)}" target="_blank" rel="noopener">${esc(m.label)}</a>`).join("")}</div>
        <div class="row"><button class="btn ghost sm" id="dl">${esc(t("saveLocal"))}</button>
          <span class="small muted" style="word-break:break-all">${esc(t("folder"))}: <code>${esc(HW.folder)}</code></span></div>
        ${HW.files.length ? `<div class="small muted">${HW.files.map(esc).join(" · ")}</div>` : ""}
      </div>
      <div class="card" id="qcard"></div>
      <div class="card">
        <div class="between"><h2>${esc(t("mastery"))}</h2><div class="small muted">${nPassed} / ${a.concepts.length}</div></div>
        <div style="display:flex;flex-direction:column;gap:6px" id="concepts">${concepts}</div>
        <div class="small muted">${esc(t("masteryHint"))}</div>
      </div>
      ${a.kind === "programming" ? `<div class="card"><div class="between"><h2>${esc(t("tests"))}</h2><button class="btn ghost sm" id="runtests">${esc(t("runTests"))}</button></div>
        <div id="testout">${HW.files.includes(testFile) ? "" : `<div class="small muted">${esc(t("noTests", { f: testFile }))}</div>`}</div></div>` : ""}
      <div class="card"><h2>${esc(t("stuckLog"))}</h2>${stuck}</div>
    </section>
    <aside class="col-side" style="flex-basis:420px">
      <div class="card">
        <div class="between" style="align-items:center">
          <div style="display:flex;flex-direction:column;gap:2px"><h2>${esc(t("aiPrompt"))}</h2><div class="small muted">${esc(t("promptSub"))}</div></div>
          <button class="btn ghost sm" id="toggleprompt" aria-expanded="${promptOpen}" aria-controls="prompttext">${esc(promptOpen ? t("hide") : t("show"))}</button>
        </div>
        <pre class="prompt ${promptOpen ? "" : "hidden"}" id="prompttext">${esc(HW.prompt[L])}</pre>
        <button class="btn" id="copyprompt">${esc(t("copy"))}</button>
      </div>
    </aside></main>`;

  $("#dl").onclick = async e => {
    e.target.disabled = true;
    try {
      const r = await api("/api/assignment/" + id + "/download", {});
      toast(r.saved.length ? t("saved", { f: r.saved.join(", ") }) : t("nothingNew"));
      renderHW(id, new URLSearchParams());
    } catch (err) { toast(t("error", { e: err.message })); e.target.disabled = false; }
  };
  $("#concepts").onclick = async e => {
    const b = e.target.closest("[data-status]");
    if (!b) return;
    await api("/api/mastery", { assignment_id: id, concept: b.dataset.concept, status: b.dataset.status });
    await load();
    renderHW(id, new URLSearchParams());
  };
  $("#app").querySelectorAll("[data-resolve]").forEach(b => b.onclick = async () => {
    await api("/api/stuck/resolve", { id: Number(b.dataset.resolve) });
    await load(); renderHW(id, new URLSearchParams());
  });
  $("#toggleprompt").onclick = e => {
    const pre = $("#prompttext"), now = pre.classList.toggle("hidden");
    store.set("promptOpen", !now);
    e.target.textContent = now ? t("show") : t("hide");
    e.target.setAttribute("aria-expanded", String(!now));
  };
  $("#copyprompt").onclick = e => copyText(HW.prompt[L], e.target);
  if ($("#runtests")) $("#runtests").onclick = async e => {
    const b = e.target; b.disabled = true; b.textContent = t("running");
    try {
      const r = await api("/api/assignment/" + id + "/test", {});
      $("#testout").innerHTML = !r.ran ? `<div class="small muted">${esc(t("noTests", { f: testFile }))}</div>`
        : `<span class="chip ${r.ok ? "green" : "orange"}">${esc(r.ok ? t("testsOk", { n: r.count }) : t("testsFail", { s: r.summary || "?" }))}</span><pre class="output">${esc(r.output)}</pre>`;
    } catch (err) { $("#testout").innerHTML = `<div class="alert">${esc(t("error", { e: err.message }))}</div>`; }
    b.disabled = false; b.textContent = t("runTests");
  };
  renderQuestion();
}

// Per-question timer: after `stuck_minutes`, suggest logging a stuck point and moving on.
function qState() { return store.get("q." + view.id) || { q: "", start: null, snooze: 0 }; }
function renderQuestion() {
  const box = $("#qcard");
  if (!box) return;
  const st = qState();
  box.innerHTML = `<h2>${esc(t("qTimer"))}</h2>
    <div class="row">
      <label class="f" style="flex:1;min-width:140px">${esc(t("qLabel"))}<input type="text" id="qname" value="${esc(st.q)}" placeholder="${esc(t("qPlaceholder"))}" ${st.start ? "disabled" : ""}></label>
      <div class="qtime" id="qtime">${st.start ? mmss((Date.now() - st.start) / 1000) : "0:00"}</div>
    </div>
    <div id="qalert"></div>
    <div class="row">
      ${st.start ? `<button class="btn sm" id="qdone">${esc(t("qDone"))}</button><button class="btn ghost sm" id="qstuck">${esc(t("qStuck"))}</button>`
        : `<button class="btn sm" id="qstart">${esc(t("qStart"))}</button>`}
    </div>`;
  if ($("#qstart")) $("#qstart").onclick = () => {
    const q = $("#qname").value.trim();
    if (!q) return $("#qname").focus();
    store.set("q." + view.id, { q, start: Date.now(), snooze: 0 });
    renderQuestion();
  };
  if ($("#qdone")) $("#qdone").onclick = () => finishQuestion("done");
  if ($("#qstuck")) $("#qstuck").onclick = () => finishQuestion("stuck");
  tickQuestion();
}
async function finishQuestion(outcome) {
  const st = qState(), minutes = (Date.now() - st.start) / 60000;
  await api("/api/attempt", { assignment_id: view.id, question: st.q, minutes: Math.round(minutes * 10) / 10, outcome });
  if (outcome === "stuck") {
    await api("/api/stuck", { ref: view.id, question: st.q, minutes: Math.round(minutes), description: "" });
  } else {
    for (const s of HW.stuck.filter(x => !x.resolved_at && x.question === st.q)) await api("/api/stuck/resolve", { id: s.id });
  }
  store.set("q." + view.id, null);
  await load();
  renderHW(view.id, new URLSearchParams());
}
function tickQuestion() {
  const st = qState(), el = $("#qtime");
  if (!el || !st.start) return;
  const min = (Date.now() - st.start) / 60000;
  el.textContent = mmss(min * 60);
  const limit = S.settings.stuck_minutes + (st.snooze || 0);
  const box = $("#qalert");
  if (S.settings.focus && min >= limit) {
    if (!box.innerHTML) {
      box.innerHTML = `<div class="alert" role="alert"><div>${esc(t("stuckAlert", { n: Math.floor(min), q: st.q }))}</div>
        <div class="row"><button class="btn sm" id="qlog">${esc(t("logSkip"))}</button><button class="btn ghost sm" id="qkeep">${esc(t("keepGoing"))}</button></div></div>`;
      $("#qlog").onclick = () => finishQuestion("stuck");
      $("#qkeep").onclick = () => { st.snooze = Math.ceil(min) - S.settings.stuck_minutes + 5; store.set("q." + view.id, st); box.innerHTML = ""; };
    }
  } else if (box.innerHTML) box.innerHTML = "";
}

// ---------- Settings ----------
function renderSettings() {
  renderBar(`<strong>${esc(t("settings"))}</strong>`);
  const ai = S.ai, st = S.settings;
  const provider = ai.provider || "anthropic";
  $("#app").innerHTML = `<main><section class="col-main">
    <form class="card" id="aiform">
      <h2>${esc(t("aiSection"))}</h2>
      <div class="grid2">
        <label class="f">${esc(t("provider"))}<select name="provider">${Object.entries(ai.providers).map(([k, v]) => `<option value="${k}" ${k === provider ? "selected" : ""}>${esc(v.label)}</option>`).join("")}</select></label>
        <label class="f">${esc(t("model"))}<input type="text" name="model" value="${esc(ai.model || ai.providers[provider].default_model)}"></label>
      </div>
      <label class="f">${esc(t("apiKey"))}<input type="password" name="api_key" autocomplete="off" placeholder="${esc(ai.has_key ? ai.key_hint : "")}"></label>
      <div class="small muted">${esc(ai.has_key ? t("keyStored", { h: ai.key_hint }) : t("keyNone"))} ${esc(t("keyNote"))}</div>
      <div class="row"><button class="btn sm" type="submit">${esc(t("save"))}</button>${ai.has_key ? `<button class="btn ghost sm" type="button" id="clearkey">${esc(t("clearKey"))}</button>` : ""}</div>
    </form>
    <form class="card" id="studyform">
      <h2>${esc(t("studySection"))}</h2>
      <div class="grid2">
        <label class="f">${esc(t("pace"))}<select name="pace">${[2, 3].map(n => `<option ${n === st.pace ? "selected" : ""}>${n}</option>`).join("")}</select></label>
        <label class="f">${esc(t("startDate"))}<input type="date" name="start_date" value="${esc(st.start_date)}"></label>
        <label class="f">${esc(t("sessionDefault"))}<input type="number" name="session_default" min="10" max="120" value="${st.session_default}"></label>
        <label class="f">${esc(t("breakEvery"))}<input type="number" name="break_every" min="10" max="90" value="${st.break_every}"></label>
        <label class="f">${esc(t("breakLen"))}<input type="number" name="break_len" min="1" max="30" value="${st.break_len}"></label>
        <label class="f">${esc(t("stuckMinutes"))}<input type="number" name="stuck_minutes" min="5" max="120" value="${st.stuck_minutes}"></label>
      </div>
      <div class="row"><button class="btn sm" type="submit">${esc(t("save"))}</button></div>
    </form>
  </section><aside class="col-side">
    <div class="card"><h2>${esc(t("calendar"))}</h2><div class="small muted">${esc(t("calendarNote"))}</div>
      <a class="btn ghost sm" href="/api/calendar.ics" download>${esc(t("download"))}</a></div>
  </aside></main>`;

  $("#aiform").provider.onchange = e => { $("#aiform").model.value = ai.providers[e.target.value].default_model; };
  $("#aiform").onsubmit = async e => {
    e.preventDefault();
    const f = e.target;
    try {
      await api("/api/config", { provider: f.provider.value, model: f.model.value, api_key: f.api_key.value });
      await load(); renderSettings(); toast(t("savedOk"));
    } catch (err) { toast(t("error", { e: err.message })); }
  };
  if ($("#clearkey")) $("#clearkey").onclick = async () => {
    await api("/api/config", { provider, clear_key: true }); await load(); renderSettings();
  };
  $("#studyform").onsubmit = async e => {
    e.preventDefault();
    const f = e.target, n = k => Number(f[k].value);
    try {
      await api("/api/settings", { pace: n("pace"), start_date: f.start_date.value, session_default: n("session_default"),
        break_every: n("break_every"), break_len: n("break_len"), stuck_minutes: n("stuck_minutes") });
      await load(); renderSettings(); toast(t("savedOk"));
    } catch (err) { toast(t("error", { e: err.message })); }
  };
}

// ---------- router ----------
async function load() {
  S = await api("/api/state");
  L = S.settings.lang === "zh" ? "zh" : "en";
  document.documentElement.lang = L === "zh" ? "zh-CN" : "en";
  document.title = t("brand");
}
function render() {
  const [path, qs] = (location.hash.replace(/^#/, "") || "/").split("?");
  const params = new URLSearchParams(qs || "");
  const parts = path.split("/").filter(Boolean);
  if (parts[0] !== "lesson") player = null;
  if (parts[0] === "lesson" && parts[1]) { view = { page: "lesson", id: parts[1] }; renderLesson(parts[1], params); }
  else if (parts[0] === "hw" && parts[1]) { view = { page: "hw", id: parts[1] }; renderHW(parts[1], params).catch(() => (location.hash = "#/")); }
  else if (parts[0] === "settings") { view = { page: "settings" }; renderSettings(); }
  else { view = { page: "today" }; renderToday(); }
  renderOverlay();
}
window.addEventListener("hashchange", async () => { await load(); render(); });
(async () => {
  try { await load(); render(); }
  catch (e) { $("#app").innerHTML = `<main><div class="card">Could not reach the local server: ${esc(e.message)}</div></main>`; }
  setInterval(tick, 1000);
})();
