/**
 * Family inc. — WhatsApp group listener (self-hosted, free bridge)
 *
 * Pairs as a WhatsApp Web "companion" to Adar's main number using Baileys
 * (the same QR-code flow as web.whatsapp.com). Two jobs:
 *
 * 1. LISTEN — group messages ONLY, normalized into the WhatsApp_Inbox schema,
 *    appended as JSON lines to ./state/inbox/whatsapp_inbox.jsonl.
 *    ALSO accepts 1:1 replies from Adar/Shanee (configurable JIDs), parses
 *    basic reminder-reply commands, writes them to ./state/inbox/replies.jsonl,
 *    and sends immediate acknowledgment. (Reply parsing is PARKED until v1.1 —
 *    SPEC §7.4: the bridge never reads 1:1 chats in v1; the guard below only
 *    lifts for the two adult JIDs once recipients.json names them.)
 * 2. SEND — polls ./state/outbox/whatsapp_outbox.jsonl (written by the Python
 *    automations via lib/outbox.py, the single chokepoint) and delivers each
 *    queued message to Adar/Shanee 1:1 (D-010: Baileys-first delivery).
 *
 * SEND SCOPE GUARD: outbound goes ONLY to the recipients named in
 * ./recipients.json ({"adar": "9725...@s.whatsapp.net", "shanee": ...}).
 * That file lives on the bridge machine and is never committed. Any outbox
 * row addressed to anyone else is refused and logged.
 *
 * REPLY SCOPE GUARD: inbound 1:1 replies are accepted ONLY from the JIDs
 * listed in recipients.json. Everything else from @s.whatsapp.net is dropped.
 *
 * Nothing leaves the machine. The Python classifier (whatsapp_summarizer.py)
 * reads the JSONL file on its hourly run. This is the privacy-first path of
 * SPEC.md §8.6 — plaintext stays in the house.
 *
 * COST: free software, runs on the appliance VPS (ENGINEERING.md §5). ~₪0/mo.
 *
 * --- Setup (full runbook: ENGINEERING.md §5) ---
 *   cd automation/bridge
 *   npm ci
 *   node baileys_listener.js            # scan the QR with Adar's phone once
 *   # auth persists in ./state/auth_state/ ; restart resumes without re-scanning
 *   # after a VPS rebuild, RESTORE state/auth_state/ from backup before re-pairing
 *
 * --- Scope guard ---
 * Group messages (jid ends in @g.us) are always accepted.
 * 1:1 chats (@s.whatsapp.net) are accepted ONLY from configured recipient JIDs
 * (Adar + Shanee) and are treated as reminder-reply commands. All other 1:1
 * messages are dropped.
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
const STATE_DIR = path.join(ROOT, 'state'); // gitignored runtime state
const AUTH_DIR = path.join(STATE_DIR, 'auth_state');
const INBOX_DIR = path.join(STATE_DIR, 'inbox');
const INBOX_FILE = path.join(INBOX_DIR, 'whatsapp_inbox.jsonl');
const REPLIES_FILE = path.join(INBOX_DIR, 'replies.jsonl');
const HEARTBEAT_FILE = path.join(INBOX_DIR, 'heartbeat.txt');
const OUTBOX_DIR = path.join(STATE_DIR, 'outbox');
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

// --- Reply handling (02_Reminders_Engine_Spec.md §"Reply parsing") ----------

/**
 * Parse a reminder-reply command from inbound text.
 * Returns {cmd, index, n} or null if no command recognized.
 *
 * Commands understood:
 *   done, 1 done, 1 ✅         → cmd='done'
 *   +7, 1 +7, snooze 7d        → cmd='snooze' with n=7
 *   mute 30d, 1 mute           → cmd='mute' with n=30 (default 30)
 *   list, today, ?             → cmd='list'
 *   help                       → cmd='help'
 */
function parseReply(text) {
  const t = (text || '').trim().toLowerCase();
  if (!t) return null;

  // Strip WhatsApp bold/italic markers
  const clean = t.replace(/[*_~`]/g, '').trim();

  // Index prefix: "1 done", "2 +7", "3 mute"
  const indexMatch = clean.match(/^(\d+)\s+(.+)$/);
  const index = indexMatch ? parseInt(indexMatch[1], 10) : null;
  const cmdPart = indexMatch ? indexMatch[2] : clean;

  // done / ✅
  if (/^(done|✅)$/.test(cmdPart)) {
    return { cmd: 'done', index, n: null };
  }

  // snooze: +N, snooze Nd, +Nd
  const snoozeMatch = cmdPart.match(/^\+(\d+)$/);
  if (snoozeMatch) {
    return { cmd: 'snooze', index, n: parseInt(snoozeMatch[1], 10) };
  }
  const snoozeWordMatch = cmdPart.match(/^snooze\s+(\d+)d?$/);
  if (snoozeWordMatch) {
    return { cmd: 'snooze', index, n: parseInt(snoozeWordMatch[1], 10) };
  }

  // mute: mute, mute Nd
  if (/^mute$/.test(cmdPart)) {
    return { cmd: 'mute', index, n: 30 };
  }
  const muteMatch = cmdPart.match(/^mute\s+(\d+)d?$/);
  if (muteMatch) {
    return { cmd: 'mute', index, n: parseInt(muteMatch[1], 10) };
  }

  // list / today / ?
  if (/^(list|today|\?)$/.test(cmdPart)) {
    return { cmd: 'list', index: null, n: null };
  }

  // help
  if (cmdPart === 'help') {
    return { cmd: 'help', index: null, n: null };
  }

  return null; // unrecognized
}

/**
 * Build an immediate acknowledgment for recognized commands.
 * For done/snooze/mute this is a quick confirmation; the engine applies the
 * actual sheet change and may send a follow-up message.
 * For list/?, the engine will send the full digest separately.
 */
function ackText(parsed, rawText) {
  if (!parsed) {
    return "👋 Didn't catch that. Reply with:\n" +
           "• 1 ✅ to mark done\n" +
           "• 1 +7 to snooze 7 days\n" +
           "• 1 mute to mute 30 days\n" +
           "• ? to see today's list";
  }
  switch (parsed.cmd) {
    case 'done':
      return parsed.index
        ? `✅ Got it — marking #${parsed.index} as done`
        : '✅ Got it — marking as done';
    case 'snooze':
      return parsed.index
        ? `📆 Got it — snoozing #${parsed.index} by ${parsed.n} day(s)`
        : `📆 Got it — snoozing by ${parsed.n} day(s)`;
    case 'mute':
      return parsed.index
        ? `🤐 Got it — muting #${parsed.index} for ${parsed.n} day(s)`
        : `🤐 Got it — muting for ${parsed.n} day(s)`;
    case 'list':
    case '?':
    case 'today':
      return '📋 Fetching today\'s reminders…';
    case 'help':
      return 'Reply to reminder digests:\n' +
             '• N ✅ — mark #N done\n' +
             '• N +D — snooze #N by D days\n' +
             '• N mute — mute #N 30 days\n' +
             '• ? — show today\'s list';
    default:
      return null;
  }
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

/**
 * Return the set of JIDs that are allowed to send 1:1 replies.
 * These are the JIDs configured in recipients.json (Adar + Shanee).
 */
function replyJids() {
  const r = loadRecipients();
  if (!r) return new Set();
  return new Set(Object.values(r));
}

/**
 * Check if a JID is a configured reply sender.
 * Used to lift the groups-only guard for 1:1 messages from Adar/Shanee.
 */
function isReplySender(jid) {
  return replyJids().has(jid);
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
      // Quiet-hours hold (lib/outbox.py stamps not_before as local-naive ISO;
      // JS parses offset-less date-times as local, and the appliance runs
      // Asia/Jerusalem — SPEC §8.2/§8.5)
      if (row.not_before && new Date(row.not_before) > new Date()) continue;
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
      console.log('[baileys] connected — listening to GROUP messages + 1:1 replies; outbox sender armed');
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
        if (msg.key?.fromMe) continue;     // ignore our own sends

        // --- 1:1 reply handling (reminder commands from Adar/Shanee) ---
        if (!isGroup(jid)) {
          if (!isReplySender(jid)) continue; // drop unknown 1:1 messages
          const text = extractText(msg);
          if (!text) continue; // empty message, skip
          const senderJid = msg.key?.participant || jid;
          const senderName = msg.pushName || senderJid.split('@')[0];
          const tsSec = Number(msg.messageTimestamp) || Math.floor(Date.now() / 1000);

          const parsed = parseReply(text);

          // Write reply to replies.jsonl for the Python engine to process
          const replyRow = {
            msg_id: msg.key?.id,
            sender_jid: senderJid,
            sender_name: senderName,
            received_at: new Date(tsSec * 1000).toISOString(),
            text: text,
            parsed: parsed ? { cmd: parsed.cmd, index: parsed.index, n: parsed.n } : null,
            recognized: !!parsed,
          };
          fs.appendFileSync(REPLIES_FILE, JSON.stringify(replyRow) + '\n', 'utf-8');
          console.log(`[reply] ${senderName}: "${text}" → ${parsed ? parsed.cmd : 'unrecognized'}`);

          // Send immediate acknowledgment
          const ack = ackText(parsed, text);
          if (ack) {
            await sock.sendMessage(jid, { text: ack });
            console.log(`[reply-ack] → ${senderName}: ${ack.slice(0, 60)}`);
          }
          continue;
        }

        // --- Group message handling (existing) ---
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
