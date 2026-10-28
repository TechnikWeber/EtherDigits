"use strict";

// ---------------------------------------------------------------- texts
const T = {
  de: {
    logout: "Abmelden", login: "Anmelden", password: "Passwort",
    tab_overview: "Übersicht", tab_messages: "Nachrichten", tab_schedules: "Zeitpläne", tab_log: "Protokoll", tab_settings: "Einstellungen",
    now: "Jetzt", next_tx: "Nächste Sendungen", queue: "Warteschlange", recent: "Letzte Sendungen", new_message: "Neue Nachricht",
    on_air: "Auf Sendung", idle: "Bereit", on_air_detail: "{schedule}, seit {since} UTC, {duration} s",
    output_silent: "Noch keine Funkausgabe (kommt mit Stufe 4). Sendungen laufen in Echtzeit und werden aufgezeichnet.",
    no_next: "Kein Zeitplan aktiv.", in: "in {t}", queued_n: "{n} wartend",
    no_password_local: "Es ist kein Passwort gesetzt. Deshalb kann nur dieser Rechner die Oberfläche öffnen. Setze ein Passwort unter Einstellungen, bevor du die Station im Netz erreichbar machst.",
    mode_groups: "Fertige Zahlengruppen", mode_text: "Klartext, auf der Station verschlüsseln",
    groups_label: "Zahlengruppen (erste Gruppe = Seitennummer)", groups_info: "<b>{n}</b> Gruppen", groups_bad: "Nur Ziffern; {n} Ziffern füllen keine Fünfergruppen.",
    station_enc_warn: "Der Klartext wird sofort verschlüsselt und nicht gespeichert. Aber die Station hat dafür das Heft. Wer die Station hat, kann alle Nachrichten mit den restlichen Seiten lesen. Sicherer ist das Offline-Werkzeug.",
    plain_text: "Klartext", pad: "Heft auf der Station",
    priority: "Priorität", prio_0: "normal", prio_1: "hoch", prio_2: "dringend",
    transmissions: "Anzahl Sendungen", transmissions_hint: "In wie vielen Sendungen die Nachricht vorkommt. Wie oft sie innerhalb einer Sendung wiederholt wird, steht im Zeitplan.",
    schedule: "Zeitplan", any_schedule: "beliebiger Zeitplan",
    not_before: "Nicht vor (UTC)", expires: "Verfällt (UTC)", label: "Notiz (nur hier sichtbar)",
    label_hint: "Schreib hier keinen Klartext hinein.",
    burn: "Nach der letzten Sendung die Zahlen von der Station löschen",
    queue_it: "In die Warteschlange", queued_ok: "Nachricht {id} wartet auf ihre Sendung.",
    filter_queued: "Wartend", filter_all: "Alle", no_messages: "Keine Nachrichten.",
    col_id: "Nr.", col_label: "Notiz", col_groups: "Gruppen", col_prio: "Prio", col_sched: "Zeitplan", col_sent: "Gesendet", col_status: "Status", col_expires: "Verfällt",
    st_queued: "wartend", st_done: "gesendet", st_expired: "verfallen", st_cancelled: "abgebrochen",
    cancel_msg: "Abbrechen", delete: "Löschen", burned: "gelöscht",
    new_schedule: "Neuer Zeitplan", edit: "Bearbeiten", preview: "Probe anhören", transmit_now: "Jetzt senden", test_tx: "Testsendung",
    enabled: "Aktiv", disabled: "aus", when: "Wann", kind_times: "Feste Uhrzeiten", kind_interval: "Alle N Minuten",
    times: "Uhrzeiten (UTC, mit Komma getrennt)", interval_minutes: "Abstand in Minuten", offset_minutes: "Versatz in Minuten",
    weekdays: "Wochentage", days: ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
    voice: "Stimme", effect: "Klang", effect_none: "klar", effect_radio: "Kurzwelle",
    callsign: "Kennung", max_messages: "Nachrichten pro Sendung",
    filler: "Wenn nichts wartet", filler_random: "Füllmeldung aus Zufallsgruppen (empfohlen)", filler_null: "„Keine Meldung“ senden", filler_skip: "gar nicht senden",
    filler_min: "Füllmeldung: mindestens Gruppen", filler_max: "höchstens Gruppen",
    filler_skip_warn: "Wer zuhört, merkt dann, wann es etwas zu sagen gibt.",
    format: "Ablauf der Sendung", interval_signal: "Pausenzeichen", interval_repeats: "Pausenzeichen wie oft",
    callsign_repeats: "Kennung wie oft", message_repeats: "Nachricht wie oft vorlesen",
    digit_gap: "Pause Ziffern (s)", group_gap: "Pause Gruppen (s)", section_gap: "Pause Abschnitte (s)",
    announce_count: "Gruppenzahl ansagen", group_twice: "Jede Gruppe zweimal lesen", end_tone: "Schlusston",
    iv_melody: "Melodie", iv_beeps: "Pieptöne", iv_none: "keins",
    name: "Name", save: "Speichern", cancel: "Abbrechen", create: "Anlegen",
    every_day: "täglich", every_n: "alle {n} min", offset: "+{n} min",
    next_runs: "Nächste: {list}", none_planned: "nichts geplant",
    delete_sched_confirm: "Zeitplan „{name}“ löschen?",
    tx_started: "Sendung gestartet.", rendering: "Wird erzeugt …",
    col_time: "Zeit (UTC)", col_kind: "Art", col_dur: "Dauer", kind_message: "Nachricht", kind_filler: "Füllmeldung", kind_null: "keine Meldung", kind_test: "Test",
    st_ok: "ok", st_error: "Fehler", st_busy: "belegt", no_log: "Noch nichts gesendet.", recording: "Aufnahme",
    pw_current: "Aktuelles Passwort", pw_new: "Neues Passwort (mindestens 10 Zeichen)", pw_again: "Noch einmal",
    pw_hint_none: "Noch kein Passwort gesetzt.", pw_hint_set: "Ein Passwort ist gesetzt.", pw_mismatch: "Die Passwörter stimmen nicht überein.", pw_ok: "Passwort gespeichert.",
    station_settings: "Station", discreet: "Diskretes Protokoll",
    discreet_hint: "Das Protokoll hält dann nur fest, dass gesendet wurde, nicht ob es eine echte Nachricht oder eine Füllmeldung war. Aufnahmen werden nicht gespeichert.",
    keep_days: "Aufnahmen behalten (Tage)", lead: "Vorlauf zum Erzeugen (s)",
    station_enc: "Verschlüsseln auf der Station erlauben", station_enc_hint: "Bequem, aber die Hefte liegen dann auf der Station. Aus ist sicherer.",
    saved: "Gespeichert.",
    tokens: "API-Tokens", tokens_hint: "Ein Token kann nur Nachrichten einreichen. Die Warteschlange, das Protokoll und die Einstellungen sieht es nicht.",
    token_name: "Name (wer es bekommt)", token_shown_once: "Nur jetzt sichtbar, kopiere es:", revoke: "Widerrufen", no_tokens: "Keine Tokens.",
    last_used: "zuletzt {t}", never: "nie",
    pads: "Hefte auf der Station", pads_hint: "Nur nötig, wenn die Station selbst verschlüsseln soll.",
    pad_upload: "Heft hochladen", pad_uploaded: "Heft gespeichert.", no_pads: "Keine Hefte.", pages_free: "{free} von {total} Seiten frei",
    delete_pad_confirm: "Heft „{name}“ von der Station löschen?",
    err_network: "Keine Verbindung zur Station.",
    stop: "STOPP", emergency_stop: "Notaus", release: "Sender freigeben",
    blocked_banner: "Notaus ausgelöst: Der Sender ist gesperrt, geplante Sendungen fallen aus. Gib ihn in der Übersicht wieder frei.",
    out_silent: "Keine Funkausgabe: Sendungen laufen in Echtzeit ohne Ton und werden aufgezeichnet.", out_soundcard: "Ausgabe auf die Soundkarte des Funkgeräts.",
    out_monitor: "Mithören am Stationsrechner ist an.",
    output_title: "Ausgabe und Funkgerät", output_mode: "Ausgabe", mode_silent: "keine (nur Echtzeit und Aufnahme)", mode_soundcard: "Soundkarte zum Funkgerät",
    device: "Soundkarte", default_device: "Systemstandard", gain: "Pegel (dB)",
    monitor: "Mithören am Stationsrechner", monitor_hint: "Spielt dieselbe Sendung parallel auf einem zweiten Gerät ab, zum Beispiel auf den eingebauten Lautsprechern. Standardmäßig aus.",
    monitor_device: "Gerät zum Mithören",
    ptt: "Sendetaste (PTT)", ptt_none: "VOX (das Funkgerät schaltet selbst)", ptt_serial: "Serielle Leitung (RTS/DTR, z. B. Digirig)", ptt_cat: "CAT über rigctld",
    serial_port: "Serieller Port", serial_line: "Leitung", serial_invert: "Umgekehrt (Leitung aus = senden)",
    ptt_lead: "PTT-Vorlauf (ms)", ptt_tail: "PTT-Nachlauf (ms)",
    cat: "Frequenz und Betriebsart per CAT setzen (Hamlib rigctld)", cat_hint: "rigctld muss laufen, z. B.: rigctld -m 3073 -r /dev/ttyUSB0. Die Frequenz steht dann im Zeitplan.",
    rig_host: "rigctld-Adresse", rig_port: "Port", max_tx: "Längste erlaubte Sendung (s)",
    test_tone: "Testton 3 s", test_cat: "CAT testen", cat_ok: "Funkgerät antwortet: {f} kHz", tone_started: "Testton läuft.",
    frequency: "Frequenz (kHz, 0 = nicht ändern)", frequency_hint: "Wird nur gesetzt, wenn CAT in den Einstellungen an ist.", rig_mode: "Betriebsart", rig_mode_keep: "nicht ändern",
    cw_ident: "Morse-Kennung am Schluss", cw_wpm: "Tempo (WpM)",
    st_blocked: "gesperrt", st_stopped: "abgebrochen",
  },
  en: {
    logout: "Log out", login: "Log in", password: "Password",
    tab_overview: "Overview", tab_messages: "Messages", tab_schedules: "Schedules", tab_log: "Log", tab_settings: "Settings",
    now: "Now", next_tx: "Next transmissions", queue: "Queue", recent: "Recent transmissions", new_message: "New message",
    on_air: "On air", idle: "Ready", on_air_detail: "{schedule}, since {since} UTC, {duration} s",
    output_silent: "No radio output yet (comes with stage 4). Transmissions run in real time and are recorded.",
    no_next: "No schedule is active.", in: "in {t}", queued_n: "{n} waiting",
    no_password_local: "No password is set, so only this computer can open the interface. Set a password under Settings before you make the station reachable on a network.",
    mode_groups: "Finished digit groups", mode_text: "Plain text, encrypt on the station",
    groups_label: "Digit groups (first group = page number)", groups_info: "<b>{n}</b> groups", groups_bad: "Digits only; {n} digits do not fill groups of five.",
    station_enc_warn: "The plain text is encrypted at once and never stored. But the station holds the pad for it, and whoever has the station can read every message sent with the remaining pages. The offline tool is safer.",
    plain_text: "Plain text", pad: "Pad on the station",
    priority: "Priority", prio_0: "normal", prio_1: "high", prio_2: "urgent",
    transmissions: "Number of transmissions", transmissions_hint: "In how many transmissions the message goes out. How often it is repeated within one transmission is set in the schedule.",
    schedule: "Schedule", any_schedule: "any schedule",
    not_before: "Not before (UTC)", expires: "Expires (UTC)", label: "Note (only visible here)",
    label_hint: "Do not put plain text here.",
    burn: "Delete the digits from the station after the last transmission",
    queue_it: "Add to queue", queued_ok: "Message {id} is waiting for its transmission.",
    filter_queued: "Waiting", filter_all: "All", no_messages: "No messages.",
    col_id: "No.", col_label: "Note", col_groups: "Groups", col_prio: "Prio", col_sched: "Schedule", col_sent: "Sent", col_status: "Status", col_expires: "Expires",
    st_queued: "waiting", st_done: "sent", st_expired: "expired", st_cancelled: "cancelled",
    cancel_msg: "Cancel", delete: "Delete", burned: "deleted",
    new_schedule: "New schedule", edit: "Edit", preview: "Listen", transmit_now: "Transmit now", test_tx: "Test transmission",
    enabled: "Active", disabled: "off", when: "When", kind_times: "Fixed times", kind_interval: "Every N minutes",
    times: "Times (UTC, comma separated)", interval_minutes: "Interval in minutes", offset_minutes: "Offset in minutes",
    weekdays: "Weekdays", days: ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"],
    voice: "Voice", effect: "Sound", effect_none: "clean", effect_radio: "shortwave",
    callsign: "Callsign", max_messages: "Messages per transmission",
    filler: "When nothing is waiting", filler_random: "Filler of random groups (recommended)", filler_null: "Send “no message”", filler_skip: "Do not transmit",
    filler_min: "Filler: at least groups", filler_max: "at most groups",
    filler_skip_warn: "Listeners will then notice when there is something to say.",
    format: "Transmission layout", interval_signal: "Interval signal", interval_repeats: "Interval signal how often",
    callsign_repeats: "Callsign how often", message_repeats: "Read message how often",
    digit_gap: "Pause digits (s)", group_gap: "Pause groups (s)", section_gap: "Pause sections (s)",
    announce_count: "Announce group count", group_twice: "Read every group twice", end_tone: "End tone",
    iv_melody: "melody", iv_beeps: "beeps", iv_none: "none",
    name: "Name", save: "Save", cancel: "Cancel", create: "Create",
    every_day: "daily", every_n: "every {n} min", offset: "+{n} min",
    next_runs: "Next: {list}", none_planned: "nothing planned",
    delete_sched_confirm: "Delete schedule “{name}”?",
    tx_started: "Transmission started.", rendering: "Rendering …",
    col_time: "Time (UTC)", col_kind: "Kind", col_dur: "Length", kind_message: "message", kind_filler: "filler", kind_null: "no message", kind_test: "test",
    st_ok: "ok", st_error: "error", st_busy: "busy", no_log: "Nothing sent yet.", recording: "Recording",
    pw_current: "Current password", pw_new: "New password (at least 10 characters)", pw_again: "Again",
    pw_hint_none: "No password set yet.", pw_hint_set: "A password is set.", pw_mismatch: "The passwords do not match.", pw_ok: "Password saved.",
    station_settings: "Station", discreet: "Discreet log",
    discreet_hint: "The log then only records that something was sent, not whether it was a real message or filler. No recordings are kept.",
    keep_days: "Keep recordings (days)", lead: "Rendering lead time (s)",
    station_enc: "Allow encrypting on the station", station_enc_hint: "Convenient, but the pads then live on the station. Off is safer.",
    saved: "Saved.",
    tokens: "API tokens", tokens_hint: "A token can only submit messages. It cannot see the queue, the log or the settings.",
    token_name: "Name (who gets it)", token_shown_once: "Shown only now, copy it:", revoke: "Revoke", no_tokens: "No tokens.",
    last_used: "last used {t}", never: "never",
    pads: "Pads on the station", pads_hint: "Only needed when the station itself is to encrypt.",
    pad_upload: "Upload pad", pad_uploaded: "Pad stored.", no_pads: "No pads.", pages_free: "{free} of {total} pages unused",
    delete_pad_confirm: "Delete pad “{name}” from the station?",
    err_network: "No connection to the station.",
    stop: "STOP", emergency_stop: "Emergency stop", release: "Release transmitter",
    blocked_banner: "Emergency stop: the transmitter is locked and scheduled transmissions are skipped. Release it on the overview.",
    out_silent: "No radio output: transmissions run in real time without sound and are recorded.", out_soundcard: "Output to the radio's sound card.",
    out_monitor: "Monitoring on the station computer is on.",
    output_title: "Output and radio", output_mode: "Output", mode_silent: "none (real time and recording only)", mode_soundcard: "sound card to the radio",
    device: "Sound card", default_device: "system default", gain: "Level (dB)",
    monitor: "Monitor on the station computer", monitor_hint: "Plays the same transmission on a second device at the same time, for example the built-in speakers. Off by default.",
    monitor_device: "Monitor device",
    ptt: "Push to talk (PTT)", ptt_none: "VOX (the radio keys itself)", ptt_serial: "Serial line (RTS/DTR, e.g. Digirig)", ptt_cat: "CAT via rigctld",
    serial_port: "Serial port", serial_line: "Line", serial_invert: "Inverted (line off = transmit)",
    ptt_lead: "PTT lead (ms)", ptt_tail: "PTT tail (ms)",
    cat: "Set frequency and mode by CAT (Hamlib rigctld)", cat_hint: "rigctld must be running, e.g.: rigctld -m 3073 -r /dev/ttyUSB0. The frequency is then set per schedule.",
    rig_host: "rigctld address", rig_port: "Port", max_tx: "Longest allowed transmission (s)",
    test_tone: "Test tone 3 s", test_cat: "Test CAT", cat_ok: "The radio answers: {f} kHz", tone_started: "Test tone playing.",
    frequency: "Frequency (kHz, 0 = leave it)", frequency_hint: "Only set when CAT is switched on in the settings.", rig_mode: "Mode", rig_mode_keep: "leave it",
    cw_ident: "Morse identification at the end", cw_wpm: "Speed (wpm)",
    st_blocked: "locked", st_stopped: "stopped",
  },
};

// The station answers in English; the frequent answers are translated here.
const SERVER_ERRORS = {
  de: {
    "wrong password": "Falsches Passwort.",
    "too many wrong passwords; wait a minute": "Zu viele falsche Versuche. Warte eine Minute.",
    "the current password is wrong": "Das aktuelle Passwort stimmt nicht.",
    "the password needs at least 10 characters": "Das Passwort braucht mindestens 10 Zeichen.",
    "the password is too simple": "Das Passwort ist zu einfach.",
    "a transmission is on air": "Es läuft gerade eine Sendung.",
    "encrypting on the station is switched off in the settings": "Verschlüsseln auf der Station ist in den Einstellungen ausgeschaltet.",
    "groups (or text and pad) are needed": "Zahlengruppen fehlen.",
    "a pad with this name is already on the station": "Ein Heft mit diesem Namen liegt schon auf der Station.",
    "this schedule sends nothing when the queue is empty": "Dieser Zeitplan sendet nichts, solange die Warteschlange leer ist.",
    "the transmitter is locked (emergency stop)": "Der Sender ist gesperrt (Notaus).",
  },
};
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
let lang = "en";
const state = {session: null, status: null, schedules: [], voices: null, settings: null, pads: [], msgFilter: "queued", tab: "overview"};

function t(key, vars = {}) {
  let s = (T[lang] && T[lang][key]) ?? T.en[key] ?? key;
  if (typeof s !== "string") return s;
  for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v);
  return s;
}

function storeGet(k) { try { return localStorage.getItem(k); } catch { return null; } }
function storeSet(k, v) { try { localStorage.setItem(k, v); } catch { /* blocked storage is fine */ } }

// ---------------------------------------------------------------- api
class ApiError extends Error { constructor(status, msg) { super(msg); this.status = status; } }

async function api(method, path, data, raw = false) {
  const opts = {method, headers: {"X-EtherDigits": "1"}, credentials: "same-origin"};
  if (data !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(data); }
  let res;
  try { res = await fetch(path, opts); } catch { throw new ApiError(0, t("err_network")); }
  if (res.status === 401 && path !== "/api/login" && path !== "/api/password") { showLogin(); throw new ApiError(401, "login required"); }
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).error || msg; } catch { /* not JSON */ }
    msg = SERVER_ERRORS[lang]?.[msg] || msg;
    throw new ApiError(res.status, msg);
  }
  return raw ? res : res.json();
}

function note(id, text, cls = "") {
  const el = $(id);
  el.className = "note" + (cls ? " " + cls : "");
  el.textContent = text || "";
}

// ---------------------------------------------------------------- time
const pad2 = n => String(n).padStart(2, "0");
function utc(isoText, withDate = true) {
  if (!isoText) return "–";
  const d = new Date(isoText);
  const time = `${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())}`;
  return withDate ? `${d.getUTCFullYear()}-${pad2(d.getUTCMonth() + 1)}-${pad2(d.getUTCDate())} ${time}` : time;
}
function local(isoText) {
  if (!isoText) return "";
  return new Date(isoText).toLocaleString(lang, {weekday: "short", hour: "2-digit", minute: "2-digit"});
}
function countdown(isoText) {
  const s = Math.max(0, Math.round((new Date(isoText) - Date.now()) / 1000));
  if (s >= 86400) return `${Math.floor(s / 86400)} d ${Math.floor(s % 86400 / 3600)} h`;
  if (s >= 3600) return `${Math.floor(s / 3600)} h ${pad2(Math.floor(s % 3600 / 60))} min`;
  if (s >= 60) return `${Math.floor(s / 60)} min ${pad2(s % 60)} s`;
  return `${s} s`;
}
// datetime-local fields are read and written as UTC
const fieldToIso = v => v ? v + ":00Z" : null;

function tickClock() {
  const d = new Date();
  $("clock").textContent = `${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())}:${pad2(d.getUTCSeconds())} UTC`;
  if (state.status) renderNext();
}

// ---------------------------------------------------------------- language
function setLang(l) {
  lang = T[l] ? l : "en";
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-i18n]").forEach(el => { el.innerHTML = t(el.dataset.i18n); });
  document.querySelectorAll("[data-lang]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.lang === lang)));
  storeSet("etherdigits.lang", lang);
  if (state.session && state.session.logged_in) renderAll();
}

// ---------------------------------------------------------------- session
function showLogin() {
  $("login").hidden = false; $("app").hidden = true; $("logoutBtn").hidden = true;
  $("loginPassword").focus();
}

async function startApp() {
  state.session = await api("GET", "/api/session");
  if (!state.session.logged_in) { showLogin(); return; }
  $("login").hidden = true; $("app").hidden = false;
  $("logoutBtn").hidden = !state.session.password_set;
  renderBanner();
  startMeter();
  state.voices = await api("GET", "/api/voices");
  await Promise.all([loadStatus(), loadSchedules(), loadSettings()]);
  fillStaticSelects();
  showTab(storeGet("etherdigits.tab") || "overview");
}

$("loginForm").addEventListener("submit", async e => {
  e.preventDefault();
  note("loginMsg", "");
  try {
    await api("POST", "/api/login", {password: $("loginPassword").value});
    $("loginPassword").value = "";
    await startApp();
  } catch (err) { note("loginMsg", err.message, "bad"); }
});

$("logoutBtn").addEventListener("click", async () => { await api("POST", "/api/logout", {}); showLogin(); });

// ---------------------------------------------------------------- tabs
function showTab(name) {
  if (!document.querySelector(`[data-tab="${name}"]`)) name = "overview";
  state.tab = name;
  storeSet("etherdigits.tab", name);
  document.querySelectorAll("[role=tab]").forEach(b => b.setAttribute("aria-selected", String(b.dataset.tab === name)));
  document.querySelectorAll("[role=tabpanel]").forEach(s => { s.hidden = s.id !== "tab-" + name; });
  refreshTab();
}
document.querySelectorAll("[role=tab]").forEach(b => b.addEventListener("click", () => showTab(b.dataset.tab)));
document.querySelectorAll("[data-goto]").forEach(b => b.addEventListener("click", () => showTab(b.dataset.goto)));
document.querySelectorAll("[data-lang]").forEach(b => b.addEventListener("click", () => setLang(b.dataset.lang)));

async function refreshTab() {
  try {
    if (state.tab === "overview") { await loadStatus(); await loadRecent(); }
    if (state.tab === "messages") { await Promise.all([loadMessages(), loadPads()]); renderMsgForm(); }
    if (state.tab === "schedules") { await loadSchedules(); }
    if (state.tab === "log") { await loadLog(); }
    if (state.tab === "settings") { await Promise.all([loadSettings(), loadTokens(), loadPads(), loadOutput()]); renderSettings(); renderOutput(); }
  } catch (err) { if (err.status !== 401) console.warn(err); }
}

function renderAll() { renderStatus(); renderSchedules(); fillStaticSelects(); refreshTab(); }

// ---------------------------------------------------------------- banner, meter, emergency stop
function renderBanner() {
  const parts = [];
  if (state.status?.blocked) parts.push(`<div class="note bad">${esc(t("blocked_banner"))}</div>`);
  if (state.session && !state.session.password_set) parts.push(`<div class="note warn">${esc(t("no_password_local"))}</div>`);
  $("banner").innerHTML = parts.join("");
}

let meterSource = null;
function startMeter() {
  if (meterSource || typeof EventSource === "undefined") return;
  meterSource = new EventSource("/api/meter");
  meterSource.onmessage = e => { try { showMeter(JSON.parse(e.data)); } catch { /* ignore a broken frame */ } };
}

function showMeter(m) {
  for (const el of [$("meterTop"), $("meterBig")]) {
    el.style.setProperty("--lvl", `${(m.level * 100).toFixed(1)}%`);
    el.style.setProperty("--pk", `${(m.peak * 100).toFixed(1)}%`);
    el.classList.toggle("live", m.on_air);
    el.setAttribute("aria-valuenow", String(Math.round(m.level * 100)));
  }
  $("airDot").className = "dot " + (m.on_air ? "air" : "idle");
  $("stopTop").hidden = !m.on_air;
}

async function emergencyStop() {
  try { await api("POST", "/api/stop", {}); } finally { await loadStatus(); }
}
$("stopTop").addEventListener("click", emergencyStop);
$("stopBig").addEventListener("click", emergencyStop);
$("releaseBtn").addEventListener("click", async () => { await api("POST", "/api/release", {}); await loadStatus(); });

// ---------------------------------------------------------------- overview
async function loadStatus() { state.status = await api("GET", "/api/status"); renderStatus(); }

function renderStatus() {
  const s = state.status;
  if (!s) return;
  $("onAir").innerHTML = s.on_air
    ? `<h3>${esc(t("on_air"))}</h3><p class="muted">${esc(t("on_air_detail", {schedule: s.on_air.schedule, since: utc(s.on_air.started, false), duration: s.on_air.duration}))}</p>`
    : `<h3>${esc(t("idle"))}</h3>`;
  $("outputNote").textContent = (s.output === "silent" ? t("out_silent") : t("out_soundcard")) + (s.monitor ? " " + t("out_monitor") : "");
  $("queueCount").textContent = s.queue;
  $("stopBig").hidden = s.blocked;
  $("releaseBtn").hidden = !s.blocked;
  renderBanner();
  renderNext();
}

function renderNext() {
  const s = state.status;
  $("nextList").innerHTML = s.next.length
    ? s.next.slice(0, 6).map(n => `<li><span>${esc(n.schedule)}</span><span><span class="t">${utc(n.at, false)}</span> <span class="muted">${esc(local(n.at))} · ${esc(t("in", {t: countdown(n.at)}))}</span></span></li>`).join("")
    : `<li class="empty">${esc(t("no_next"))}</li>`;
}

async function loadRecent() {
  const entries = await api("GET", "/api/log?limit=6");
  $("recentLog").innerHTML = logTable(entries, false);
}

// ---------------------------------------------------------------- messages
let msgMode = "groups";

function renderMsgForm() {
  const allowed = state.settings && state.settings.station_encryption;
  $("msgModeSeg").hidden = !allowed;
  if (!allowed) msgMode = "groups";
  document.querySelectorAll("#msgModeSeg button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.mode === msgMode)));
  $("msgGroupsBox").hidden = msgMode !== "groups";
  $("msgTextBox").hidden = msgMode !== "text";
  const sel = $("msgSchedule"), keep = sel.value;
  sel.innerHTML = `<option value="">${esc(t("any_schedule"))}</option>` + state.schedules.map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join("");
  sel.value = keep;
  $("msgPad").innerHTML = state.pads.filter(p => !p.error).map(p => `<option value="${esc(p.name)}">${esc(p.name)} (${esc(t("pages_free", {free: p.unused, total: p.pages}))})</option>`).join("");
  updateGroupsInfo();
}
document.querySelectorAll("#msgModeSeg button").forEach(b => b.addEventListener("click", () => { msgMode = b.dataset.mode; renderMsgForm(); }));

function updateGroupsInfo() {
  const digits = $("msgGroups").value.replace(/[\s\-./,;]+/g, "");
  if (!digits) { $("msgGroupsInfo").innerHTML = ""; return; }
  const ok = /^[0-9]+$/.test(digits) && digits.length % 5 === 0;
  $("msgGroupsInfo").innerHTML = ok ? t("groups_info", {n: digits.length / 5}) : `<span style="color:var(--danger)">${esc(t("groups_bad", {n: digits.length}))}</span>`;
}
$("msgGroups").addEventListener("input", updateGroupsInfo);

$("msgForm").addEventListener("submit", async e => {
  e.preventDefault();
  note("msgMsg", "");
  const data = {
    priority: +$("msgPriority").value, transmissions: +$("msgTransmissions").value,
    schedule_id: $("msgSchedule").value ? +$("msgSchedule").value : null,
    not_before: fieldToIso($("msgNotBefore").value), expires: fieldToIso($("msgExpires").value),
    label: $("msgLabel").value, burn: $("msgBurn").checked,
  };
  if (msgMode === "text") { data.text = $("msgText").value; data.pad = $("msgPad").value; }
  else data.groups = $("msgGroups").value;
  try {
    const m = await api("POST", "/api/messages", data);
    note("msgMsg", t("queued_ok", {id: m.id}), "good");
    $("msgGroups").value = ""; $("msgText").value = ""; $("msgLabel").value = "";
    updateGroupsInfo();
    await Promise.all([loadMessages(), loadPads()]);
    renderMsgForm();
  } catch (err) { note("msgMsg", err.message, "bad"); }
});

document.querySelectorAll("#msgFilter button").forEach(b => b.addEventListener("click", () => {
  state.msgFilter = b.dataset.filter;
  document.querySelectorAll("#msgFilter button").forEach(x => x.setAttribute("aria-pressed", String(x === b)));
  loadMessages();
}));

async function loadMessages() {
  const list = await api("GET", "/api/messages" + (state.msgFilter ? "?status=" + state.msgFilter : ""));
  const names = Object.fromEntries(state.schedules.map(s => [s.id, s.name]));
  if (!list.length) { $("msgList").innerHTML = `<p class="empty">${esc(t("no_messages"))}</p>`; return; }
  const prio = ["", "high", "urgent"];
  $("msgList").innerHTML = `<div class="tbl-wrap"><table class="tbl"><tr><th>${t("col_id")}</th><th>${t("col_label")}</th><th>${t("col_groups")}</th><th>${t("col_prio")}</th><th>${t("col_sched")}</th><th>${t("col_sent")}</th><th>${t("col_status")}</th><th></th></tr>` +
    list.map(m => `<tr>
      <td class="mono">${m.id}</td>
      <td>${esc(m.label)}<details><summary>${m.groups ? m.group_count : esc(t("burned"))}</summary>${m.groups ? `<div class="out">${esc(m.groups.join(" "))}</div>` : ""}</details></td>
      <td class="mono">${m.group_count}</td>
      <td><span class="pill ${prio[m.priority]}">${esc(t("prio_" + m.priority))}</span></td>
      <td>${esc(m.schedule_id ? names[m.schedule_id] || m.schedule_id : t("any_schedule"))}</td>
      <td class="mono">${m.sent_count}/${m.transmissions}</td>
      <td><span class="pill ${m.status}">${esc(t("st_" + m.status))}</span>${m.expires ? `<div class="muted">${esc(t("col_expires"))} ${utc(m.expires)}</div>` : ""}</td>
      <td>${m.status === "queued" ? `<button class="btn small danger" data-cancel="${m.id}">${esc(t("cancel_msg"))}</button>` : `<button class="btn small" data-delete="${m.id}">${esc(t("delete"))}</button>`}</td>
    </tr>`).join("") + "</table></div>";
  $("msgList").querySelectorAll("[data-cancel]").forEach(b => b.addEventListener("click", async () => { await api("POST", `/api/messages/${b.dataset.cancel}/cancel`, {}); loadMessages(); }));
  $("msgList").querySelectorAll("[data-delete]").forEach(b => b.addEventListener("click", async () => { await api("DELETE", `/api/messages/${b.dataset.delete}`); loadMessages(); }));
}

// ---------------------------------------------------------------- schedules
async function loadSchedules() { state.schedules = await api("GET", "/api/schedules"); renderSchedules(); }

function describe(s) {
  const days = t("days");
  const dayText = s.weekdays.length === 7 ? t("every_day") : s.weekdays.map(d => days[d]).join(" ");
  if (s.kind === "times") return `${dayText} ${s.times.join(", ")} UTC`;
  return `${t("every_n", {n: s.interval_minutes})}${s.offset_minutes ? " " + t("offset", {n: s.offset_minutes}) : ""} · ${dayText}`;
}

function renderSchedules() {
  const box = $("schedList");
  if (!box) return;
  const voices = Object.fromEntries((state.voices?.voices || []).map(v => [v.id, v.name]));
  const voiceName = v => voices[voiceId(v)] || v;
  box.innerHTML = state.schedules.map(s => `<div class="card sched ${s.enabled ? "" : "off"}">
      <div class="head"><h3>${esc(s.name)}</h3><span class="pill ${s.enabled ? "ok" : ""}">${esc(s.enabled ? t("enabled") : t("disabled"))}</span></div>
      <div class="when">${esc(describe(s))}</div>
      <p class="muted">${esc(voiceName(s.voice))} · ${esc(t("callsign"))} ${esc(s.format.callsign || state.voices?.format_defaults.callsign || "")} · ${esc(t("filler_" + s.filler))}</p>
      <p class="muted">${esc(s.upcoming.length ? t("next_runs", {list: s.upcoming.map(x => utc(x, false)).join(", ")}) : t("none_planned"))}</p>
      <div class="actions">
        <button class="btn small" data-edit="${s.id}">${esc(t("edit"))}</button>
        <button class="btn small" data-preview="${s.id}">${esc(t("preview"))}</button>
        <button class="btn small" data-transmit="${s.id}">${esc(t("transmit_now"))}</button>
        <button class="btn small" data-test="${s.id}">${esc(t("test_tx"))}</button>
        <button class="btn small danger" data-del="${s.id}">${esc(t("delete"))}</button>
      </div>
      <div class="note" id="schedNote${s.id}"></div>
    </div>`).join("");
  const byId = id => state.schedules.find(s => s.id === +id);
  box.querySelectorAll("[data-edit]").forEach(b => b.addEventListener("click", () => openEditor(byId(b.dataset.edit))));
  box.querySelectorAll("[data-preview]").forEach(b => b.addEventListener("click", () => preview(`/api/schedules/${b.dataset.preview}/preview`, {}, "schedNote" + b.dataset.preview)));
  box.querySelectorAll("[data-transmit]").forEach(b => b.addEventListener("click", () => transmit(b.dataset.transmit, false)));
  box.querySelectorAll("[data-test]").forEach(b => b.addEventListener("click", () => transmit(b.dataset.test, true)));
  box.querySelectorAll("[data-del]").forEach(b => b.addEventListener("click", async () => {
    if (!confirm(t("delete_sched_confirm", {name: byId(b.dataset.del).name}))) return;
    await api("DELETE", `/api/schedules/${b.dataset.del}`);
    loadSchedules();
  }));
}

async function transmit(id, test) {
  const target = "schedNote" + id;
  try {
    await api("POST", `/api/schedules/${id}/transmit`, {test});
    note(target, t("tx_started"), "good");
    setTimeout(loadStatus, 1500);
  } catch (err) { note(target, err.message, "bad"); }
}

let previewUrl = null;
async function preview(path, data, noteId) {
  note(noteId, t("rendering"));
  try {
    const res = await api("POST", path, data, true);
    const blob = await res.blob();
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(blob);
    let text = "";
    try { text = decodeURIComponent(res.headers.get("X-Transcript") || ""); } catch { /* cut header */ }
    // Inside the editor dialog the player sits in the dialog, otherwise below the list.
    const inDialog = $("schedDialog").open;
    const audio = inDialog ? ensureDialogAudio() : $("previewAudio");
    const pre = inDialog ? $("dialogPreviewText") : $("previewText");
    audio.src = previewUrl; audio.hidden = false; pre.hidden = false; pre.textContent = text;
    note(noteId, "");
    audio.play().catch(() => {});
  } catch (err) { note(noteId, err.message, "bad"); }
}

function ensureDialogAudio() {
  if (!$("dialogAudio")) {
    $("schedMsg").insertAdjacentHTML("beforebegin", `<audio id="dialogAudio" controls></audio><pre class="out" id="dialogPreviewText"></pre>`);
  }
  return $("dialogAudio");
}

// editor
let editing = null, editKind = "times";

// A schedule may name a language ("de") instead of a voice; the station then takes the first voice of it.
function voiceId(v) {
  const list = state.voices?.voices || [];
  if (list.some(p => p.id === v)) return v;
  return (list.find(p => p.language === v) || list[0] || {}).id || v;
}

function fillStaticSelects() {
  if (!state.voices) return;
  const v = state.voices;
  $("sVoice").innerHTML = v.voices.map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join("");
  $("sEffect").innerHTML = v.effects.map(e => `<option value="${e}">${esc(t("effect_" + e))}</option>`).join("");
  $("fInterval").innerHTML = v.intervals.map(i => `<option value="${i}">${esc(t("iv_" + i))}</option>`).join("");
  $("sRigMode").innerHTML = v.rig_modes.map(m => `<option value="${m}">${esc(m || t("rig_mode_keep"))}</option>`).join("");
  const days = t("days");
  $("sDays").innerHTML = days.map((d, i) => `<label><input type="checkbox" value="${i}"> ${esc(d)}</label>`).join("");
}

function setKind(kind) {
  editKind = kind;
  document.querySelectorAll("#sKindSeg button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.kind === kind)));
  $("sTimesBox").hidden = kind !== "times";
  $("sIntervalBox").hidden = kind !== "interval";
}
document.querySelectorAll("#sKindSeg button").forEach(b => b.addEventListener("click", () => setKind(b.dataset.kind)));

function fillerVisibility() {
  $("sFillerRange").hidden = $("sFiller").value !== "random";
  $("sSkipWarn").hidden = $("sFiller").value !== "skip";
}
$("sFiller").addEventListener("change", fillerVisibility);

function openEditor(s) {
  const d = state.voices.format_defaults;
  editing = s ? s.id : null;
  s = s || {name: "", enabled: true, kind: "times", times: ["18:00"], weekdays: [0, 1, 2, 3, 4, 5, 6], interval_minutes: 60, offset_minutes: 0,
            voice: state.voices.voices[0]?.id || "de", effect: "none", format: {}, filler: "random", filler_min: 10, filler_max: 30, max_messages: 1};
  const f = Object.assign({}, d, s.format);
  $("schedTitle").textContent = s.name || t("new_schedule");
  $("sName").value = s.name; $("sEnabled").checked = s.enabled;
  setKind(s.kind);
  $("sTimes").value = s.times.join(", ");
  $("sInterval").value = s.interval_minutes; $("sOffset").value = s.offset_minutes;
  $("sDays").querySelectorAll("input").forEach(c => { c.checked = s.weekdays.includes(+c.value); });
  $("sVoice").value = voiceId(s.voice); $("sEffect").value = s.effect;
  $("sCallsign").value = f.callsign; $("sMax").value = s.max_messages;
  $("sFreq").value = s.frequency_khz || ""; $("sRigMode").value = s.rig_mode || "";
  $("fCw").value = f.cw_ident || ""; $("fCwWpm").value = f.cw_wpm;
  $("sFiller").value = s.filler; $("sFillerMin").value = s.filler_min; $("sFillerMax").value = s.filler_max;
  $("fInterval").value = f.interval; $("fIntervalRepeats").value = f.interval_repeats;
  $("fCallRepeats").value = f.callsign_repeats; $("fMsgRepeats").value = f.message_repeats;
  $("fDigitGap").value = f.digit_gap; $("fGroupGap").value = f.group_gap; $("fSectionGap").value = f.section_gap;
  $("fCount").checked = f.announce_group_count; $("fTwice").checked = f.group_twice; $("fEndTone").checked = f.end_tone;
  fillerVisibility();
  note("schedMsg", "");
  if ($("dialogAudio")) { $("dialogAudio").remove(); $("dialogPreviewText").remove(); }
  $("schedDialog").showModal();
}

function editorData() {
  const d = state.voices.format_defaults;
  const fmt = {
    callsign: $("sCallsign").value.trim(), interval: $("fInterval").value, interval_repeats: +$("fIntervalRepeats").value,
    callsign_repeats: +$("fCallRepeats").value, message_repeats: +$("fMsgRepeats").value,
    digit_gap: +$("fDigitGap").value, group_gap: +$("fGroupGap").value, section_gap: +$("fSectionGap").value,
    announce_group_count: $("fCount").checked, group_twice: $("fTwice").checked, end_tone: $("fEndTone").checked,
    cw_ident: $("fCw").value.trim().toUpperCase(), cw_wpm: +$("fCwWpm").value,
  };
  // Store only what differs from the defaults, so improved defaults reach old schedules.
  for (const k of Object.keys(fmt)) if (fmt[k] === d[k]) delete fmt[k];
  return {
    name: $("sName").value.trim(), enabled: $("sEnabled").checked, kind: editKind,
    times: $("sTimes").value.split(/[,\s]+/).filter(Boolean),
    weekdays: [...$("sDays").querySelectorAll("input:checked")].map(c => +c.value),
    interval_minutes: +$("sInterval").value, offset_minutes: +$("sOffset").value,
    voice: $("sVoice").value, effect: $("sEffect").value, format: fmt,
    filler: $("sFiller").value, filler_min: +$("sFillerMin").value, filler_max: +$("sFillerMax").value,
    max_messages: +$("sMax").value,
    frequency_khz: +$("sFreq").value || 0, rig_mode: $("sRigMode").value,
  };
}

$("schedSave").addEventListener("click", async () => {
  note("schedMsg", "");
  try {
    if (editing === null) await api("POST", "/api/schedules", editorData());
    else await api("PUT", `/api/schedules/${editing}`, editorData());
    $("schedDialog").close();
    await loadSchedules(); await loadStatus();
  } catch (err) { note("schedMsg", err.message, "bad"); }
});
$("schedPreview").addEventListener("click", () => preview("/api/preview", {schedule: editorData()}, "schedMsg"));
$("schedCancel").addEventListener("click", () => $("schedDialog").close());
$("newSchedule").addEventListener("click", () => openEditor(null));

// ---------------------------------------------------------------- log
function logTable(entries, full) {
  if (!entries.length) return `<p class="empty">${esc(t("no_log"))}</p>`;
  return `<div class="tbl-wrap"><table class="tbl"><tr><th>${t("col_time")}</th><th>${t("col_sched")}</th><th>${t("col_kind")}</th><th>${t("col_dur")}</th><th>${t("col_status")}</th>${full ? "<th></th>" : ""}</tr>` +
    entries.map(e => `<tr>
      <td class="mono">${utc(e.started)}</td>
      <td>${esc(e.schedule_name)}</td>
      <td>${e.kind ? esc(t("kind_" + e.kind)) : "–"}${e.message_ids ? ` <span class="muted">#${esc(e.message_ids.split(" ").join(", #"))}</span>` : ""}</td>
      <td class="mono">${e.duration ? Math.round(e.duration) + " s" : ""}</td>
      <td><span class="pill ${e.status}">${esc(t("st_" + e.status))}</span>${e.error ? `<div class="muted">${esc(e.error)}</div>` : ""}</td>
      ${full ? `<td>${e.transcript ? `<details><summary>${esc(t("format"))}</summary><div class="out">${esc(e.transcript)}</div></details>` : ""}
        ${e.recording ? `<details data-rec="${e.id}"><summary>${esc(t("recording"))}</summary></details>` : ""}</td>` : ""}
    </tr>`).join("") + "</table></div>";
}

async function loadLog() {
  $("logList").innerHTML = logTable(await api("GET", "/api/log?limit=200"), true);
  // Load audio only when somebody opens it.
  $("logList").querySelectorAll("[data-rec]").forEach(d => d.addEventListener("toggle", () => {
    if (d.open && !d.querySelector("audio")) d.insertAdjacentHTML("beforeend", `<audio controls preload="none" src="/api/log/${d.dataset.rec}/recording"></audio>`);
  }));
}

// ---------------------------------------------------------------- settings
async function loadSettings() { state.settings = await api("GET", "/api/settings"); }
async function loadPads() { state.pads = await api("GET", "/api/pads"); }

function renderSettings() {
  const s = state.settings;
  $("setDiscreet").checked = s.discreet; $("setKeep").value = s.keep_recordings_days;
  $("setLead").value = s.lead_seconds; $("setStationEnc").checked = s.station_encryption;
  $("pwHint").textContent = state.session.password_set ? t("pw_hint_set") : t("pw_hint_none");
  $("pwCurrentBox").hidden = !state.session.password_set;
  $("padList").innerHTML = state.pads.length
    ? `<ul class="list">${state.pads.map(p => `<li><span>${esc(p.name)} <span class="muted">${p.error ? esc(p.error) : esc(t("pages_free", {free: p.unused, total: p.pages}))}</span></span>
        <button class="btn small danger" data-pad="${esc(p.name)}">${esc(t("delete"))}</button></li>`).join("")}</ul>`
    : `<p class="empty">${esc(t("no_pads"))}</p>`;
  $("padList").querySelectorAll("[data-pad]").forEach(b => b.addEventListener("click", async () => {
    if (!confirm(t("delete_pad_confirm", {name: b.dataset.pad}))) return;
    await api("DELETE", `/api/pads/${encodeURIComponent(b.dataset.pad)}`);
    await loadPads(); renderSettings();
  }));
}

$("setForm").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    state.settings = await api("PUT", "/api/settings", {
      discreet: $("setDiscreet").checked, keep_recordings_days: +$("setKeep").value,
      lead_seconds: +$("setLead").value, station_encryption: $("setStationEnc").checked,
    });
    note("setMsg", t("saved"), "good");
  } catch (err) { note("setMsg", err.message, "bad"); }
});

$("pwForm").addEventListener("submit", async e => {
  e.preventDefault();
  if ($("pwNew").value !== $("pwNew2").value) { note("pwMsg", t("pw_mismatch"), "bad"); return; }
  try {
    await api("POST", "/api/password", {current: $("pwCurrent").value, new: $("pwNew").value});
    ["pwCurrent", "pwNew", "pwNew2"].forEach(id => { $(id).value = ""; });
    note("pwMsg", t("pw_ok"), "good");
    state.session = await api("GET", "/api/session");
    $("banner").innerHTML = ""; $("logoutBtn").hidden = false;
    renderSettings();
  } catch (err) { note("pwMsg", err.message, "bad"); }
});

async function loadTokens() {
  const list = await api("GET", "/api/tokens");
  $("tokenList").innerHTML = list.length
    ? `<ul class="list">${list.map(k => `<li><span>${esc(k.name)} <span class="muted">${esc(t("last_used", {t: k.last_used ? utc(k.last_used) : t("never")}))}</span></span>
        <button class="btn small danger" data-token="${k.id}">${esc(t("revoke"))}</button></li>`).join("")}</ul>`
    : `<p class="empty">${esc(t("no_tokens"))}</p>`;
  $("tokenList").querySelectorAll("[data-token]").forEach(b => b.addEventListener("click", async () => {
    await api("DELETE", `/api/tokens/${b.dataset.token}`); note("tokenNew", ""); loadTokens();
  }));
}

$("tokenForm").addEventListener("submit", async e => {
  e.preventDefault();
  try {
    const r = await api("POST", "/api/tokens", {name: $("tokenName").value});
    $("tokenName").value = "";
    const el = $("tokenNew");
    el.className = "note warn";
    el.innerHTML = `${esc(t("token_shown_once"))}<br><code>${esc(r.token)}</code><br><br><code>curl -X POST ${esc(location.origin)}/api/submit -H "Authorization: Bearer ${esc(r.token)}" -H "Content-Type: application/json" -d '{"groups": "12345 67890"}'</code>`;
    loadTokens();
  } catch (err) { note("tokenNew", err.message, "bad"); }
});

$("padUpload").addEventListener("click", () => $("padFile").click());
$("padFile").addEventListener("change", async e => {
  const file = e.target.files[0];
  e.target.value = "";
  if (!file) return;
  try {
    const pad = JSON.parse(await file.text());
    const name = file.name.replace(/\.json$/i, "").replace(/[^A-Za-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40) || "pad";
    await api("POST", "/api/pads", {name, pad});
    note("padMsg", t("pad_uploaded"), "good");
    await loadPads(); renderSettings();
  } catch (err) { note("padMsg", err.message, "bad"); }
});

// ---------------------------------------------------------------- output and radio
async function loadOutput() {
  [state.output, state.devices] = await Promise.all([api("GET", "/api/output"), api("GET", "/api/output/devices")]);
}

function deviceOptions(selected) {
  const list = state.devices.devices;
  let html = `<option value="">${esc(t("default_device"))}</option>`;
  html += list.map(d => `<option value="${esc(d.name)}">${esc(d.name)} · ${esc(d.hostapi)}${d.default ? " ★" : ""}</option>`).join("");
  if (selected && !list.some(d => d.name === selected)) html += `<option value="${esc(selected)}">${esc(selected)} (?)</option>`;
  return html;
}

function renderOutput() {
  const o = state.output;
  $("oMode").value = o.mode;
  $("oDevice").innerHTML = deviceOptions(o.device); $("oDevice").value = o.device;
  $("oMonitorDevice").innerHTML = deviceOptions(o.monitor_device); $("oMonitorDevice").value = o.monitor_device;
  $("oGain").value = o.gain_db; $("oMonitor").checked = o.monitor; $("oMonitorGain").value = o.monitor_gain_db;
  $("oPtt").value = o.ptt; $("oSerialPort").value = o.serial_port; $("oSerialLine").value = o.serial_line;
  $("oInvert").checked = o.serial_invert; $("oLead").value = o.ptt_lead_ms; $("oTail").value = o.ptt_tail_ms;
  $("oCat").checked = o.cat; $("oRigHost").value = o.rig_host; $("oRigPort").value = o.rig_port; $("oMax").value = o.max_tx_seconds;
  $("oSerialPorts").innerHTML = state.devices.serial_ports.map(p => `<option value="${esc(p.device)}">${esc(p.description)}</option>`).join("");
  if (state.devices.error) note("outMsg", state.devices.error, "warn");
  outputVisibility();
}

function outputVisibility() {
  const radio = $("oMode").value === "soundcard";
  $("oRadioBox").hidden = !radio; $("oPttBox").hidden = !radio;
  $("oMonitorBox").hidden = !$("oMonitor").checked;
  $("oSerialBox").hidden = $("oPtt").value !== "serial"; $("oInvertBox").hidden = $("oPtt").value !== "serial";
  $("oCatBox").hidden = !$("oCat").checked;
}
["oMode", "oMonitor", "oPtt", "oCat"].forEach(id => $(id).addEventListener("change", outputVisibility));

function outputData() {
  return {
    mode: $("oMode").value, device: $("oDevice").value, gain_db: +$("oGain").value,
    monitor: $("oMonitor").checked, monitor_device: $("oMonitorDevice").value, monitor_gain_db: +$("oMonitorGain").value,
    ptt: $("oPtt").value, serial_port: $("oSerialPort").value.trim(), serial_line: $("oSerialLine").value,
    serial_invert: $("oInvert").checked, ptt_lead_ms: +$("oLead").value, ptt_tail_ms: +$("oTail").value,
    cat: $("oCat").checked, rig_host: $("oRigHost").value.trim(), rig_port: +$("oRigPort").value,
    max_tx_seconds: +$("oMax").value,
  };
}

$("outForm").addEventListener("submit", async e => {
  e.preventDefault();
  try { state.output = await api("PUT", "/api/output", outputData()); note("outMsg", t("saved"), "good"); loadStatus(); }
  catch (err) { note("outMsg", err.message, "bad"); }
});
$("oTestTone").addEventListener("click", async () => {
  try {
    state.output = await api("PUT", "/api/output", outputData());  // test what is on the screen
    await api("POST", "/api/output/test", {what: "tone", seconds: 3});
    note("outMsg", t("tone_started"), "good");
  } catch (err) { note("outMsg", err.message, "bad"); }
});
$("oTestCat").addEventListener("click", async () => {
  try {
    state.output = await api("PUT", "/api/output", outputData());
    const r = await api("POST", "/api/output/test", {what: "cat"});
    note("outMsg", t("cat_ok", {f: (r.frequency_hz / 1000).toLocaleString(lang, {maximumFractionDigits: 3})}), "good");
  } catch (err) { note("outMsg", err.message, "bad"); }
});

// ---------------------------------------------------------------- start
setInterval(tickClock, 1000);
setInterval(() => {
  if (!state.session?.logged_in || $("app").hidden || document.hidden) return;
  loadStatus().catch(() => {});
  if (state.tab === "overview") loadRecent().catch(() => {});
}, 3000);

setLang(storeGet("etherdigits.lang") || ((navigator.language || "en").toLowerCase().startsWith("de") ? "de" : "en"));
tickClock();
startApp().catch(err => { $("banner").innerHTML = `<div class="note bad">${esc(err.message)}</div>`; });
