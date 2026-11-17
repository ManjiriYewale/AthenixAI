"use strict";
/* Chat widget. Talks only to /api/v1/chat. Server keeps no private data; this page sends the profile each turn. */
const chat = {profile: {}, pending: null, count: 0, skipped: []};
const $c = (s) => document.querySelector(s);

function say(who, text) { const m = el("div", `m ${who}`, text); $c("#msgs").append(m); m.scrollIntoView({block: "end"}); return m; }

function setQuick(items) {
  const q = $c("#quick"); q.replaceChildren();
  for (const it of items) { const b = el("button", "", it); b.type = "button"; b.onclick = () => send(it); q.append(b); }
}

function syncForm(profile) {
  let changed = false;
  for (const [k, v] of Object.entries(profile)) {
    const f = $("#f").elements[k];
    if (f && String(f.value) !== String(v) && (v !== "Other state")) { f.value = v; changed = true; }
  }
  if (changed) $("#f").dispatchEvent(new Event("input", {bubbles: true}));
}

function decorate(m, r) {
  if (r.schemes.length) {
    const d = el("details"); d.append(el("summary", "", `Schemes checked (${r.schemes.length})`));
    for (const s of r.schemes) {
  const icon = s.status === "Eligible" ? "✓" : s.status === "Not eligible" ? "✕" : "⚠";
  d.append(el("div", "", `${icon} ${s.name}: ${s.status}`));
}
    m.append(d);
  }
  if (r.citations.length) {
    const d = el("details"); d.append(el("summary", "", `Sources (${r.citations.length})`));
    for (const c of r.citations) d.append(el("p", "meta", `${c.source}, page ${c.page}: “${c.snippet}”`));
    m.append(d);
  }
  const d = el("details"); d.append(el("summary", "", "How I worked this out (agents)"));
  for (const t of r.trace) d.append(el("div", "", `${t.agent}: ${t.action}`));
  m.append(d);
  for (const w of r.warnings) m.append(el("div", "warn", "⚑ " + w));
}

async function send(text) {
  text = text.trim(); if (!text) return;
  say("me", text); $c("#chat-input").value = ""; setQuick([]);
  const wait = say("bot typing", "Thinking");
  const profile = {...chat.profile, ...(typeof readForm === "function" ? readForm().profile : {})};
  try {
    const res = await fetch(API + "/chat", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message: text, profile, pending_field: chat.pending, clarification_count: chat.count, skipped_fields: chat.skipped})});
    const r = await res.json();
    if (!res.ok) throw new Error(r.error?.message || "Request failed");
    Object.assign(chat, {profile: r.profile, pending: r.pending_field, count: r.clarification_count, skipped: r.skipped_fields});
    wait.className = "m bot"; wait.textContent = r.reply; decorate(wait, r);
    setQuick(r.question ? [...r.question.choices, "Skip"] : ["What documents do I need?", "How do I apply?"]);
    syncForm(r.profile);
  } catch (e) { wait.className = "m bot"; wait.textContent = "✖ Sorry, I could not reach the assistant: " + e.message; }
}

function toggle(open) {
  $c("#chat").hidden = !open; $c("#chat-open").hidden = open; $c("#chat-open").setAttribute("aria-expanded", String(open));
  if (open) { $c("#chat-input").focus(); if (!$c("#msgs").children.length) { say("bot", "Hi! I can find schemes, check your eligibility condition by condition, list documents and show application steps from the sources. Try a suggestion below."); setQuick(["Find schemes for me", "I am 21, a student in Maharashtra", "Am I eligible for a scholarship?"]); } }
}
$c("#chat-open").onclick = () => toggle(true);
$c("#chat-close").onclick = () => toggle(false);
$c("#chat-form").onsubmit = (e) => { e.preventDefault(); send($c("#chat-input").value); };
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$c("#chat").hidden) toggle(false); });
