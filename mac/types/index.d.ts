/** Where a session stands, as the deck colors it. */
export type DeckState = 'busy' | 'ask' | 'done' | 'idle' | 'stale'

/** What this mod knows about one running session (its own, or a peer's sidecar). */
export type DeckRow = {
  sessionId: string
  pid: number
  name: string
  cwd: string
  project: string
  state: DeckState
  /** What needs the person: 'permission: <tool>', 'question', a notification type, or ''. */
  reason: string
  model: string
  usd: number
  ctxPercent: number
  turns: number
  tty: string
  /** True when the row's figures come from a session that runs this mod too. */
  isPeerMod: boolean
  isSelf: boolean
  updatedAt: number
}

/** This session's own figures, drawn in the band. */
export type OwnStatus = {
  model: string
  usd: number
  ctxPercent: number
  ctxTokens: number
  window: number
  turns: number
  project: string
  /** Percent used of each limit window the CLI reports; null when the plan has no such window (Claude Ultra: no 5h). */
  fiveHour: number | null
  sevenDay: number | null
  spend: number | null
  state: DeckState
  reason: string
  updatedAt: number
}

/** The start-of-session animation while it runs. */
export type Intro = {
  x: number
  dir: 1 | -1
  frame: number
  startedAt: number
  width?: number
}

/** VIC-II registers `/pure` lets a POKE set: C64 color indexes 0-15, or null for the palette's own. */
export type Pokes = {
  /** 53280: the band's ground. */
  border: number | null
  /** 53281: the banner's screen. */
  screen: number | null
  /** 646: the text. */
  text: number | null
}

/** The emulated C64's screen as `/emul` draws it: 25 rows of 40 cells, colors 0-15 plus 16 when reversed. */
export type EmulScreen = {
  rows: { text: string; colors: number[] }[]
  border: number
  background: number
  cursor: { row: number; col: number; color: number }
  running: boolean
  waiting: 'none' | 'input' | 'get'
  steps: number
}

declare module 'claude-code' {
  interface PluginState {
    'cc-retro-deck-mac': {
      own: OwnStatus | null
      roster: DeckRow[]
      themeOverride: string | null
      intro: Intro | null
      pokes: Pokes
      emul: EmulScreen | null
    }
  }
}
