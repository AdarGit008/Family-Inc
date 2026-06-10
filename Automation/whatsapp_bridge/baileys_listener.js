/**
 * Family inc. — WhatsApp group listener (self-hosted, free bridge)
 *
 * Pairs as a WhatsApp Web "companion" to Adar's main number using Baileys
 * (the same QR-code flow as web.whatsapp.com). Two jobs:
 *
 * 1. LISTEN — group messages ONLY, normalized into the WhatsApp_Inbox schema,
 *    appended as JSON lines to ../inbox/whatsapp_inbox.jsonl.
 * 2. SEND — polls ../outbox/whatsapp_outbox.jsonl (written by the Python
 *    automations: reminders engine, briefings, whatsapp_summarizer alerts)
 *    and delivers each queued message to Adar/Shanee 1:1. Decision
 *    2026-06-04 (Adar): Baileys-first delivery, Twilio not provisioned.
 *
 * SEND SCOPE GUARD: outbound goes ONLY to the recipients named in
 * ./recipients.json ({"adar": "9725...@s.whatsapp.net", "shanee": ...}).
 * That file lives next to auth_state/ on the bridge machine and is never
 * committed. Any outbox row addressed to anyone else is refused and logged.
 *
 * Nothing leaves the machine. The Python classifier (whatsapp_summarizer.py)
 * reads the JSONL file on its hourly run. This is the privacy-first path from
 * 07_WhatsApp_Group_Summarizer_Spec.md — plaintext stays in the house.
 *
 * COST: free software. Runs on any old Android-via-Termux, a Raspberry Pi,
 * an always-on laptop, or a cheap second phone. ~₪0/month.
 *
 * --- Setup ---
 *   cd Automation/whatsapp_bridge
 *   npm install
 *   node baileys_listener.js            # scan the QR with Adar's phone once
 *   # auth persists in ./auth_state/ ; restart resumes without re-scanning
 *
 * --- Scope guard ---
 * Reads GROUPS ONLY (jid ends in @g.us). 1:1 chats (@s.whatsapp.net) are
 * dropped before any processing — matches the spec's "No 1:1 chat reading."
 * Media bodies are never stored; only has_media=true is recorded.
 */

const fs = require('fs');
const path = require('path');
const P = require('pino');
const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
} = require('@whiskeysockets/baileys');

const ROOT = __dirname;
const AUTH_DIR = path.join(ROOT, 'auth_state');
const INBOX_DIR = path.join(ROOT, '..', 'inbox');
const INBOX_FILE = path.join(INBOX_DIR, 'whatsapp_inbox.jsonl');
const HEARTBEAT_FILE = path.join(INBOX_DIR, 'heartbeat.txt');
const OUTBOX_DIR = path.join(ROOT, '..', 'outbox');
const OUTBOX_FILE = path.join(OUTBOX_DIR, 'whatsapp_outbox.jsonl');
const SENT_FILE = path.join(OUTBOX_DIR, 'whatsapp_sent.jsonl');
const RECIPIENTS_FILE = path.join(ROOT, 'recipients.json'); // never committed
const OUTBOX_POLL_MS = 15 * 1000;

fs.mkdirSync(INBOX_DIR, { recursive: true });
fs.mkdirSync(OUTBOX_DIR, { recursive: true });

// Heartbeat: whatsapp_summarizer.py checks this file's timestamp and surfaces a
// "bridge may be down" warning in the daily digest when it goes stale.
// Written on connect + every message + every 15 min while connected.
function beat() {
  try { fs.writeFileSync(HEARTBEAT_FILE, new Date().toISOString(), 'utf-8'); } catch (e) { /* noop */ }
}

const logger = P({ level: 'warn' });

// In-memory cache of group subject lookups so we don't spam metadata calls.
const groupNameCache = new Map();

function isGroup(jid) {
  return typeof jid === 'string' && jid.endsWith('@g.us');
}

// Pull the human-readable body out of the many WA message shapes.
function extractText(msg) {
  const m = msg.message || {};
  return (
    m.conversation ||
    m.extendedTextMessage?.text ||
    m.imageMessage?.caption ||
    m.videoMessage?.caption ||
    m.documentMessage?.caption ||
    ''
  ).trim();
}

function hasMedia(msg) {
  const m = msg.message || {};
  return Boolean(
    m.imageMessage || m.videoMessage || m.audioMessage ||
    m.stickerMessage || m.documentMessage,
  );
}

function appendInbox(row) {
  fs.appendFileSync(INBOX_FILE, JSON.stringify(row) + '\n', 'utf-8');
}

// --- Outbound (Baileys-first delivery, decision 2026-06-04) ----------------

function loadRecipients() {
  try {
    const r = JSON.parse(fs.readFileSync(RECIPIENTS_FILE, 'utf-8'));
    // hard scope guard: exactly these two logical names, 1:1 JIDs only
    const out = {};
    for (const name of ['adar', 'shanee']) {
      if (typeof r[name] === 'string' && r[name].endsWith('@s.whatsapp.net')) {
        out[name] = r[name];
      }
    }
    return out;
  } catch (e) {
    return null; // missing/invalid -> sending disabled, listening unaffected
  }
}

function readJsonl(file) {
  if (!fs.existsSync(file)) return [];
  return fs.readFileSync(file, 'utf-8')
    .split('\n')
    .filter(Boolean)
    .map((l) => { try { return JSON.parse(l); } catch (e) { return null; } })
    .filter(Boolean);
}

let outboxBusy = false;
async function processOutbox(sock) {
  if (outboxBusy) return; // don't overlap polls
  outboxBusy = true;
  try {
    const recipients = loadRecipients();
    const pending = readJsonl(OUTBOX_FILE);
    if (!pending.length) return;
    if (!recipients || !Object.keys(recipients).length) {
      console.log('[outbox] recipients.json missing/invalid — sending disabled');
      return;
    }
    // dedup per (id, target) so a crash mid-"both" still delivers the second leg
    const done = new Set(readJsonl(SENT_FILE).map((r) => `${r.id}:${r.to}`));
    for (const row of pending) {
      if (!row.id) continue;
      const targets = row.to === 'both' ? ['adar', 'shanee'] : [row.to];
      for (const name of targets) {
        if (done.has(`${row.id}:${name}`)) continue;
        const jid = recipients[name];
        if (!jid) { // scope guard: refuse anything not adar/shanee
          fs.appendFileSync(SENT_FILE, JSON.stringify({
            id: row.id, to: name, status: 'refused_unknown_recipient',
            at: new Date().toISOString(),
          }) + '\n', 'utf-8');
          console.log(`[outbox] REFUSED ${row.id} → "${name}" (not a configured recipient)`);
          continue;
        }
        await sock.sendMessage(jid, { text: String(row.body || '').slice(0, 4096) });
        fs.appendFileSync(SENT_FILE, JSON.stringify({
          id: row.id, to: name, status: 'sent', at: new Date().toISOString(),
        }) + '\n', 'utf-8');
        console.log(`[outbox] sent ${row.id} → ${name}`);
        done.add(`${row.id}:${name}`);
      }
    }
  } catch (e) {
    console.log('[outbox] error (will retry next poll):', e.message || e);
  } finally {
    outboxBusy = false;
  }
}

async function resolveGroupName(sock, jid) {
  if (groupNameCache.has(jid)) return groupNameCache.get(jid);
  try {
    const meta = await sock.groupMetadata(jid);
    groupNameCache.set(jid, meta.subject || jid);
    return meta.subject || jid;
  } catch (e) {
    return jid;
  }
}

async function start() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();

  const sock = makeWASocket({
    version,
    auth: state,
    logger,
    printQRInTerminal: true, // scan once with Adar's phone -> Linked devices
    markOnlineOnConnect: false, // stay invisible except when delivering outbox
    syncFullHistory: false,
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', (u) => {
    const { connection, lastDisconnect } = u;
    if (connection === 'open') {
      console.log('[baileys] connected — listening to GROUP messages; outbox sender armed');
      beat();
      processOutbox(sock); // flush anything queued while we were down
      if (!global._beatTimer) {
        global._beatTimer = setInterval(beat, 15 * 60 * 1000); // idle heartbeat
      }
      if (!global._outboxTimer) {
        global._outboxTimer = setInterval(() => processOutbox(sock), OUTBOX_POLL_MS);
      }
    } else if (connection === 'close') {
      // stop the timers so a dead bridge actually LOOKS dead (and can't "send")
      if (global._beatTimer) { clearInterval(global._beatTimer); global._beatTimer = null; }
      if (global._outboxTimer) { clearInterval(global._outboxTimer); global._outboxTimer = null; }
      const code = lastDisconnect?.error?.output?.statusCode;
      const loggedOut = code === DisconnectReason.loggedOut;
      console.log(`[baileys] connection closed (code ${code}); ${loggedOut ? 'logged out — delete auth_state and re-pair' : 'reconnecting…'}`);
      if (!loggedOut) start();
    }
  });

  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    beat();
    if (type !== 'notify') return; // ignore history backfill
    for (const msg of messages) {
      try {
        const jid = msg.key?.remoteJid;
        if (!isGroup(jid)) continue;       // GROUPS ONLY
        if (msg.key?.fromMe) continue;     // ignore our own sends

        const text = extractText(msg);
        const media = hasMedia(msg);
        if (!text && !media) continue;     // nothing to record

        const groupName = await resolveGroupName(sock, jid);
        const senderJid = msg.key?.participant || jid;
        const senderName = msg.pushName || senderJid.split('@')[0];
        const tsSec = Number(msg.messageTimestamp) || Math.floor(Date.now() / 1000);

        appendInbox({
          msg_id: msg.key?.id,
          group_jid: jid,
          group_name: groupName,
          sender_jid: senderJid,
          sender_name: senderName,
          received_at: new Date(tsSec * 1000).toISOString(),
          text: media && !text ? '' : text, // never store media body
          has_media: media,
        });
        console.log(`[inbox] ${groupName} | ${senderName}: ${(text || '[media]').slice(0, 60)}`);
      } catch (e) {
        logger.warn({ e }, 'failed to process message');
      }
    }
  });
}

start().catch((e) => {
  console.error('[baileys] fatal', e);
  process.exit(1);
});
