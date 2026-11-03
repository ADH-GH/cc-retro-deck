import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { DeckRow, DeckState, EmulScreen, Intro, OwnStatus, Pokes } from '../types'
import { C64 as C64Machine } from './basic'
import { refreshShell, setupCommand, uninstallCommand } from './setup'

// ---------------------------------------------------------------------------
// Palettes: 8/16-bit home computer colors, one role each.
// ---------------------------------------------------------------------------

type Palette = {
  /** The band's ground. On the C64 that is the light blue border, not the dark screen. */
  bg: string
  fg: string
  /** Separators and rules. */
  frame: string
  /** The banner's screen inside the border. */
  screenBg: string
  screenFg: string
  project: string
  model: string
  cost: string
  turns: string
  limits: string
  label: string
  busy: string
  ask: string
  askBg: string
  askFg: string
  done: string
  idle: string
  stale: string
  accent: string
  meterOn: string
  meterOff: string
  crab: string
  banner: string[]
}

// C64: the Colodore palette, all sixteen VIC-II colors as a bright CRT showed
// them. Amiga: Workbench 1.3's four. CGA: IBM's sixteen.
const C64 = {
  black: '#000000', white: '#FFFFFF', red: '#813338', cyan: '#75CEC8',
  purple: '#8E3C97', green: '#56AC4D', blue: '#2E2C9B', yellow: '#EDF171',
  orange: '#8E5029', brown: '#553800', lightRed: '#C46C71', darkGrey: '#4A4A4A',
  grey: '#7B7B7B', lightGreen: '#A9FF9F', lightBlue: '#706DEB', lightGrey: '#B2B2B2',
}

const PALETTES: Record<string, Palette> = {
  c64: {
    bg: C64.lightBlue, fg: C64.white, frame: C64.blue,
    screenBg: C64.blue, screenFg: C64.lightBlue,
    project: C64.yellow, model: C64.white, cost: C64.lightGreen, turns: C64.cyan,
    limits: C64.lightBlue, label: C64.lightBlue,
    busy: C64.cyan, ask: C64.lightRed, askBg: C64.red, askFg: C64.white,
    done: C64.lightGreen, idle: C64.lightGrey, stale: C64.grey,
    accent: C64.yellow, meterOn: C64.lightGreen, meterOff: C64.lightBlue, crab: C64.lightRed,
    banner: [
      '    **** CLAUDE CODE RETRO DECK V0.12 ****',
      ' 64K RAM SYSTEM  38911 BASIC BYTES FREE',
      'READY.',
    ],
  },
  amiga: {
    bg: '#0055AA', fg: '#FFFFFF', frame: '#FF8800',
    screenBg: '#0055AA', screenFg: '#FFFFFF',
    project: '#FF8800', model: '#FFFFFF', cost: '#FFFFFF', turns: '#FFFFFF',
    limits: '#FFFFFF', label: '#FF8800',
    busy: '#FFFFFF', ask: '#FF8800', askBg: '#FF8800', askFg: '#000000',
    done: '#FFFFFF', idle: '#8899BB', stale: '#667799',
    accent: '#FF8800', meterOn: '#FFFFFF', meterOff: '#003377', crab: '#FF8800',
    banner: [
      'Claude Code Workbench release 1.3  Retro Deck V0.12',
      'Copyright © Commodore-Amiga, Inc. (in spirit)  Insert Workbench disk',
    ],
  },
  cga: {
    bg: '#0000AA', fg: '#FFFF55', frame: '#55FFFF',
    screenBg: '#000000', screenFg: '#AAAAAA',
    project: '#FFFF55', model: '#FFFFFF', cost: '#55FF55', turns: '#55FFFF',
    limits: '#AAAAAA', label: '#AAAAAA',
    busy: '#55FFFF', ask: '#FF5555', askBg: '#AA0000', askFg: '#FFFFFF',
    done: '#55FF55', idle: '#AAAAAA', stale: '#555555',
    accent: '#FFFF55', meterOn: '#55FF55', meterOff: '#555555', crab: '#FF5555',
    banner: [
      'Starting Claude Code... Retro Deck V0.12',
      'C:\\> HIMEM is testing extended memory...done.',
    ],
  },
}

// ---------------------------------------------------------------------------
// The crab: the Claude Code mascot at its own size, 9 columns by 3 rows, in
// the two forms the CLI itself draws it. Block glyphs on most terminals; on
// Apple Terminal, whose fonts misplace the quadrant glyphs, a solid band with
// the eyes cut out of it. A `cut` cell is ground color on crab color.
// ---------------------------------------------------------------------------

type Cell = { text: string; cut?: boolean }
type Sprite = Cell[][]

const CRAB_W = 9
const EYE = '#000000'   // the eyes are black, as the CLI draws them
// One dance cycle: twelve walking frames, then a four-frame hop on the spot.
const CRAB_CYCLE = 16
const CRAB_WALK = 12

function crabSprite(apple: boolean, dir: 1 | -1, frame: number): Sprite {
  const phase = frame % CRAB_CYCLE
  const walking = phase < CRAB_WALK
  const stepLeft = Math.floor(phase / 2) % 2 === 0
  const up = phase % 2 === 0
  const feet = walking ? (stepLeft ? ' ▘▘      ' : '      ▝▝ ') : ' ▘▘   ▝▝ '
  if (apple) {
    const eyes = walking ? (dir === 1 ? ' ▝   ▝ ' : ' ▘   ▘ ') : up ? ' ▂   ▂ ' : ' ▗   ▂ '
    return [
      [{ text: '▗' }, { text: eyes, cut: true }, { text: '▖' }],
      [{ text: ' ' }, { text: '       ', cut: true }, { text: ' ' }],
      [{ text: feet }],
    ]
  }
  const eyes = walking ? (dir === 1 ? '█▟███▟' : '▟███▟█') : '▛███▛█'
  const armsUp = !walking && up
  return [
    [{ text: armsUp ? `▗▟${eyes}▄` : ` ▐${eyes} ` }],
    [{ text: armsUp ? ' ▜██████▘' : '▝▜██████▀' }],
    [{ text: feet }],
  ]
}

// ---------------------------------------------------------------------------
// State the drawings read (survives a hot reload) and module state (does not).
// ---------------------------------------------------------------------------

const PANE = 'deck'
const own = atom({ plugin: 'cc-retro-deck-linux', key: 'own' } as const, null)
const roster = atom({ plugin: 'cc-retro-deck-linux', key: 'roster' } as const, [])
const themeOverride = atom({ plugin: 'cc-retro-deck-linux', key: 'themeOverride' } as const, null)
const intro = atom({ plugin: 'cc-retro-deck-linux', key: 'intro' } as const, null)
const pokes = atom({ plugin: 'cc-retro-deck-linux', key: 'pokes' } as const, { border: null, screen: null, text: null })
const emul = atom({ plugin: 'cc-retro-deck-linux', key: 'emul' } as const, null)

// The sixteen VIC-II colors by index, for POKE 53280/53281/646 and the emulated screen.
const C64_COLORS = [
  C64.black, C64.white, C64.red, C64.cyan, C64.purple, C64.green, C64.blue, C64.yellow,
  C64.orange, C64.brown, C64.lightRed, C64.darkGrey, C64.grey, C64.lightGreen, C64.lightBlue, C64.lightGrey,
]
const C64_PANE = 'c64'

const HOTKEYS = '123456789abcdefghijklmnopqrstuvwxyz'
const STALE_AFTER_MS = 6 * 60 * 60 * 1000
const PEER_FRESH_MS = 20 * 1000
const SWITCH_COOLDOWN_MS = 15 * 1000
const INTRO_MS = 6000
const INTRO_FRAME_MS = 90
const DECK_COLUMNS = 46
const ROSTER_EVERY_MS = 15 * 1000      // ADH: 10 to 15 s is fine; same tick as the Mac edition
const STATE_WORD: Record<DeckState, string> = { busy: 'ACT', ask: 'ASK', done: 'RDY', idle: 'IDL', stale: 'IDL' }

let configuredTheme = 'c64'
let autoSwitch = false
let autoOpen = true
let showBanner = true
let showCrab = true
let introEvery = 60
let inFrame = false
let frameSock = ''                 // tmux socket of frame.sh; names the header's party file
let appleTerminal = false
let currentTurnId = ''
let tabReturn: string[] = []
let pureData: string[] = []
let pureDataPtr = 0
let machine: C64Machine | null = null
let emulTimer: { cancel: () => void } | null = null

let home = ''
let uninstalled = false              // /deck uninstall apply: write nothing more under ~/.claude/retro-deck
let sessionId = ''
let selfPid = 0
let selfTty = ''
let state: DeckState = 'idle'
let reason = ''
let lastSwitchAt = 0
let isWorking = false

// Linux: every framed session is a window of ONE tmux server (shell/frame.sh), and
// those windows stand in for the Terminal.app tabs of the Mac version. GNOME Terminal
// cannot be switched to a tab from outside; tmux can.
const TMUX_SOCK = 'c64'

// ---------------------------------------------------------------------------
// Small pure helpers.
// ---------------------------------------------------------------------------

/** `5h 12% · 7d 3% · $ 40%`, each part only when the CLI reports that window. */
function limitsText(status: OwnStatus): string {
  const parts: string[] = []
  if (status.fiveHour !== null && status.fiveHour !== undefined) parts.push(`5h ${status.fiveHour}%`)
  if (status.sevenDay !== null && status.sevenDay !== undefined) parts.push(`7d ${status.sevenDay}%`)
  if (status.spend !== null && status.spend !== undefined) parts.push(`$ ${status.spend}%`)
  return parts.join(' · ')
}

function sidecarDir(): string { return `${home}/.claude/retro-deck/sessions` }
function registryDir(): string { return `${home}/.claude/sessions` }
function snapshotPath(): string { return `${home}/.claude/retro-deck/last-deck.json` }

function projectOf(cwd: string): string {
  const parts = cwd.split('/').filter(Boolean)
  const hit = parts.find(p => /^\d{3}-/.test(p))
  return hit ?? parts[parts.length - 1] ?? cwd
}

/** True when the folder name says which project it is (`NNN-name`), false for a bare root like `~/claude`. */
function isProjectName(project: string): boolean { return /^\d{3}-/.test(project) }

/** What a deck row is called: the project folder when it names one, else the session's topic. */
function labelOf(row: { project: string; name: string }): string {
  return isProjectName(row.project) || !row.name ? row.project : row.name
}

// The topic of a session, read once from the head of its transcript: the project it
// talks about most (`NNN-name`), else a few words from the small model, else its first
// prompt while the model has not answered. A model's answer is kept in the store.
const topicCache = new Map<string, { topic: string; at: number }>()
const pendingTopics = new Set<string>()
const TOPIC_RETRY_MS = 60 * 1000
const TOPIC_WIDTH = 28

function transcriptPath(cwd: string, id: string): string {
  return `${home}/.claude/projects/${cwd.replace(/[^A-Za-z0-9]/g, '-')}/${id}.jsonl`
}

function clip(text: string): string {
  return text.length > TOPIC_WIDTH ? text.slice(0, TOPIC_WIDTH - 1).trimEnd() + '…' : text
}

/** The person's own messages in a transcript head, without pasted tags and slash commands. */
function userTexts(head: string): string[] {
  const out: string[] = []
  for (const line of head.split('\n')) {
    if (!line.includes('"type":"user"')) continue
    try {
      const d = JSON.parse(line) as { type?: string; message?: { content?: unknown } }
      if (d.type !== 'user') continue
      const c = d.message?.content
      const text = typeof c === 'string'
        ? c
        : Array.isArray(c) ? c.map(x => (x && typeof x === 'object' && (x as { type?: string }).type === 'text' ? String((x as { text?: string }).text ?? '') : '')).join(' ') : ''
      const clean = text.replace(/<[^>]*>[\s\S]*?<\/[^>]*>/g, ' ').replace(/\s+/g, ' ').trim()
      if (!clean || clean.startsWith('<') || clean.startsWith('/')) continue
      out.push(clean)
    } catch { /* a half line at the cut */ }
  }
  return out
}

/** The project a conversation names most often, as `NNN-name`; '' when it names none that exists. */
function projectMentioned(texts: string[], known: ReadonlySet<string> | null): string {
  const count = new Map<string, number>()
  for (const t of texts) {
    for (const m of t.matchAll(/\b(\d{3}-[a-z][a-z0-9]*(?:-[a-z0-9]+)*)/gi)) {
      const slug = m[1].toLowerCase()
      if (known !== null && !known.has(slug)) continue   // a template's `077-kurzname` is no project
      count.set(slug, (count.get(slug) ?? 0) + 1)
    }
  }
  let best = ''
  let n = 0
  for (const [slug, c] of count) if (c > n) { best = slug; n = c }
  return best
}

// The project folders that exist, so a mention counts only when it names one of them;
// The `NNN-name` folders under `<root>/projects`, listed once per load.
let knownProjects: ReadonlySet<string> | null = null
let knownProjectsAt = 0

async function knownProjectFolders($: EngineInterface, root: string): Promise<ReadonlySet<string> | null> {
  const now = Date.now()
  if (knownProjects !== null && now - knownProjectsAt < 10 * 60 * 1000) return knownProjects
  const names = new Set<string>()
  for (const dir of [`${root}/projects`]) {
    const ls = await $.process.run(['ls', '-1', dir], { timeoutMs: 3000 }).catch(() => ({ stdout: '' }))
    for (const line of ls.stdout.split('\n')) if (/^\d{3}-/.test(line)) names.add(line.trim().toLowerCase())
  }
  knownProjects = names.size > 0 ? names : null
  knownProjectsAt = now
  return knownProjects
}

async function topicOf($: EngineInterface, id: string, cwd: string, now: number): Promise<string> {
  const hit = topicCache.get(id)
  if (hit && (hit.topic || now - hit.at < TOPIC_RETRY_MS)) return hit.topic
  const stored = await $.store.get(`topic:${id}`).catch(() => undefined)
  if (typeof stored === 'string' && stored) {
    topicCache.set(id, { topic: stored, at: now })
    return stored
  }
  const head = await $.process
    .run(['head', '-c', '262144', transcriptPath(cwd, id)], { timeoutMs: 3000 })
    .catch(() => ({ stdout: '' }))
  const texts = userTexts(head.stdout)
  const project = projectMentioned(texts, await knownProjectFolders($, cwd))
  const topic = project || clip(texts[0] ?? '')
  topicCache.set(id, { topic, at: now })
  if (!project && texts.length > 0) void nameByModel($, id, texts)
  return topic
}

/** Asks the small model what a conversation is about, once per session; the answer goes to the store. */
async function nameByModel($: EngineInterface, id: string, texts: string[]): Promise<void> {
  if (pendingTopics.has(id)) return
  pendingTopics.add(id)
  const sample = texts.slice(0, 6).map(t => t.slice(0, 400)).join('\n---\n').slice(0, 2400)
  const reply = await $.model.complete({
    model: 'haiku',
    system: 'You name coding sessions. Answer with the topic alone: two to four words, in the language of the messages, no quotes, no period, never the word Claude.',
    prompt: `Messages from the start of a session:\n\n${sample}\n\nTopic:`,
    maxTokens: 24,
    effort: 'low',
    timeoutMs: 20000,
  }).catch(() => null)
  pendingTopics.delete(id)
  if (!reply || !reply.isAnswered) return
  const name = clip(reply.text.replace(/\s+/g, ' ').replace(/^["'„“«]+|["'“”».]+$/g, '').trim())
  if (!name) return
  topicCache.set(id, { topic: name, at: Date.now() })
  await $.store.set(`topic:${id}`, name).catch(() => undefined)
}

/** The deck row a person means: a tab id (`12`, `012`), or one of the old hotkeys (`c`). */
function rowAt(rows: readonly DeckRow[], ref: string): DeckRow | undefined {
  const v = ref.trim().toLowerCase()
  if (!v) return undefined
  return rows[/^\d+$/.test(v) ? parseInt(v, 10) - 1 : HOTKEYS.indexOf(v)]
}

async function gotoRow($: EngineInterface, ref: string): Promise<void> {
  const rows = await read($, roster)
  const row = rowAt(rows, ref)
  if (!row) { $.ui.toast(`No tab ${ref.trim() || '?'} on the deck`); return }
  const ok = await jumpTo($, row.tty)
  if (!ok) $.ui.toast(`No frame window on ${row.tty || 'an unknown tty'}`)
}

function meter(percent: number, width: number): [string, string] {
  const on = Math.round((Math.min(100, Math.max(0, percent)) / 100) * width)
  return ['█'.repeat(on), '░'.repeat(width - on)]
}

function money(usd: number): string { return `$${usd.toFixed(2)}` }

function ago(ms: number, now: number): string {
  const s = Math.max(0, Math.round((now - ms) / 1000))
  if (s < 60) return `${s}s`
  if (s < 3600) return `${Math.round(s / 60)}m`
  if (s < 86400) return `${Math.round(s / 3600)}h`
  return `${Math.round(s / 86400)}d`
}

// ---------------------------------------------------------------------------
// Engine-facing helpers: top-level declarations, as the validator asks.
// ---------------------------------------------------------------------------

async function paletteFor($: EngineInterface): Promise<Palette> {
  const over = await read($, themeOverride)
  const base = PALETTES[over ?? configuredTheme] ?? PALETTES.c64
  const pk = await read($, pokes)
  if (pk.border === null && pk.screen === null && pk.text === null) return base
  return {
    ...base,
    bg: pk.border === null ? base.bg : C64_COLORS[pk.border],
    screenBg: pk.screen === null ? base.screenBg : C64_COLORS[pk.screen],
    fg: pk.text === null ? base.fg : C64_COLORS[pk.text],
  }
}

// ---------------------------------------------------------------------------
// /pure: the C64 BASIC V2 command set, read as instructions to Claude Code.
// ---------------------------------------------------------------------------

const PURE_HELP = [
  'LOAD "$",8        directory: the saved sessions      LIST              the running sessions as program lines',
  'LOAD "NAME",8,1   jump to that session\'s tab         LOAD "*",8,1      open the deck',
  'RUN <text>        hand <text> to Claude as a prompt  CONT              ask Claude to continue',
  'INPUT "question"  ask Claude the question            STOP / END        break the running turn',
  'SAVE "NAME",8     snapshot every session now         VERIFY            check the snapshot against what runs',
  'GOTO <n>          jump to deck row n (1-9, a-z)      GOSUB <n> / RETURN  jump and come back',
  'POKE 53280,c      border (band) color 0-15           POKE 53281,c      screen color; POKE 646,c text color',
  'PRINT <expr>      evaluate: PEEK, FRE(0), TI$, CHR$  SYS 64738         reset: colors, theme, crab',
  'OPEN / CLOSE      open or close the deck             NEW               a fresh session in a new window',
  'DATA a,b / READ / RESTORE   a scratch list across sessions   CLR   forget the POKEs and the theme',
]

const READY = '\nREADY.'

async function pure($: EngineInterface, line: string): Promise<string> {
  const src = line.trim()
  const up = src.toUpperCase()
  const str = (re: RegExp): string | undefined => { const m = re.exec(src); return m ? (m[1] ?? '').trim() : undefined }

  if (up === '' || up === 'HELP') return PURE_HELP.join('\n') + READY
  if (/^REM\b/.test(up)) return 'READY.'

  if (/^(LOAD|DLOAD)\s*"?\$|^DIR\b|^CATALOG\b/.test(up)) {
    const rows = await read($, roster)
    const text = await $.fs.read(snapshotPath()).catch(() => '')
    let saved: { sessionId: string; project: string; tty: string }[] = []
    try { saved = (JSON.parse(text) as { sessions?: typeof saved }).sessions ?? [] } catch { /* no snapshot yet */ }
    const alive = new Set(rows.map(r => r.sessionId))
    const out = ['0 "CLAUDE CODE     " CC 2A']
    saved.forEach((sv, i) => {
      const name = sv.project.toUpperCase().slice(0, 16)
      out.push(`${String(i + 1).padEnd(4)} "${name}"${' '.repeat(Math.max(1, 18 - name.length))}${alive.has(sv.sessionId) ? 'PRG' : 'PRG*  (closed, /deck restore)'}`)
    })
    out.push(`${Math.max(0, 664 - saved.length)} BLOCKS FREE.`)
    return out.join('\n') + READY
  }

  const loadName = str(/^LOAD\s*"([^"]*)"/i)
  if (loadName !== undefined) {
    if (loadName === '*' || loadName === '') {
      await refreshRoster($)
      const opened = await $.ui.open({ id: PANE, title: 'TASKS', focus: true, columns: DECK_COLUMNS })
      return `SEARCHING FOR *\nLOADING\n${opened.isPlaced ? '' : '(the deck waits for a wider terminal)\n'}READY.`
    }
    const rows = await read($, roster)
    const want = loadName.toUpperCase().replace(/\*$/, '')
    const row = rows.find(r => labelOf(r).toUpperCase().startsWith(want)) ?? rowAt(rows, loadName)
    if (!row) return `SEARCHING FOR ${loadName.toUpperCase()}\n?FILE NOT FOUND  ERROR` + READY
    const ok = await jumpTo($, row.tty)
    return `SEARCHING FOR ${loadName.toUpperCase()}\n${ok ? 'LOADING' : '?DEVICE NOT PRESENT  ERROR'}` + READY
  }

  if (/^LIST\b/.test(up)) {
    const rows = await read($, roster)
    if (rows.length === 0) return 'READY.'
    return rows.map((r, i) => `${(i + 1) * 10} ${r.isSelf ? 'REM ' : ''}${labelOf(r).toUpperCase()}: ${r.state.toUpperCase()}${r.reason ? ' ' + r.reason.toUpperCase() : ''}`).join('\n') + READY
  }

  const runText = str(/^RUN\b(.*)$/i)
  if (runText !== undefined) {
    const text = runText || 'Continue with the current task.'
    await $.prompt.submit({ text, asUser: true })
    return 'RUNNING'
  }
  if (/^CONT\b/.test(up)) {
    await $.prompt.submit({ text: 'Continue.', asUser: true })
    return 'CONTINUING'
  }
  const question = str(/^INPUT\s*"?([^"]*)"?/i)
  if (question !== undefined) {
    if (!question) return '?MISSING QUESTION  ERROR' + READY
    await $.prompt.submit({ text: question, asUser: true })
    return `? ${question}`
  }
  if (/^(STOP|END)\b/.test(up)) {
    if (!currentTurnId) return 'READY.'
    await $.turn.abort({ turnId: currentTurnId }).catch(() => undefined)
    return `BREAK IN TURN` + READY
  }

  const saveName = str(/^SAVE\s*"?([^",]*)"?/i)
  if (saveName !== undefined) {
    await refreshRoster($)
    return `SAVING ${(saveName || 'DECK').toUpperCase()}` + READY
  }
  if (/^VERIFY\b/.test(up)) {
    const rows = await read($, roster)
    const text = await $.fs.read(snapshotPath()).catch(() => '')
    let saved: { sessionId: string; project: string }[] = []
    try { saved = (JSON.parse(text) as { sessions?: typeof saved }).sessions ?? [] } catch { /* none */ }
    const alive = new Set(rows.map(r => r.sessionId))
    const gone = saved.filter(sv => !alive.has(sv.sessionId))
    return gone.length === 0
      ? 'VERIFYING\nOK' + READY
      : `VERIFYING\n?VERIFY ERROR: ${gone.length} saved session(s) not running: ${gone.map(g => g.project).join(', ')}\n(/deck restore brings them back)` + READY
  }

  const jump = str(/^(?:GOTO|GO TO|GOSUB)\s*(\S+)/i)
  if (jump !== undefined) {
    const rows = await read($, roster)
    const n = Number(jump)
    const row = Number.isFinite(n) ? rows[(n >= 10 ? n / 10 : n) - 1] : rows[HOTKEYS.indexOf(jump.toLowerCase())]
    if (!row) return "?UNDEF'D STATEMENT  ERROR" + READY
    if (/^GOSUB/i.test(up)) tabReturn.push(selfTty)
    const ok = await jumpTo($, row.tty)
    return ok ? `GOING TO ${row.project.toUpperCase()}` + READY : '?DEVICE NOT PRESENT  ERROR' + READY
  }
  if (/^RETURN\b/.test(up)) {
    const back = tabReturn.pop()
    if (!back) return '?RETURN WITHOUT GOSUB  ERROR' + READY
    const ok = await jumpTo($, back)
    return (ok ? 'RETURNED' : '?DEVICE NOT PRESENT  ERROR') + READY
  }

  const poke = /^POKE\s*(\d+)\s*,\s*(\d+)/i.exec(src)
  if (poke) {
    const addr = Number(poke[1]), value = Number(poke[2])
    if (value > 255 || addr > 65535) return '?ILLEGAL QUANTITY  ERROR' + READY
    const color = value & 15
    if (addr === 53280) await update($, pokes, pk => ({ ...pk, border: color }))
    else if (addr === 53281) await update($, pokes, pk => ({ ...pk, screen: color }))
    else if (addr === 646) await update($, pokes, pk => ({ ...pk, text: color }))
    else { machine ??= new C64Machine(); machine.poke(addr, value) }
    return 'READY.'
  }
  if (/^SYS\s*64738\b/.test(up)) {
    await update($, pokes, () => ({ border: null, screen: null, text: null }))
    await update($, themeOverride, () => null)
    tabReturn = []
    void runIntro($)
    return '    **** CLAUDE CODE RETRO DECK ****\n\n 64K RAM SYSTEM  38911 BASIC BYTES FREE' + READY
  }
  if (/^SYS\b/.test(up)) return 'READY.'
  if (/^CLR\b/.test(up)) {
    await update($, pokes, () => ({ border: null, screen: null, text: null }))
    await update($, themeOverride, () => null)
    return 'READY.'
  }

  if (/^OPEN\b/.test(up)) {
    await refreshRoster($)
    const opened = await $.ui.open({ id: PANE, title: 'TASKS', focus: true, columns: DECK_COLUMNS })
    return (opened.isPlaced ? 'DECK OPEN' : 'DECK WAITS FOR A WIDER TERMINAL') + READY
  }
  if (/^CLOSE\b/.test(up)) { await $.ui.close({ id: PANE }); return 'READY.' }
  if (/^NEW\b/.test(up)) {
    const root = await $.session.root()
    const ran = await $.process.run(['bash', `${$.plugin.root}/scripts/open-session.sh`, root], { timeoutMs: 10000 }).catch(() => null)
    return (ran && ran.exitCode === 0 ? 'NEW SESSION OPENED' : '?DEVICE NOT PRESENT  ERROR') + READY
  }

  const data = str(/^DATA\s*(.*)$/i)
  if (data !== undefined) {
    pureData.push(...data.split(',').map(x => x.trim().replace(/^"|"$/g, '')).filter(Boolean))
    await $.store.set('pure-data', pureData)
    return 'READY.'
  }
  if (/^READ\b/.test(up)) {
    if (pureDataPtr >= pureData.length) return '?OUT OF DATA  ERROR' + READY
    return pureData[pureDataPtr++] + READY
  }
  if (/^RESTORE\b/.test(up)) { pureDataPtr = 0; return 'READY.' }

  if (/^(PRINT|\?)/.test(up)) {
    const status = await read($, own)
    const pk = await read($, pokes)
    const expr = src
      .replace(/FRE\s*\(\s*-?\d+\s*\)/gi, String(status ? Math.max(0, status.window - status.ctxTokens) : 38911))
      .replace(/PEEK\s*\(\s*53280\s*\)/gi, String(pk.border ?? 14))
      .replace(/PEEK\s*\(\s*53281\s*\)/gi, String(pk.screen ?? 6))
      .replace(/PEEK\s*\(\s*646\s*\)/gi, String(pk.text ?? 14))
    const scratch = new C64Machine()
    scratch.clearScreen()
    scratch.submit(expr)
    const rows = scratch.snapshot().rows.map(r => r.text.trimEnd()).filter(Boolean)
    return rows.join('\n')
  }

  return '?SYNTAX  ERROR' + READY
}

// ---------------------------------------------------------------------------
// /emul: the emulated C64 in a pane.
// ---------------------------------------------------------------------------

function diskFile(): Record<string, string> {
  return machine ? Object.fromEntries(machine.disk) : {}
}

async function emulMachine($: EngineInterface): Promise<C64Machine> {
  if (machine) return machine
  machine = new C64Machine()
  const saved = await $.store.get('c64-disk').catch(() => undefined)
  if (saved && typeof saved === 'object') {
    for (const [k, v] of Object.entries(saved as Record<string, unknown>)) if (typeof v === 'string') machine.disk.set(k, v)
  }
  return machine
}

async function syncEmul($: EngineInterface): Promise<void> {
  if (!machine) return
  const shot: EmulScreen = machine.snapshot()
  await update($, emul, () => shot)
  if (machine.diskDirty) {
    machine.diskDirty = false
    await $.store.set('c64-disk', diskFile()).catch(() => undefined)
  }
}

async function emulFeed($: EngineInterface, text: string): Promise<void> {
  const m = await emulMachine($)
  m.submit(text)
  if (m.isRunning && !emulTimer) {
    emulTimer = $.clock.every(60, async () => {
      const still = m.step(1500)
      await syncEmul($)
      if (!still && emulTimer) { emulTimer.cancel(); emulTimer = null }
    })
  }
  await syncEmul($)
}

function screenText(shot: EmulScreen): string {
  return shot.rows.map(r => r.text.trimEnd()).join('\n').replace(/\n+$/, '')
}

// Every session running this mod writes one sidecar file; the deck in every
// session reads them all. The engine's own registry supplies the rest.
async function publish($: EngineInterface, status: OwnStatus): Promise<void> {
  if (uninstalled) return
  if (!home || !sessionId) return
  const row: DeckRow = {
    sessionId,
    pid: selfPid,
    name: '',
    cwd: await $.session.root(),
    project: status.project,
    state: status.state,
    reason: status.reason,
    model: status.model,
    usd: status.usd,
    ctxPercent: status.ctxPercent,
    turns: status.turns,
    tty: selfTty,
    isPeerMod: true,
    isSelf: false,
    updatedAt: status.updatedAt,
  }
  await $.fs.write(`${sidecarDir()}/${sessionId}.json`, JSON.stringify(row)).catch(() => undefined)
}

async function measure($: EngineInterface): Promise<OwnStatus> {
  const [usage, model, turns, root, now] = await Promise.all([
    $.session.usage(),
    $.session.model(),
    $.session.turns(),
    $.session.root(),
    $.clock.now(),
  ])
  // Only the windows the plan has: Claude Ultra reports no five_hour, and a missing one is not 0%.
  const limit = (kind: string): number | null => usage.rateLimits.find(r => r.kind === kind)?.percentUsed ?? null
  const status: OwnStatus = {
    model,
    usd: usage.cost?.usd ?? 0,
    ctxPercent: usage.context.percent ?? 0,
    ctxTokens: usage.context.tokens ?? 0,
    window: usage.context.window,
    turns,
    project: isProjectName(projectOf(root)) ? projectOf(root) : (await topicOf($, sessionId, root, Date.now())) || projectOf(root),
    fiveHour: limit('five_hour'),
    sevenDay: limit('seven_day'),
    spend: limit('spend_limit'),
    state,
    reason,
    updatedAt: now,
  }
  await update($, own, () => status)
  await publish($, status)
  return status
}

async function tmux($: EngineInterface, args: string[]): Promise<{ exitCode: number; stdout: string }> {
  return $.process
    .run(['tmux', '-L', TMUX_SOCK, ...args], { timeoutMs: 5000 })
    .catch(() => ({ exitCode: 1, stdout: '' }))
}

// The window whose pane runs on this tty comes to the front of the frame.
async function jumpTo($: EngineInterface, tty: string): Promise<boolean> {
  if (!tty) return false
  const panes = await tmux($, ['list-panes', '-a', '-F', '#{pane_tty} #{window_id}'])
  const hit = panes.stdout.split('\n').map(l => l.trim().split(' ')).find(([t]) => t === tty)
  if (!hit || !hit[1]) return false
  const ran = await tmux($, ['select-window', '-t', hit[1]])
  return ran.exitCode === 0
}

// This session needs the person. Switch the frame to it only while the
// tab they look at is itself busy (so they are waiting there, not typing).
async function attention($: EngineInterface): Promise<void> {
  const now = await $.clock.now()
  if (!autoSwitch || now - lastSwitchAt < SWITCH_COOLDOWN_MS) return
  // The active pane of the frame's current window: frame.sh keeps Claude Code's pane active.
  const front = await tmux($, ['display-message', '-p', '-t', 'c64:', '#{pane_tty}'])
  const frontTty = front.exitCode === 0 ? front.stdout.trim() : ''
  if (!frontTty || frontTty === selfTty) return
  const rows = await read($, roster)
  const looking = rows.find(r => r.tty === frontTty)
  if (!looking || looking.state !== 'busy') {
    void $.ui.notify(`${projectOf(await $.session.root())} needs you (${reason})`, { title: 'Retro Deck' })
    return
  }
  lastSwitchAt = now
  await jumpTo($, selfTty)
}

async function setState($: EngineInterface, next: DeckState, why = ''): Promise<void> {
  state = next
  reason = why
  await measure($)
  if (next === 'ask') await attention($)
}

type Registry = {
  pid: number; sessionId: string; cwd: string; name?: string
  status?: string; updatedAt?: number; statusUpdatedAt?: number
}

async function readJsonDir<T>($: EngineInterface, dir: string, keep: (v: T) => boolean): Promise<T[]> {
  const out: T[] = []
  const entries = await $.fs.list(dir).catch(() => [])
  for (const entry of entries) {
    if (entry.kind !== 'file' || !entry.name.endsWith('.json')) continue
    const text = await $.fs.read(`${dir}/${entry.name}`).catch(() => '')
    try {
      const parsed = JSON.parse(text) as T
      if (keep(parsed)) out.push(parsed)
    } catch { /* half-written: next tick */ }
  }
  return out
}

/**
 * The pane ttys of the C64 server, and whether any terminal shows it. With no client, its
 * windows are closed for the person: frame.sh ends the server with the last client, but a
 * server from before that keeps running unseen. Null when there is no server.
 */
async function frameTtys($: EngineInterface): Promise<{ panes: Set<string>; isShown: boolean } | null> {
  const panes = await tmux($, ['list-panes', '-a', '-F', '#{pane_tty}'])
  if (panes.exitCode !== 0) return null
  const clients = await tmux($, ['list-clients', '-F', '#{client_tty}'])
  return { panes: new Set(panes.stdout.split('\n').filter(Boolean)), isShown: clients.stdout.trim() !== '' }
}

// One refresh at a time: the tick and the event-driven calls (open, jump, turn end) would
// otherwise overlap, and the older one could land last.
let rosterRun: Promise<void> | null = null
let rosterLoaded = false             // until the first answer the pane says SEARCHING, not 0 TABS

function refreshRoster($: EngineInterface): Promise<void> {
  if (rosterRun) return rosterRun
  rosterRun = refreshRosterOnce($).finally(() => { rosterRun = null })
  return rosterRun
}

async function refreshRosterOnce($: EngineInterface): Promise<void> {
  if (!home || uninstalled) return
  const now = await $.clock.now()
  const registry = await readJsonDir<Registry>($, registryDir(), r => Boolean(r.pid && r.sessionId))

  // One ps call: which pids live, and on which tty each runs.
  const ttyByPid = new Map<number, string>()
  if (registry.length > 0) {
    const ps = await $.process
      .run(['ps', '-o', 'pid=,tty=', '-p', registry.map(r => String(r.pid)).join(',')], { timeoutMs: 5000 })
      .catch(() => ({ stdout: '' }))
    for (const line of ps.stdout.split('\n')) {
      const m = line.trim().match(/^(\d+)\s+(\S+)/)
      if (m) ttyByPid.set(Number(m[1]), m[2] === '??' || m[2] === '?' ? '' : `/dev/${m[2]}`)
    }
    // No line at all: ps failed or hung. That says nothing about who lives: keep the last
    // roster and snapshot instead of flashing 0 TABS and saving an empty deck for restore.
    if (ttyByPid.size === 0) return
  }
  // Only sessions someone can see: a frame window counts while a terminal shows the server.
  const frame = await frameTtys($)
  const isHidden = (tty: string) => frame !== null && !frame.isShown && frame.panes.has(tty)

  const sidecars = new Map<string, DeckRow>()
  const dead: string[] = []
  const livingIds = new Set(registry.filter(r => ttyByPid.has(r.pid)).map(r => r.sessionId))
  for (const row of await readJsonDir<DeckRow>($, sidecarDir(), r => Boolean(r.sessionId))) {
    sidecars.set(row.sessionId, row)
    if (!livingIds.has(row.sessionId) && now - row.updatedAt > 60 * 60 * 1000) dead.push(`${sidecarDir()}/${row.sessionId}.json`)
  }
  if (dead.length > 0) await $.process.run(['rm', '-f', ...dead], { timeoutMs: 5000 }).catch(() => undefined)

  const rows: DeckRow[] = []
  for (const r of registry) {
    if (!ttyByPid.has(r.pid)) continue // process gone
    if (isHidden(ttyByPid.get(r.pid) ?? '') && r.sessionId !== sessionId) continue // its terminal was closed
    const side = sidecars.get(r.sessionId)
    const sideFresh = side !== undefined && now - side.updatedAt < PEER_FRESH_MS
    const seen = r.statusUpdatedAt ?? r.updatedAt ?? 0
    let rowState: DeckState = r.status === 'busy' ? 'busy' : now - seen > STALE_AFTER_MS ? 'stale' : 'idle'
    let why = ''
    if (sideFresh && side) {
      rowState = side.state
      why = side.reason
    }
    if (r.sessionId === sessionId) {
      selfPid = r.pid
      selfTty = ttyByPid.get(r.pid) ?? ''
      rowState = state
      why = reason
    }
    const project = projectOf(r.cwd)
    const topic = isProjectName(project) ? '' : await topicOf($, r.sessionId, r.cwd, now)
    rows.push({
      sessionId: r.sessionId,
      pid: r.pid,
      name: topic || (r.name ?? ''),
      cwd: r.cwd,
      project,
      state: rowState,
      reason: why,
      model: side?.model ?? '',
      usd: side?.usd ?? 0,
      ctxPercent: side?.ctxPercent ?? 0,
      turns: side?.turns ?? 0,
      tty: ttyByPid.get(r.pid) ?? '',
      isPeerMod: sideFresh,
      isSelf: r.sessionId === sessionId,
      updatedAt: side?.updatedAt ?? seen,
    })
  }

  const rank: Record<DeckState, number> = { ask: 0, done: 1, busy: 2, idle: 3, stale: 4 }
  rows.sort((a, b) => rank[a.state] - rank[b.state] || b.updatedAt - a.updatedAt)
  rosterLoaded = true
  await update($, roster, () => rows)

  // The snapshot the restore script reopens after the CLI was closed by mistake:
  // every live session, in tty order, with what `claude --resume` needs.
  const snapshot = {
    savedAt: now,
    sessions: [...rows]
      .sort((a, b) => a.tty.localeCompare(b.tty))
      .map(r => ({ sessionId: r.sessionId, cwd: r.cwd, project: labelOf(r), tty: r.tty })),
  }
  await $.fs.write(snapshotPath(), JSON.stringify(snapshot, null, 2)).catch(() => undefined)
}

async function runIntro($: EngineInterface): Promise<void> {
  if (!showCrab && !showBanner) return
  const startedAt = await $.clock.now()
  await update($, intro, () => ({ x: 0, dir: 1, frame: 0, startedAt }))
  const timer = $.clock.every(INTRO_FRAME_MS, async () => {
    const now = await $.clock.now()
    if (now - startedAt > INTRO_MS) {
      timer.cancel()
      await update($, intro, () => null)
      return
    }
    await update($, intro, cur => {
      if (cur === null) return cur
      const frame = cur.frame + 1
      const walking = frame % CRAB_CYCLE < CRAB_WALK
      const right = Math.max(1, (cur.width ?? 80) - CRAB_W - 1)
      let x = walking ? cur.x + cur.dir : cur.x
      let dir = cur.dir
      if (x >= right) { x = right; dir = -1 }
      if (x <= 0) { x = 0; dir = 1 }
      return { ...cur, x, dir, frame }
    })
  })
}

async function deckCommand($: EngineInterface, args: string): Promise<{ text: string }> {
  const [verb, arg] = args.trim().split(/\s+/)
  if (verb === 'theme') {
    if (arg && PALETTES[arg]) {
      await update($, themeOverride, () => arg)
      return { text: `Deck theme: ${arg}` }
    }
    await update($, themeOverride, () => null)
    return { text: `Deck theme back to the configured one (${configuredTheme}). Known: ${Object.keys(PALETTES).join(', ')}` }
  }
  if (verb === 'jump') {
    const rows = await read($, roster)
    const row = rowAt(rows, arg ?? '')
    if (!row) return { text: `No deck row ${arg ?? ''}: give the tab id (001) as the deck shows it.` }
    const ok = await jumpTo($, row.tty)
    return { text: ok ? `Jumped to ${row.project} (${row.tty}).` : `No frame window found on ${row.tty || 'an unknown tty'} (jumps need LOAD "*",8,1).` }
  }
  if (verb === 'intro') {
    if (inFrame) {
      // The header strip (boot.py --band) watches this file and sends its two crabs dancing.
      await $.fs.write(`${home}/.claude/retro-deck/party-${frameSock}`, String(Date.now())).catch(() => undefined)
      return { text: 'Crabs released in the header.' }
    }
    void runIntro($)
    return { text: 'Crab released.' }
  }
  if (verb === 'setup') return { text: await setupCommand($, home, arg === 'apply') }
  if (verb === 'uninstall') {
    const text = await uninstallCommand($, home, arg === 'apply', frameSock)
    if (arg === 'apply') uninstalled = true
    return { text }
  }
  if (verb === 'restore') {
    const ran = await $.process
      .run(['bash', `${$.plugin.root}/scripts/restore.sh`], { timeoutMs: 120000 })
      .catch(err => ({ exitCode: 1, stdout: '', stderr: String(err) }))
    return { text: ran.exitCode === 0 ? ran.stdout.trim() || 'Nothing to restore: every saved session is still running.' : `restore failed: ${ran.stderr.trim()}` }
  }
  // Open first, fill after: CLI 2.1.314 gives up on a command that has not answered within
  // a few seconds. The pane says SEARCHING FOR * until the roster arrives.
  void refreshRoster($)
  const opened = await $.ui.open({ id: PANE, title: 'TASKS', focus: true, columns: DECK_COLUMNS })
  return { text: opened.isPlaced ? 'Tasks opened. Type a tab number and Enter in the pane to jump, or click a row.' : 'Tasks wait for a wider terminal.' }
}

// ---------------------------------------------------------------------------
// The module.
// ---------------------------------------------------------------------------

export const register: Register = (on, options) => {
  configuredTheme = typeof options.theme === 'string' ? options.theme : 'c64'
  autoSwitch = options.autoSwitch === true
  autoOpen = options.autoOpen !== false
  showBanner = options.banner !== false
  showCrab = options.crab !== false
  introEvery = typeof options.introEvery === 'number' && options.introEvery >= 0 ? Math.floor(options.introEvery) : 60

  on('session.start', async ($, e, next) => {
    home = (await $.env.get('HOME')) ?? ''
    if (home) void refreshShell($, home)
    sessionId = await $.session.id()
    await $.command.register({
      name: 'deck',
      description: 'Retro deck: open the deck; "theme c64|amiga|cga"; "jump <hotkey>"; "restore" reopens closed sessions; "intro" sends the crabs dancing',
    })
    // Since Claude Code 2.1.3xx /tasks is built in and the host refuses the name. A refusal
    // must not end session.start: everything below (frame, timers, /pure, /emul) hangs on it.
    await $.command
      .register({ name: 'tasks', description: 'Claude Code Tasks: the deck of every running session, by tab number; same as /deck' })
      .catch(() => undefined)
    await $.command.register({
      name: 'pure',
      description: 'C64 BASIC V2 commands read as Claude Code actions: LOAD "$",8 · LIST · RUN <text> · GOTO <n> · POKE 53280,c · SYS 64738 · HELP',
    })
    await $.command.register({
      name: 'emul',
      description: 'A Commodore 64 in a pane: BASIC V2 with screen, color RAM and disk 8. "/emul" opens it, "/emul <line>" types a line',
    })
    const savedData = await $.store.get('pure-data').catch(() => undefined)
    if (Array.isArray(savedData)) pureData = savedData.filter((x): x is string => typeof x === 'string')
    const started = await next(e)
    await refreshRoster($)
    await measure($)
    appleTerminal = (await $.env.get('TERM_PROGRAM')) === 'Apple_Terminal'
    frameSock = (await $.env.get('C64_FRAME')) ?? ''
    inFrame = frameSock !== ''        // frame.sh: the header shows crabs and banner
    if (!inFrame) void runIntro($)
    if (introEvery > 0 && !inFrame) {
      // The crab comes back every so often; never over a question that waits.
      $.clock.every(introEvery * 1000, async () => {
        if (state !== 'ask' && (await read($, intro)) === null) void runIntro($)
      })
    }
    if (autoOpen && e.surface !== null) void $.ui.open({ id: PANE, title: 'TASKS', columns: DECK_COLUMNS })
    $.clock.every(ROSTER_EVERY_MS, async () => {
      await refreshRoster($)
      if (isWorking) await measure($)
    })
    return started
  })

  on('command.run', { command: 'deck' }, ($, e) => deckCommand($, e.args))
  on('command.run', { command: 'tasks' }, ($, e) => deckCommand($, e.args))

  on('command.run', { command: 'pure' }, async ($, e) => {
    const text = await pure($, e.args).catch(err => `?${String((err as Error)?.message ?? err).toUpperCase()}  ERROR` + READY)
    return { text }
  })

  on('command.run', { command: 'emul' }, async ($, e) => {
    const line = e.args.trim()
    await emulMachine($)
    if (line) {
      await emulFeed($, line)
      const shot = await read($, emul)
      return { text: shot ? screenText(shot) : 'READY.' }
    }
    await syncEmul($)
    const opened = await $.ui.open({ id: C64_PANE, title: 'C64', focus: true })
    return { text: opened.isPlaced ? 'The C64 is on. Type a line in its pane and press Enter; SYS 64738 resets it.' : 'The C64 waits for a wider terminal; "/emul <line>" types blind meanwhile.' }
  })

  on('prompt.submit', async ($, e, next) => {
    isWorking = true
    await setState($, 'busy')
    return next(e)
  }).catch(($, e, next) => next(e))

  on('turn.start', async ($, e, next) => {
    isWorking = true
    currentTurnId = e.turnId
    if (state !== 'busy') await setState($, 'busy')
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    isWorking = false
    await setState($, 'done', e.reason === 'answer' ? '' : e.reason)
    return next(e)
  })

  // A question to the person is attention, for as long as the tool waits.
  on('tool.call', { tool: 'AskUserQuestion' }, async ($, e, next) => {
    await setState($, 'ask', 'question')
    const ran = await next(e)
    await setState($, 'busy')
    return ran
  }).catch(($, e, next) => next(e))

  // The permission dialog: from the classic PermissionRequest to the call's end.
  on('classic.PermissionRequest', async ($, e, next) => {
    await setState($, 'ask', `permission: ${e.tool_name}`)
    return next(e)
  }).catch(($, e, next) => next(e))

  on('tool.call', async ($, e, next) => {
    const ran = await next(e)
    if (state === 'ask' && reason.startsWith('permission')) await setState($, 'busy')
    return ran
  }).catch(($, e, next) => next(e))

  // idle_prompt is Claude Code saying it waits for the next prompt after a minute: that is
  // DONE, not a question (found on Windows, 0.12.0-beta.2: a red ASK idle_prompt). auth_success neither.
  on('classic.Notification', async ($, e, next) => {
    const notAsking = ['permission_prompt', 'idle_prompt', 'auth_success']
    if (!notAsking.includes(e.notification_type) && state !== 'ask') {
      await setState($, 'ask', e.notification_type)
    }
    return next(e)
  }).catch(($, e, next) => next(e))

  on('classic.Elicitation', async ($, e, next) => {
    await setState($, 'ask', 'mcp question')
    return next(e)
  }).catch(($, e, next) => next(e))

  // -- the band above the prompt: intro first, then one status row ----------

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) return next(e)
    const pal = await paletteFor($)
    const { Box, Text } = $.ui.resolve(e)
    const width = e.props.bodyColumns
    const running = await read($, intro)

    if (running !== null) {
      if (running.width !== width) {
        // Tell the animation how wide the band is; the timer, not the drawing, writes it.
        void $.clock.after(1, () => void update($, intro, cur => (cur === null ? cur : { ...cur, width })))
      }
      const sprite = showCrab ? crabSprite(appleTerminal, running.dir, running.frame) : []
      const x = Math.min(running.x, Math.max(0, width - CRAB_W))
      const tail = Math.max(0, width - x - CRAB_W)
      const bannerRoom = Math.max(0, e.props.maxRows - sprite.length)
      const lines = showBanner ? pal.banner.slice(0, bannerRoom) : []
      const inner = Math.max(0, width - 4)
      return (
        <Box flexDirection="column" width="100%" backgroundColor={pal.bg}>
          {sprite.map((row, i) => (
            <Box key={`crab:${i}`} backgroundColor={pal.bg}>
              {x > 0 && <Text backgroundColor={pal.bg}>{' '.repeat(x)}</Text>}
              {row.map(cell => (
                <Text color={cell.cut ? EYE : pal.crab} backgroundColor={cell.cut ? pal.crab : pal.bg}>{cell.text}</Text>
              ))}
              {tail > 0 && <Text backgroundColor={pal.bg}>{' '.repeat(tail)}</Text>}
            </Box>
          ))}
          {lines.map((line, i) => (
            <Box key={`banner:${i}`} backgroundColor={pal.bg}>
              <Text backgroundColor={pal.bg}>{'  '}</Text>
              <Text backgroundColor={pal.screenBg} color={pal.screenFg} bold={i === 0}>{line.slice(0, inner).padEnd(inner)}</Text>
              <Text backgroundColor={pal.bg}>{'  '}</Text>
            </Box>
          ))}
        </Box>
      )
    }

    return next(e)
  })

  // -- the prompt footer: this session's figures in the line of the mode labels --

  on('ui.render', { component: 'SessionMode' }, async ($, e, next) => {
    const status = await read($, own)
    if (status === null) return next(e)
    const pal = await paletteFor($)
    const { Box, Text } = $.ui.resolve(e)
    const [onCells, offCells] = meter(status.ctxPercent, 8)
    const stateWord = status.state === 'ask' ? ` ASK ${status.reason} ` : ` ${status.state.toUpperCase()} `
    const modes = e.props.modes.join(' & ')
    const dot = <Text color={pal.limits}>{' · '}</Text>
    // Drawn on the screen's own ground, so no color of the band's ground or the screen's.
    return (
      <Box>
        {isProjectName(status.project) && <Text color={pal.project} bold>{status.project}</Text>}
        {isProjectName(status.project) && dot}
        <Text color={pal.limits}>{status.model.replace(/^claude-/, '')}</Text>
        {dot}
        <Text color={pal.limits}>ctx </Text>
        <Text color={pal.limits} bold>{onCells}</Text>
        <Text color={pal.limits}>{offCells}</Text>
        <Text color={pal.limits}> {status.ctxPercent}%</Text>
        {dot}
        <Text color={pal.limits}>{money(status.usd)}</Text>
        {dot}
        <Text color={pal.limits}>turn {status.turns}</Text>
        {dot}
        {limitsText(status) !== '' && <Text color={pal.limits}>{limitsText(status)}</Text>}
        {limitsText(status) !== '' && dot}
        {status.state === 'ask'
          ? <Text backgroundColor={pal.askBg} color={pal.askFg} bold>{stateWord}</Text>
          : <Text color={pal.limits} bold>{stateWord}</Text>}
        {modes.length > 0 && <Text dimColor>{'  ' + modes}</Text>}
      </Box>
    )
  })

  // -- the C64 pane: the emulated screen and its keyboard line ---------------

  on('ui.render', { component: 'Pane', requestId: C64_PANE }, async ($, e) => {
    const shot = await read($, emul)
    const els = $.ui.resolve(e)
    const { Box, Text } = els
    const Input = 'Input' in els ? els.Input : null   // the mobile app draws no field yet
    const border = C64_COLORS[shot?.border ?? 14]
    const screen = C64_COLORS[shot?.background ?? 6]
    const rows = shot?.rows ?? []
    const cursorOn = shot !== null && !shot.running
    return (
      <Box flexDirection="column" backgroundColor={border} width="100%" height="100%">
        <Text backgroundColor={border} color={screen}>{' '}</Text>
        {rows.map((row, r) => {
          const runs: { text: string; color: number }[] = []
          for (let c = 0; c < row.text.length; c++) {
            let color = row.colors[c] ?? 14
            if (cursorOn && shot!.cursor.row === r && shot!.cursor.col === c) color = shot!.cursor.color | 16
            const last = runs[runs.length - 1]
            if (last && last.color === color) last.text += row.text[c]
            else runs.push({ text: row.text[c], color })
          }
          return (
            <Box key={`c64:${r}`} backgroundColor={border}>
              <Text backgroundColor={border}>{'  '}</Text>
              {runs.map(run => (
                <Text
                  color={run.color & 16 ? screen : C64_COLORS[run.color & 15]}
                  backgroundColor={run.color & 16 ? C64_COLORS[run.color & 15] : screen}
                >{run.text}</Text>
              ))}
            </Box>
          )
        })}
        <Text backgroundColor={border} color={screen}>{' '}</Text>
        <Box backgroundColor={border}>
          <Text backgroundColor={border} color={screen}>{'  '}</Text>
          {Input
            ? <Input
                key="c64:kbd"
                placeholder={shot?.waiting === 'input' ? 'the program asks: type the answer' : shot?.running ? 'running: Enter = RUN/STOP' : 'type a BASIC line, Enter = RETURN'}
                submitLabel="RETURN"
                autoFocus
                onSubmit={(value: string) => void emulFeed($, value)}
              />
            : <Text backgroundColor={border} color={C64_COLORS[1]}>{'type with /emul <line>'}</Text>}
        </Box>
      </Box>
    )
  })

  // -- the pane: every running session, colored by state --------------------

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const rows = await read($, roster)
    const pal = await paletteFor($)
    const els = $.ui.resolve(e)
    const { Box, Text, Button } = els
    const Input = 'Input' in els ? els.Input : null   // the mobile app draws no field yet
    const now = Date.now()
    const columns = e.props.bodyColumns
    const bodyRows = Math.max(8, e.props.scroll.bodyRows)
    const shown = rows.slice(0, Math.max(1, bodyRows - 6))
    const more = rows.length - shown.length
    const ageWidth = 4
    const nameWidth = Math.max(8, columns - 12 - ageWidth - 1)
    const needs = rows.filter(r => r.state === 'ask').length
    const working = rows.filter(r => r.state === 'busy').length
    // The pane is part of the screen: its ground is the screen's blue and every color one
    // that shows on it. The rows below the list are the engine's (ANSI 8), which the
    // Terminal profile paints in the same blue.
    // No color of its own: the terminal's ground is the profile's exact blue, while a hex
    // blue rounds to a greyer step of Apple Terminal's 256-color cube.
    const bg = undefined
    const line = <Text backgroundColor={bg} color={pal.screenFg}>{'─'.repeat(Math.max(1, columns))}</Text>

    return (
      <Box flexDirection="column" backgroundColor={bg} width="100%" height="100%">
        <Text backgroundColor={bg} color={pal.accent} bold>{' **** CLAUDE CODE TASKS ****'}</Text>
        {!rosterLoaded && <Text backgroundColor={bg} color={pal.screenFg}>{' SEARCHING FOR *'}</Text>}
        {rosterLoaded && <Box backgroundColor={bg}>
          <Text backgroundColor={bg} color={pal.screenFg}>{' '}{rows.length} TABS · </Text>
          <Text backgroundColor={bg} color={pal.ask} bold>{needs} ASK</Text>
          <Text backgroundColor={bg} color={pal.screenFg}> · </Text>
          <Text backgroundColor={bg} color={pal.busy}>{working} ACT</Text>
        </Box>}
        {line}
        {rosterLoaded && shown.length === 0 && <Text backgroundColor={bg} color={pal.screenFg}>{' READY.'}</Text>}
        {shown.map((row, i) => {
          const id = String(i + 1).padStart(3, '0')
          const stateColor = pal[row.state]
          const textColor = row.isSelf ? pal.accent : row.state === 'stale' ? pal.stale : row.state === 'idle' ? pal.idle : pal.fg
          const label = labelOf(row).slice(0, nameWidth).padEnd(nameWidth)
          const age = ago(row.updatedAt, now).padStart(ageWidth)
          return (
            <Box key={`row:${row.sessionId}`} backgroundColor={bg}>
              <Button key={`jump:${row.sessionId}`} plain onPress={() => void jumpTo($, row.tty)}>
                <Text backgroundColor={bg} color={row.isSelf ? pal.accent : pal.fg} bold={row.isSelf}>{' '}{id}</Text>
                <Text
                  backgroundColor={row.state === 'ask' ? pal.askBg : bg}
                  color={row.state === 'ask' ? pal.askFg : stateColor}
                  bold={row.state === 'ask' || row.state === 'busy'}
                >{'  '}{STATE_WORD[row.state]}</Text>
                <Text backgroundColor={bg} color={pal.screenFg}>{' '}{age}</Text>
                <Text backgroundColor={bg} color={textColor}>{'  '}{label}</Text>
              </Button>
            </Box>
          )
        })}
        {more > 0 && <Text backgroundColor={bg} color={pal.screenFg}>{` ${more} more below`}</Text>}
        {line}
        <Box backgroundColor={bg}>
          {Input
            ? <Input
                key="deck:goto"
                placeholder="tab number + Enter = jump · or click a row"
                submitLabel="GOTO"
                autoFocus
                onSubmit={(value: string) => void gotoRow($, value)}
              />
            : <Text backgroundColor={bg} color={pal.screenFg}>{' /deck jump <nr>'}</Text>}
        </Box>
      </Box>
    )
  })
}
