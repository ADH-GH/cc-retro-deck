// ---------------------------------------------------------------------------
// A Commodore 64 BASIC V2 interpreter over an emulated 64K memory map.
//
// What is emulated, for now: the BASIC V2 keyword set, the 40x25 text screen
// at $0400 with its color RAM at $D800, the VIC-II border and background
// registers ($D020/$D021), the cursor color at 646, the jiffy clock (TI, TI$),
// a disk drive 8 as a name → listing map. No 6510, no SID, no sprites: the
// machine is the one a BASIC program sees, not the one a machine-code program
// sees. `/emul` in register.tsx draws the screen and feeds the keyboard.
// ---------------------------------------------------------------------------

export const COLS = 40
export const ROWS = 25
export const SCREEN = 1024
export const COLOR_RAM = 55296
export const BORDER = 53280
export const BACKGROUND = 53281
export const TEXT_COLOR = 646

/** One drawn row: the characters, and per cell the color index (0-15) plus 16 when reversed. */
export type ScreenRow = { text: string; colors: number[] }

export type Machine = {
  rows: ScreenRow[]
  border: number
  background: number
  cursor: { row: number; col: number; color: number }
  running: boolean
  waiting: 'none' | 'input' | 'get'
  steps: number
}

type Value = number | string
type Pos = { line: number; stmt: number }

type Tok =
  | { t: 'num'; v: number }
  | { t: 'str'; v: string }
  | { t: 'var'; v: string }
  | { t: 'kw'; v: string }
  | { t: 'op'; v: string }

const KEYWORDS = [
  'RESTORE', 'RETURN', 'INPUT#', 'PRINT#', 'VERIFY', 'RIGHT$', 'GOSUB', 'CLOSE', 'INPUT', 'PRINT',
  'LEFT$', 'STR$', 'CHR$', 'MID$', 'PEEK', 'POKE', 'DATA', 'READ', 'GOTO', 'STEP', 'THEN',
  'STOP', 'CONT', 'LIST', 'LOAD', 'SAVE', 'OPEN', 'WAIT', 'NEXT', 'END', 'FOR', 'DIM', 'LET',
  'RUN', 'REM', 'NEW', 'CLR', 'CMD', 'SYS', 'GET', 'TAB', 'SPC', 'NOT', 'AND', 'ASC', 'ABS',
  'ATN', 'COS', 'DEF', 'EXP', 'FRE', 'INT', 'LEN', 'LOG', 'POS', 'RND', 'SGN', 'SIN', 'SQR',
  'TAN', 'USR', 'VAL', 'IF', 'ON', 'OR', 'TO', 'FN', 'GO',
]

export class BasicError extends Error {
  constructor(public kind: string) { super(kind) }
}

const ERR = (k: string) => new BasicError(k)

/** Screen code (upper/graphics set) for a character, and back. */
function toScreen(ch: string): number {
  const c = ch.charCodeAt(0)
  if (c >= 64 && c < 96) return c - 64          // @ A-Z [ \ ] ^ _
  if (c >= 96 && c < 128) return c - 32         // lower case typed: shown as upper
  if (c >= 32 && c < 64) return c               // space, digits, punctuation
  return 32
}
function fromScreen(code: number): string {
  const c = code & 127
  if (c < 32) return String.fromCharCode(c + 64)
  if (c < 64) return String.fromCharCode(c)
  if (c < 96) return String.fromCharCode(c)     // 64-95 are graphics in the real set; shown as-is
  return ' '
}

function fmtNum(n: number): string {
  if (!Number.isFinite(n)) throw ERR('OVERFLOW')
  let s: string
  if (Number.isInteger(n) && Math.abs(n) < 1e9) s = String(n)
  else {
    const abs = Math.abs(n)
    if (abs >= 1e9 || (abs < 0.01 && abs > 0)) s = n.toExponential(8).replace(/\.?0+e/, 'E').replace('e', 'E').replace('E+', 'E+')
    else s = String(Number(n.toPrecision(9)))
  }
  return (n >= 0 ? ' ' : '') + s
}

export class C64 {
  mem = new Uint8Array(65536)
  program = new Map<number, string>()
  disk = new Map<string, string>()
  diskDirty = false

  private vars = new Map<string, Value>()
  private arrays = new Map<string, { dims: number[]; data: Value[] }>()
  private fns = new Map<string, { param: string; body: Tok[] }>()
  private forStack: { name: string; end: number; step: number; pos: Pos }[] = []
  private gosubStack: Pos[] = []
  private dataItems: string[] = []
  private dataPtr = 0
  private lines: number[] = []
  private pc: Pos | null = null
  private contPos: Pos | null = null
  private pending: { kind: 'input' | 'get'; targets: Tok[][]; pos: Pos } | null = null
  private reverse = false
  private quoteMode = false
  private col = 0
  private row = 0
  private rndSeed = 0.5
  private stepsDone = 0
  private jiffyBase: number
  private tiOffset = 0

  constructor(private now: () => number = () => Date.now()) {
    this.jiffyBase = now()
    this.powerOn()
  }

  // ---- the machine as the pane draws it -----------------------------------

  powerOn(): void {
    this.mem.fill(0)
    this.mem[BORDER] = 14
    this.mem[BACKGROUND] = 6
    this.mem[TEXT_COLOR] = 14
    this.program.clear()
    this.clearVars()
    this.clearScreen()
    this.print('    **** COMMODORE 64 BASIC V2 ****\n\n 64K RAM SYSTEM  38911 BASIC BYTES FREE\n\nREADY.\n')
    this.readyShown = true
    this.pc = null
    this.contPos = null
    this.pending = null
  }

  snapshot(): Machine {
    const rows: ScreenRow[] = []
    for (let r = 0; r < ROWS; r++) {
      let text = ''
      const colors: number[] = []
      for (let c = 0; c < COLS; c++) {
        const code = this.mem[SCREEN + r * COLS + c]
        text += fromScreen(code)
        colors.push((this.mem[COLOR_RAM + r * COLS + c] & 15) | (code & 128 ? 16 : 0))
      }
      rows.push({ text, colors })
    }
    return {
      rows,
      border: this.mem[BORDER] & 15,
      background: this.mem[BACKGROUND] & 15,
      cursor: { row: this.row, col: this.col, color: this.mem[TEXT_COLOR] & 15 },
      running: this.pc !== null && this.pending === null,
      waiting: this.pending?.kind ?? 'none',
      steps: this.stepsDone,
    }
  }

  get isRunning(): boolean { return this.pc !== null && this.pending === null }

  // ---- keyboard -----------------------------------------------------------

  /** A line typed at the keyboard: an answer to INPUT/GET, a program line, or an immediate statement. */
  submit(text: string): void {
    if (this.pending) {
      const p = this.pending
      this.pending = null
      if (p.kind === 'get') {
        this.assign(p.targets[0], text.length ? text[0] : '')
      } else {
        this.print(text + '\n')
        const parts = text.split(',')
        for (let i = 0; i < p.targets.length; i++) {
          const raw = (parts[i] ?? '').trim()
          const target = p.targets[i]
          if (this.isStringTarget(target)) this.assign(target, raw)
          else {
            const n = Number(raw)
            if (raw === '' || Number.isNaN(n)) { this.print('?REDO FROM START\n? '); this.pending = p; return }
            this.assign(target, n)
          }
        }
      }
      if (p.pos.line === -2) { this.pc = null; this.print('\nREADY.\n'); return }
      this.pc = p.pos
      return
    }
    if (this.isRunning) { this.breakRun(); return }
    const m = /^\s*(\d+)\s?(.*)$/.exec(text)
    if (m) {
      const n = Number(m[1])
      if (n > 63999) { this.error('SYNTAX'); return }
      if (m[2].trim() === '') this.program.delete(n)
      else this.program.set(n, m[2])
      this.contPos = null
      return
    }
    if (text.trim() === '') return
    try {
      this.readyShown = false
      this.execLine(text, { line: -1, stmt: 0 })
      if (!this.pc && !this.pending && !this.readyShown) this.print('\nREADY.\n')
      this.readyShown = false
    } catch (e) {
      this.report(e)
    }
  }

  /** RUN/STOP. */
  breakRun(): void {
    if (this.pc) {
      this.contPos = this.pc
      this.print(`\nBREAK IN ${this.pc.line}\nREADY.\n`)
      this.pc = null
      this.readyShown = true
    }
    this.pending = null
  }

  /** Runs up to `budget` statements of the program; returns whether it is still running. */
  step(budget = 2000): boolean {
    let n = 0
    const wasRunning = this.pc !== null
    this.errored = false
    try {
      while (this.pc && !this.pending && n < budget) {
        this.execAt(this.pc)
        n++
        this.stepsDone++
      }
    } catch (e) {
      this.report(e)
    }
    if (wasRunning && !this.pc && !this.pending && !this.errored && !this.readyShown) this.print('\nREADY.\n')
    this.readyShown = false
    return this.isRunning
  }
  private errored = false
  private readyShown = false

  // ---- screen -------------------------------------------------------------

  clearScreen(): void {
    this.mem.fill(32, SCREEN, SCREEN + COLS * ROWS)
    this.mem.fill(this.mem[TEXT_COLOR] & 15, COLOR_RAM, COLOR_RAM + COLS * ROWS)
    this.row = 0
    this.col = 0
    this.reverse = false
  }

  private scroll(): void {
    this.mem.copyWithin(SCREEN, SCREEN + COLS, SCREEN + COLS * ROWS)
    this.mem.fill(32, SCREEN + COLS * (ROWS - 1), SCREEN + COLS * ROWS)
    this.mem.copyWithin(COLOR_RAM, COLOR_RAM + COLS, COLOR_RAM + COLS * ROWS)
    this.mem.fill(this.mem[TEXT_COLOR] & 15, COLOR_RAM + COLS * (ROWS - 1), COLOR_RAM + COLS * ROWS)
  }

  private putChar(ch: string): void {
    const i = this.row * COLS + this.col
    this.mem[SCREEN + i] = toScreen(ch) | (this.reverse ? 128 : 0)
    this.mem[COLOR_RAM + i] = this.mem[TEXT_COLOR] & 15
    this.col++
    if (this.col >= COLS) { this.col = 0; this.newline() }
  }

  private newline(): void {
    this.row++
    this.reverse = false
    if (this.row >= ROWS) { this.row = ROWS - 1; this.scroll() }
  }

  /** PETSCII-ish output: control codes for colors, cursor and clear/home, text otherwise. */
  print(s: string): void {
    for (const ch of s) {
      const c = ch.charCodeAt(0)
      switch (c) {
        case 10: case 13: this.col = 0; this.newline(); continue
        case 147: this.clearScreen(); continue
        case 19: this.row = 0; this.col = 0; continue
        case 17: this.newline(); continue
        case 145: if (this.row > 0) this.row--; continue
        case 29: if (this.col < COLS - 1) this.col++; continue
        case 157: if (this.col > 0) this.col--; else if (this.row > 0) { this.row--; this.col = COLS - 1 } continue
        case 18: this.reverse = true; continue
        case 146: this.reverse = false; continue
        case 20: if (this.col > 0) { this.col--; this.mem[SCREEN + this.row * COLS + this.col] = 32 } continue
      }
      const color = PETSCII_COLORS[c]
      if (color !== undefined) { this.mem[TEXT_COLOR] = color; continue }
      if (c < 32) continue
      this.putChar(ch)
    }
  }

  // ---- memory -------------------------------------------------------------

  peek(addr: number): number {
    addr = this.addr(addr)
    if (addr === 160 || addr === 161 || addr === 162) {
      const j = this.jiffies()
      return addr === 162 ? j & 255 : addr === 161 ? (j >> 8) & 255 : (j >> 16) & 255
    }
    return this.mem[addr]
  }

  poke(addr: number, value: number): void {
    addr = this.addr(addr)
    if (value < 0 || value > 255 || !Number.isInteger(value)) throw ERR('ILLEGAL QUANTITY')
    this.mem[addr] = value
  }

  private addr(a: number): number {
    if (!Number.isFinite(a) || a < 0 || a > 65535) throw ERR('ILLEGAL QUANTITY')
    return Math.floor(a)
  }

  private jiffies(): number {
    return (Math.floor((this.now() - this.jiffyBase) * 60 / 1000) + this.tiOffset) % 5184000
  }

  // ---- program control ----------------------------------------------------

  private clearVars(): void {
    this.vars.clear()
    this.arrays.clear()
    this.fns.clear()
    this.forStack = []
    this.gosubStack = []
    this.dataPtr = 0
  }

  private collectData(): void {
    this.dataItems = []
    for (const n of this.lines) {
      const src = this.program.get(n)!
      for (const stmt of splitStatements(tokenize(src))) {
        if (stmt[0]?.t === 'kw' && stmt[0].v === 'DATA') {
          const raw = rawAfterKeyword(src, 'DATA')
          for (const item of splitData(raw)) this.dataItems.push(item)
        }
      }
    }
  }

  private run(from?: number): void {
    this.clearVars()
    this.lines = [...this.program.keys()].sort((a, b) => a - b)
    this.collectData()
    if (this.lines.length === 0) { this.pc = null; return }
    let line = this.lines[0]
    if (from !== undefined) {
      if (!this.program.has(from)) throw ERR("UNDEF'D STATEMENT")
      line = from
    }
    this.pc = { line, stmt: 0 }
    this.contPos = null
  }

  private gotoLine(n: number): Pos {
    if (!this.program.has(n)) throw ERR("UNDEF'D STATEMENT")
    return { line: n, stmt: 0 }
  }

  private nextPos(pos: Pos): Pos | null {
    const stmts = splitStatements(tokenize(this.program.get(pos.line) ?? ''))
    if (pos.stmt + 1 < stmts.length) return { line: pos.line, stmt: pos.stmt + 1 }
    const i = this.lines.indexOf(pos.line)
    if (i < 0 || i + 1 >= this.lines.length) return null
    return { line: this.lines[i + 1], stmt: 0 }
  }

  private execAt(pos: Pos): void {
    const src = this.program.get(pos.line)
    if (src === undefined) { this.pc = null; return }
    const stmts = splitStatements(tokenize(src))
    const stmt = stmts[pos.stmt]
    if (!stmt) { this.pc = this.nextPos(pos); return }
    const jump = this.execStatement(stmt, pos, src)
    if (this.pending) return
    if (jump === 'end') { this.pc = null; return }
    if (jump === 'skipline') {
      const i = this.lines.indexOf(pos.line)
      this.pc = i + 1 < this.lines.length ? { line: this.lines[i + 1], stmt: 0 } : null
      return
    }
    if (jump) { this.pc = jump; return }
    if (this.pc && this.pc.line === pos.line && this.pc.stmt === pos.stmt) this.pc = this.nextPos(pos)
  }

  private execLine(src: string, pos: Pos): void {
    const stmts = splitStatements(tokenize(src))
    for (let i = 0; i < stmts.length; i++) {
      const jump = this.execStatement(stmts[i], { ...pos, stmt: i }, src)
      if (this.pending || this.pc) return
      if (jump === 'end' || jump === 'skipline') return
      if (jump) { this.pc = jump; return }
    }
  }

  private report(e: unknown): void {
    const kind = e instanceof BasicError ? e.kind : 'SYNTAX'
    const where = this.pc && this.pc.line >= 0 ? ` IN ${this.pc.line}` : ''
    if (this.pc) this.contPos = null
    this.pc = null
    this.pending = null
    this.errored = true
    this.print(`\n?${kind} ERROR${where}\nREADY.\n`)
    if (!(e instanceof BasicError)) this.lastInternal = String((e as Error)?.message ?? e)
  }
  lastInternal = ''

  private error(kind: string): void { this.report(ERR(kind)) }

  // ---- statements ---------------------------------------------------------

  /** Returns a jump target, 'end', 'skipline', or undefined to continue. */
  private execStatement(stmt: Tok[], pos: Pos, src: string): Pos | 'end' | 'skipline' | undefined {
    if (stmt.length === 0) return undefined
    const head = stmt[0]
    const p = new Parser(stmt, this)
    if (head.t === 'kw') {
      p.i = 1
      switch (head.v) {
        case 'REM': case 'DATA': return undefined
        case 'PRINT': this.doPrint(p); return undefined
        case 'LET': this.doLet(p); return undefined
        case 'GOTO': return this.gotoLine(p.lineNumber())
        case 'GO': p.kw('TO'); return this.gotoLine(p.lineNumber())
        case 'GOSUB': {
          const target = this.gotoLine(p.lineNumber())
          this.gosubStack.push(pos)
          return target
        }
        case 'RETURN': {
          const back = this.gosubStack.pop()
          if (!back) throw ERR('RETURN WITHOUT GOSUB')
          return this.nextPos(back) ?? 'end'
        }
        case 'IF': {
          const cond = p.expr()
          if (p.peekKw('THEN')) p.i++
          else if (!p.peekKw('GOTO')) throw ERR('SYNTAX')
          if (!truthy(cond)) return 'skipline'
          if (p.peekKw('GOTO')) { p.i++; return this.gotoLine(p.lineNumber()) }
          if (p.peek()?.t === 'num') return this.gotoLine(p.lineNumber())
          const rest = stmt.slice(p.i)
          return this.execStatement(rest, pos, src)
        }
        case 'FOR': {
          const v = p.varName()
          p.op('=')
          const start = p.num()
          p.kw('TO')
          const end = p.num()
          let step = 1
          if (p.peekKw('STEP')) { p.i++; step = p.num() }
          this.setVar(v, start)
          this.forStack = this.forStack.filter(f => f.name !== v)
          this.forStack.push({ name: v, end, step, pos })
          return undefined
        }
        case 'NEXT': {
          const names: string[] = []
          while (p.peek()?.t === 'var') { names.push(p.varName()); if (p.peekOp(',')) p.i++ }
          if (names.length === 0) names.push(this.forStack.at(-1)?.name ?? '')
          for (const name of names) {
            const idx = this.forStack.map(f => f.name).lastIndexOf(name)
            if (idx < 0) throw ERR('NEXT WITHOUT FOR')
            const f = this.forStack[idx]
            const val = (this.getVar(f.name) as number) + f.step
            this.setVar(f.name, val)
            const done = f.step >= 0 ? val > f.end : val < f.end
            if (!done) {
              this.forStack.length = idx + 1
              return this.nextPos(f.pos) ?? 'end'
            }
            this.forStack.splice(idx, 1)
          }
          return undefined
        }
        case 'END': this.contPos = this.nextPos(pos); return 'end'
        case 'STOP': this.contPos = this.nextPos(pos); this.print(`\nBREAK IN ${pos.line}\nREADY.\n`); this.readyShown = true; return 'end'
        case 'CONT': {
          if (!this.contPos) throw ERR("CAN'T CONTINUE")
          this.lines = [...this.program.keys()].sort((a, b) => a - b)
          this.pc = this.contPos
          this.contPos = null
          return this.pc
        }
        case 'RUN': {
          const n = p.peek()?.t === 'num' ? p.lineNumber() : undefined
          this.clearScreenIfImmediate(pos)
          this.run(n)
          return this.pc ?? 'end'
        }
        case 'NEW': this.program.clear(); this.clearVars(); this.contPos = null; return 'end'
        case 'CLR': this.clearVars(); return undefined
        case 'LIST': this.doList(p); return undefined
        case 'DIM': {
          do {
            const name = p.varName()
            p.op('(')
            const dims: number[] = []
            do { dims.push(Math.floor(p.num()) + 1) } while (p.peekOp(',') && ++p.i)
            p.op(')')
            if (this.arrays.has(name)) throw ERR("REDIM'D ARRAY")
            const size = dims.reduce((a, b) => a * b, 1)
            if (size > 65536) throw ERR('OUT OF MEMORY')
            this.arrays.set(name, { dims, data: new Array(size).fill(name.endsWith('$') ? '' : 0) })
          } while (p.peekOp(',') && ++p.i)
          return undefined
        }
        case 'READ': {
          do {
            const target = p.target()
            if (this.dataPtr >= this.dataItems.length) throw ERR('OUT OF DATA')
            const raw = this.dataItems[this.dataPtr++]
            if (this.isStringTarget(target)) this.assign(target, raw)
            else { const n = Number(raw); if (Number.isNaN(n)) throw ERR('SYNTAX'); this.assign(target, n) }
          } while (p.peekOp(',') && ++p.i)
          return undefined
        }
        case 'RESTORE': this.dataPtr = 0; return undefined
        case 'INPUT': {
          let prompt = ''
          if (p.peek()?.t === 'str') { prompt = (p.next() as { v: string }).v; p.op(';') }
          const targets: Tok[][] = []
          do { targets.push(p.target()) } while (p.peekOp(',') && ++p.i)
          this.print(prompt + '? ')
          this.pending = { kind: 'input', targets, pos: this.nextPos(pos) ?? pos }
          if (pos.line < 0) this.pending.pos = { line: -2, stmt: 0 }
          return undefined
        }
        case 'GET': {
          const target = p.target()
          this.pending = { kind: 'get', targets: [target], pos: this.nextPos(pos) ?? pos }
          if (pos.line < 0) this.pending.pos = { line: -2, stmt: 0 }
          return undefined
        }
        case 'POKE': { const a = p.num(); p.op(','); const v = p.num(); this.poke(a, v); return undefined }
        case 'SYS': {
          const a = Math.floor(p.num())
          if (a === 64738) this.powerOn()
          else if (a === 58692 || a === 65520) this.clearScreen()
          return a === 64738 ? 'end' : undefined
        }
        case 'WAIT': p.num(); p.op(','); p.num(); if (p.peekOp(',')) { p.i++; p.num() } return undefined
        case 'ON': {
          const n = Math.floor(p.num())
          const isSub = p.peekKw('GOSUB')
          if (!isSub && !p.peekKw('GOTO')) throw ERR('SYNTAX')
          p.i++
          const targets: number[] = []
          do { targets.push(p.lineNumber()) } while (p.peekOp(',') && ++p.i)
          if (n < 0 || n > 255) throw ERR('ILLEGAL QUANTITY')
          if (n === 0 || n > targets.length) return undefined
          if (isSub) this.gosubStack.push(pos)
          return this.gotoLine(targets[n - 1])
        }
        case 'DEF': {
          p.kw('FN')
          const name = p.varName()
          p.op('(')
          const param = p.varName()
          p.op(')')
          p.op('=')
          this.fns.set(name, { param, body: stmt.slice(p.i) })
          return undefined
        }
        case 'LOAD': {
          const name = p.peek()?.t === 'str' ? (p.next() as { v: string }).v : '*'
          const listing = this.diskFind(name)
          this.print(`\nSEARCHING FOR ${name}\n`)
          if (listing === undefined) throw ERR('FILE NOT FOUND')
          this.print('LOADING\n')
          this.program.clear()
          for (const line of listing.split('\n')) {
            const m = /^(\d+)\s?(.*)$/.exec(line)
            if (m) this.program.set(Number(m[1]), m[2])
          }
          this.clearVars()
          return undefined
        }
        case 'SAVE': {
          const name = p.peek()?.t === 'str' ? (p.next() as { v: string }).v : ''
          if (!name) throw ERR('MISSING FILE NAME')
          this.disk.set(name.toUpperCase(), this.listing())
          this.diskDirty = true
          this.print(`\nSAVING ${name}\n`)
          return undefined
        }
        case 'VERIFY': {
          const name = p.peek()?.t === 'str' ? (p.next() as { v: string }).v : '*'
          const listing = this.diskFind(name)
          this.print(`\nSEARCHING FOR ${name}\n`)
          if (listing === undefined) throw ERR('FILE NOT FOUND')
          this.print(listing === this.listing() ? 'VERIFYING\nOK\n' : 'VERIFYING\n?VERIFY ERROR\n')
          return undefined
        }
        case 'OPEN': case 'CLOSE': case 'CMD': case 'PRINT#': case 'INPUT#': throw ERR('DEVICE NOT PRESENT')
        default: throw ERR('SYNTAX')
      }
    }
    if (head.t === 'var') { p.i = 0; this.doLet(p); return undefined }
    throw ERR('SYNTAX')
  }

  private clearScreenIfImmediate(_pos: Pos): void { /* a real C64 does not clear on RUN; kept for symmetry */ }

  private doLet(p: Parser): void {
    const target = p.target()
    p.op('=')
    const v = p.expr()
    this.assign(target, v)
  }

  private doPrint(p: Parser): void {
    let newline = true
    while (p.peek()) {
      const t = p.peek()!
      if (t.t === 'op' && t.v === ';') { p.i++; newline = false; continue }
      if (t.t === 'op' && t.v === ',') { p.i++; newline = false; this.tabTo(Math.floor(this.col / 10 + 1) * 10); continue }
      if (t.t === 'kw' && t.v === 'TAB') {
        p.i++; p.op('('); const n = Math.floor(p.num()); p.op(')')
        this.tabTo(n); newline = false; continue
      }
      if (t.t === 'kw' && t.v === 'SPC') {
        p.i++; p.op('('); const n = Math.floor(p.num()); p.op(')')
        this.print(' '.repeat(Math.max(0, Math.min(n, 255)))); newline = false; continue
      }
      const v = p.expr()
      this.print(typeof v === 'number' ? fmtNum(v) + ' ' : v)
      newline = true
    }
    if (newline) this.print('\n')
  }

  private tabTo(colTarget: number): void {
    if (colTarget >= COLS) { this.print('\n'); return }
    while (this.col < colTarget) this.print(' ')
  }

  private doList(p: Parser): void {
    let from = -Infinity, to = Infinity
    if (p.peek()?.t === 'num') { from = p.lineNumber(); to = from }
    if (p.peekOp('-')) { p.i++; to = p.peek()?.t === 'num' ? p.lineNumber() : Infinity }
    this.print('\n')
    for (const n of [...this.program.keys()].sort((a, b) => a - b)) {
      if (n < from || n > to) continue
      this.print(`${n} ${this.program.get(n)}\n`)
    }
  }

  listing(): string {
    return [...this.program.keys()].sort((a, b) => a - b).map(n => `${n} ${this.program.get(n)}`).join('\n')
  }

  private diskFind(name: string): string | undefined {
    const key = name.toUpperCase()
    if (key === '*' || key === '') return [...this.disk.values()][0]
    if (this.disk.has(key)) return this.disk.get(key)
    if (key.endsWith('*')) {
      const pre = key.slice(0, -1)
      for (const [k, v] of this.disk) if (k.startsWith(pre)) return v
    }
    return undefined
  }

  /** The directory as LOAD "$",8 would list it. */
  directory(): string[] {
    const out = ['0 "RETRO DECK      " RD 2A']
    for (const [k, v] of this.disk) out.push(`${String(Math.max(1, Math.ceil(v.length / 254))).padEnd(4)} "${k.slice(0, 16)}"${' '.repeat(Math.max(1, 18 - k.slice(0, 16).length))}PRG`)
    out.push(`${Math.max(0, 664 - [...this.disk.values()].reduce((a, v) => a + Math.ceil(v.length / 254), 0))} BLOCKS FREE.`)
    return out
  }

  // ---- variables ----------------------------------------------------------

  private isStringTarget(target: Tok[]): boolean { return (target[0] as { v: string }).v.endsWith('$') }

  getVar(name: string): Value {
    if (name === 'TI') return this.ti()
    if (name === 'TI$') return this.tiString()
    if (name === 'ST') return 0
    const v = this.vars.get(name)
    if (v !== undefined) return v
    return name.endsWith('$') ? '' : 0
  }

  setVar(name: string, v: Value): void {
    if (name.endsWith('$') !== (typeof v === 'string')) throw ERR('TYPE MISMATCH')
    if (name === 'TI$') { this.setTi(v as string); return }
    if (name === 'TI' || name === 'ST') throw ERR('SYNTAX')
    if (name.endsWith('%')) v = Math.trunc(v as number)
    this.vars.set(name, v)
  }

  private assign(target: Tok[], v: Value): void {
    const name = (target[0] as { v: string }).v
    if (target.length === 1) { this.setVar(name, v); return }
    const idx = this.indexOf(name, target)
    const arr = this.arrays.get(name)!
    if (name.endsWith('$') !== (typeof v === 'string')) throw ERR('TYPE MISMATCH')
    arr.data[idx] = name.endsWith('%') ? Math.trunc(v as number) : v
  }

  /** Flat index for an array reference `name(i,j)` given as tokens; auto-DIMs to 10. */
  indexOf(name: string, target: Tok[]): number {
    const p = new Parser(target, this)
    p.i = 1
    p.op('(')
    const subs: number[] = []
    do { subs.push(Math.floor(p.num())) } while (p.peekOp(',') && ++p.i)
    p.op(')')
    let arr = this.arrays.get(name)
    if (!arr) {
      const dims = subs.map(() => 11)
      arr = { dims, data: new Array(dims.reduce((a, b) => a * b, 1)).fill(name.endsWith('$') ? '' : 0) }
      this.arrays.set(name, arr)
    }
    if (subs.length !== arr.dims.length) throw ERR('BAD SUBSCRIPT')
    let idx = 0
    for (let i = 0; i < subs.length; i++) {
      if (subs[i] < 0 || subs[i] >= arr.dims[i]) throw ERR('BAD SUBSCRIPT')
      idx = idx * arr.dims[i] + subs[i]
    }
    return idx
  }

  arrayGet(name: string, target: Tok[]): Value {
    const idx = this.indexOf(name, target)
    return this.arrays.get(name)!.data[idx]
  }

  callFn(name: string, arg: number): number {
    const fn = this.fns.get(name)
    if (!fn) throw ERR("UNDEF'D FUNCTION")
    const saved = this.vars.get(fn.param)
    this.vars.set(fn.param, arg)
    try {
      const p = new Parser(fn.body, this)
      const v = p.expr()
      if (typeof v !== 'number') throw ERR('TYPE MISMATCH')
      return v
    } finally {
      if (saved === undefined) this.vars.delete(fn.param); else this.vars.set(fn.param, saved)
    }
  }

  rnd(arg: number): number {
    if (arg === 0) return (this.jiffies() % 1000) / 1000
    if (arg < 0) { this.rndSeed = Math.abs(arg) % 1 || 0.5 }
    this.rndSeed = (this.rndSeed * 9821 + 0.211327) % 1
    return this.rndSeed
  }

  ti(): number { return this.jiffies() }
  tiString(): string {
    const secs = Math.floor(this.jiffies() / 60)
    const h = Math.floor(secs / 3600) % 24, m = Math.floor(secs / 60) % 60, s = secs % 60
    return [h, m, s].map(x => String(x).padStart(2, '0')).join('')
  }
  setTi(hhmmss: string): void {
    if (!/^\d{6}$/.test(hhmmss)) throw ERR('ILLEGAL QUANTITY')
    const h = Number(hhmmss.slice(0, 2)), m = Number(hhmmss.slice(2, 4)), s = Number(hhmmss.slice(4, 6))
    const target = (h * 3600 + m * 60 + s) * 60
    this.tiOffset = 0
    this.tiOffset = (target - this.jiffies() + 5184000) % 5184000
  }
  fre(): number { return 38911 - this.program.size * 20 - this.vars.size * 7 }
  pos(): number { return this.col }
}

const PETSCII_COLORS: Record<number, number> = {
  144: 0, 5: 1, 28: 2, 159: 3, 156: 4, 30: 5, 31: 6, 158: 7,
  129: 8, 149: 9, 150: 10, 151: 11, 152: 12, 153: 13, 154: 14, 155: 15,
}

function truthy(v: Value): boolean { return typeof v === 'number' ? v !== 0 : v !== '' }

// ---- tokenizer --------------------------------------------------------------

export function tokenize(src: string): Tok[] {
  const toks: Tok[] = []
  let i = 0
  const s = src
  while (i < s.length) {
    const ch = s[i]
    if (ch === ' ') { i++; continue }
    if (ch === '"') {
      let j = i + 1
      while (j < s.length && s[j] !== '"') j++
      toks.push({ t: 'str', v: s.slice(i + 1, j) })
      i = j + 1
      continue
    }
    if (ch === '?') { toks.push({ t: 'kw', v: 'PRINT' }); i++; continue }
    if (/[0-9.]/.test(ch)) {
      const m = /^(\d+\.?\d*|\.\d+)(E[+-]?\d+)?/i.exec(s.slice(i))
      if (m) { toks.push({ t: 'num', v: Number(m[0]) }); i += m[0].length; continue }
      toks.push({ t: 'op', v: ch }); i++
      continue
    }
    const upper = s.slice(i).toUpperCase()
    let matched = false
    for (const kw of KEYWORDS) {
      if (upper.startsWith(kw)) {
        toks.push({ t: 'kw', v: kw })
        i += kw.length
        matched = true
        if (kw === 'REM' || kw === 'DATA') { toks.push({ t: 'str', v: s.slice(i) }); return toks }
        break
      }
    }
    if (matched) continue
    if (/[A-Za-z]/.test(ch)) {
      // A variable: letters and digits until a keyword or something else begins; two chars count.
      let j = i
      let name = ''
      while (j < s.length && /[A-Za-z0-9]/.test(s[j])) {
        const rest = s.slice(j).toUpperCase()
        if (name.length > 0 && KEYWORDS.some(k => rest.startsWith(k))) break
        name += s[j].toUpperCase()
        j++
      }
      let suffix = ''
      if (s[j] === '$' || s[j] === '%') { suffix = s[j]; j++ }
      const short = (name[0] ?? '') + (name[1] ?? '')
      toks.push({ t: 'var', v: short + suffix })
      i = j
      continue
    }
    const two = s.slice(i, i + 2)
    if (two === '<=' || two === '>=' || two === '<>' || two === '=<' || two === '=>' || two === '><') {
      toks.push({ t: 'op', v: two === '=<' ? '<=' : two === '=>' ? '>=' : two === '><' ? '<>' : two })
      i += 2
      continue
    }
    if ('+-*/^=<>(),;:#'.includes(ch)) { toks.push({ t: 'op', v: ch }); i++; continue }
    if (ch === '\t') { i++; continue }
    toks.push({ t: 'op', v: ch })
    i++
  }
  return toks
}

function splitStatements(toks: Tok[]): Tok[][] {
  const out: Tok[][] = []
  let cur: Tok[] = []
  for (const t of toks) {
    if (t.t === 'op' && t.v === ':') { out.push(cur); cur = []; continue }
    cur.push(t)
  }
  out.push(cur)
  return out.filter((s, i, a) => s.length > 0 || i === a.length - 1)
}

function rawAfterKeyword(src: string, kw: string): string {
  const i = src.toUpperCase().indexOf(kw)
  return i < 0 ? '' : src.slice(i + kw.length)
}

function splitData(raw: string): string[] {
  const items: string[] = []
  let cur = ''
  let inQ = false
  for (const ch of raw) {
    if (ch === '"') { inQ = !inQ; continue }
    if (ch === ',' && !inQ) { items.push(cur.trim()); cur = ''; continue }
    if (ch === ':' && !inQ) break
    cur += ch
  }
  items.push(cur.trim())
  return items
}

// ---- expressions ------------------------------------------------------------

class Parser {
  i = 0
  constructor(private toks: Tok[], private m: C64) {}

  peek(): Tok | undefined { return this.toks[this.i] }
  next(): Tok { const t = this.toks[this.i++]; if (!t) throw ERR('SYNTAX'); return t }
  peekKw(v: string): boolean { const t = this.peek(); return t?.t === 'kw' && t.v === v }
  peekOp(v: string): boolean { const t = this.peek(); return t?.t === 'op' && t.v === v }
  kw(v: string): void { if (!this.peekKw(v)) throw ERR('SYNTAX'); this.i++ }
  op(v: string): void { if (!this.peekOp(v)) throw ERR('SYNTAX'); this.i++ }

  varName(): string { const t = this.next(); if (t.t !== 'var') throw ERR('SYNTAX'); return t.v }
  lineNumber(): number { const t = this.next(); if (t.t !== 'num') throw ERR('SYNTAX'); return Math.floor(t.v) }
  num(): number { const v = this.expr(); if (typeof v !== 'number') throw ERR('TYPE MISMATCH'); return v }
  str(): string { const v = this.expr(); if (typeof v !== 'string') throw ERR('TYPE MISMATCH'); return v }

  /** A variable or array element reference, as tokens, for assignment. */
  target(): Tok[] {
    const start = this.i
    const t = this.next()
    if (t.t !== 'var') throw ERR('SYNTAX')
    if (this.peekOp('(')) {
      let depth = 0
      do {
        const x = this.next()
        if (x.t === 'op' && x.v === '(') depth++
        if (x.t === 'op' && x.v === ')') depth--
      } while (depth > 0)
    }
    return this.toks.slice(start, this.i)
  }

  expr(): Value { return this.orExpr() }

  private orExpr(): Value {
    let v = this.andExpr()
    while (this.peekKw('OR')) { this.i++; const r = this.andExpr(); v = (toInt(v) | toInt(r)) }
    return v
  }
  private andExpr(): Value {
    let v = this.notExpr()
    while (this.peekKw('AND')) { this.i++; const r = this.notExpr(); v = (toInt(v) & toInt(r)) }
    return v
  }
  private notExpr(): Value {
    if (this.peekKw('NOT')) { this.i++; return ~toInt(this.notExpr()) }
    return this.cmpExpr()
  }
  private cmpExpr(): Value {
    const l = this.addExpr()
    const t = this.peek()
    if (t?.t === 'op' && ['=', '<', '>', '<=', '>=', '<>'].includes(t.v)) {
      this.i++
      const r = this.addExpr()
      if (typeof l !== typeof r) throw ERR('TYPE MISMATCH')
      const res = t.v === '=' ? l === r : t.v === '<' ? l < r : t.v === '>' ? l > r : t.v === '<=' ? l <= r : t.v === '>=' ? l >= r : l !== r
      return res ? -1 : 0
    }
    return l
  }
  private addExpr(): Value {
    let v = this.mulExpr()
    for (;;) {
      if (this.peekOp('+')) { this.i++; const r = this.mulExpr(); if (typeof v !== typeof r) throw ERR('TYPE MISMATCH'); v = typeof v === 'string' ? v + (r as string) : v + (r as number); if (typeof v === 'string' && v.length > 255) throw ERR('STRING TOO LONG') }
      else if (this.peekOp('-')) { this.i++; const r = this.mulExpr(); if (typeof v !== 'number' || typeof r !== 'number') throw ERR('TYPE MISMATCH'); v = v - r }
      else return v
    }
  }
  private mulExpr(): Value {
    let v = this.unary()
    for (;;) {
      if (this.peekOp('*')) { this.i++; const r = this.unary(); v = numOf(v) * numOf(r) }
      else if (this.peekOp('/')) { this.i++; const r = numOf(this.unary()); if (r === 0) throw ERR('DIVISION BY ZERO'); v = numOf(v) / r }
      else return v
    }
  }
  private unary(): Value {
    if (this.peekOp('-')) { this.i++; return -numOf(this.unary()) }
    if (this.peekOp('+')) { this.i++; return numOf(this.unary()) }
    return this.power()
  }
  private power(): Value {
    const base = this.primary()
    if (this.peekOp('^')) { this.i++; const e = this.unary(); return Math.pow(numOf(base), numOf(e)) }
    return base
  }
  private primary(): Value {
    const t = this.next()
    if (t.t === 'num') return t.v
    if (t.t === 'str') return t.v
    if (t.t === 'op' && t.v === '(') { const v = this.expr(); this.op(')'); return v }
    if (t.t === 'var') {
      if (this.peekOp('(')) {
        const start = this.i - 1
        let depth = 0
        do { const x = this.next(); if (x.t === 'op' && x.v === '(') depth++; if (x.t === 'op' && x.v === ')') depth-- } while (depth > 0)
        return this.m.arrayGet(t.v, this.toks.slice(start, this.i))
      }
      return this.m.getVar(t.v)
    }
    if (t.t === 'kw') return this.func(t.v)
    throw ERR('SYNTAX')
  }
  private arg(): Value { this.op('('); const v = this.expr(); this.op(')'); return v }
  private func(name: string): Value {
    const m = this.m
    switch (name) {
      case 'FRE': this.arg(); return m.fre()
      case 'POS': this.arg(); return m.pos()
      case 'RND': return m.rnd(numOf(this.arg()))
      case 'PEEK': return m.peek(numOf(this.arg()))
      case 'ABS': return Math.abs(numOf(this.arg()))
      case 'SGN': return Math.sign(numOf(this.arg()))
      case 'INT': return Math.floor(numOf(this.arg()))
      case 'SQR': { const v = numOf(this.arg()); if (v < 0) throw ERR('ILLEGAL QUANTITY'); return Math.sqrt(v) }
      case 'LOG': { const v = numOf(this.arg()); if (v <= 0) throw ERR('ILLEGAL QUANTITY'); return Math.log(v) }
      case 'EXP': return Math.exp(numOf(this.arg()))
      case 'SIN': return Math.sin(numOf(this.arg()))
      case 'COS': return Math.cos(numOf(this.arg()))
      case 'TAN': return Math.tan(numOf(this.arg()))
      case 'ATN': return Math.atan(numOf(this.arg()))
      case 'USR': this.arg(); return 0
      case 'LEN': return strOf(this.arg()).length
      case 'ASC': { const s = strOf(this.arg()); if (!s.length) throw ERR('ILLEGAL QUANTITY'); return s.toUpperCase().charCodeAt(0) }
      case 'VAL': { const s = strOf(this.arg()).trim(); const n = parseFloat(s); return Number.isNaN(n) ? 0 : n }
      case 'STR$': return fmtNum(numOf(this.arg()))
      case 'CHR$': { const n = numOf(this.arg()); if (n < 0 || n > 255) throw ERR('ILLEGAL QUANTITY'); return String.fromCharCode(Math.floor(n)) }
      case 'LEFT$': { this.op('('); const s = this.str(); this.op(','); const n = Math.floor(this.num()); this.op(')'); if (n < 0 || n > 255) throw ERR('ILLEGAL QUANTITY'); return s.slice(0, n) }
      case 'RIGHT$': { this.op('('); const s = this.str(); this.op(','); const n = Math.floor(this.num()); this.op(')'); if (n < 0 || n > 255) throw ERR('ILLEGAL QUANTITY'); return n === 0 ? '' : s.slice(-n) }
      case 'MID$': {
        this.op('('); const s = this.str(); this.op(','); const start = Math.floor(this.num())
        let len = 255
        if (this.peekOp(',')) { this.i++; len = Math.floor(this.num()) }
        this.op(')')
        if (start < 1 || len < 0) throw ERR('ILLEGAL QUANTITY')
        return s.slice(start - 1, start - 1 + len)
      }
      case 'FN': { const fnName = this.varName(); const a = numOf(this.arg()); return m.callFn(fnName, a) }
      default: throw ERR('SYNTAX')
    }
  }
}

function numOf(v: Value): number { if (typeof v !== 'number') throw ERR('TYPE MISMATCH'); return v }
function strOf(v: Value): string { if (typeof v !== 'string') throw ERR('TYPE MISMATCH'); return v }
function toInt(v: Value): number {
  const n = numOf(v)
  if (n < -32768 || n > 32767) throw ERR('ILLEGAL QUANTITY')
  return Math.trunc(n)
}
