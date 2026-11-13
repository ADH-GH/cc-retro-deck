// /deck setup and /deck uninstall: everything the plugin needs outside its own folder, set up
// and taken back. Each shows what it would do first and acts only with `apply`.
//
// The plugin folder changes with every version (the install is a copy under the plugin
// cache), so the shell line cannot point there: the shell files are copied to
// ~/.claude/retro-deck/shell/ and kept current on every session start (refreshShell).
//
// Linux edition (bash, GNOME Terminal: colors come per escape sequence, no Terminal profiles).
// The macOS edition has its own copy of this file (ADR 0003).
import type { EngineInterface } from 'claude-code'

const EDITION = {
  rc: '.bashrc',
  loader: 'load.bash',
  line: '[ -r ~/.claude/retro-deck/shell/load.bash ] && . ~/.claude/retro-deck/shell/load.bash',
  files: ['load.bash', 'frame.sh', 'fix.sh', 'boot.py', 'trek.py', 'nyc.py', 'magenta.py', 'berlin.py', 'sf.py', 'cologne.py', 'ultipa.py', 'c64.tmux.conf'],
  tmuxHint: 'sudo apt install tmux',
  plugin: 'cc-retro-deck-linux@cc-retro-deck',
}
const BEGIN = '# >>> cc-retro-deck >>>'
const END = '# <<< cc-retro-deck <<<'
const PATHS = 'PATH=/usr/local/bin:$PATH'

function shellDir(home: string): string { return `${home}/.claude/retro-deck/shell` }

async function sh($: EngineInterface, script: string, args: string[] = [], timeoutMs = 15000): Promise<{ ok: boolean; out: string }> {
  const ran = await $.process.run(['sh', '-c', script, 'sh', ...args], { timeoutMs }).catch(() => null)
  return { ok: ran !== null && ran.exitCode === 0, out: (ran?.stdout ?? '').trim() }
}

async function pluginVersion($: EngineInterface): Promise<string> {
  try {
    return (JSON.parse(await $.fs.read(`${$.plugin.root}/.claude-plugin/plugin.json`)) as { version?: string }).version ?? ''
  } catch { return '' }
}

/** The rc file without our block, and the lines outside it that load an older copy. */
function splitRc(text: string): { rest: string; hasBlock: boolean; strays: number[] } {
  const lines = text.split('\n')
  const out: string[] = []
  const strays: number[] = []
  let inside = false
  let hasBlock = false
  lines.forEach((line, i) => {
    if (line.trim() === BEGIN) { inside = true; hasBlock = true; return }
    if (line.trim() === END) { inside = false; return }
    if (inside) return
    if (line.includes(EDITION.loader) && !line.trim().startsWith('#')) strays.push(i + 1)
    out.push(line)
  })
  return { rest: out.join('\n').replace(/\n+$/, ''), hasBlock, strays }
}

async function readRc($: EngineInterface, home: string): Promise<string> {
  return $.fs.read(`${home}/${EDITION.rc}`).catch(() => '')
}

/** Copy the shell files when setup has been done and the plugin brought another version. */
export async function refreshShell($: EngineInterface, home: string): Promise<void> {
  const dir = shellDir(home)
  const stamp = await $.fs.read(`${dir}/.version`).catch(() => null)
  if (stamp === null) return                  // never set up (or uninstalled): stay out
  const version = await pluginVersion($)
  if (version === '' || stamp.trim() === version) return
  await copyShell($, home, version)
}

async function copyShell($: EngineInterface, home: string, version: string): Promise<boolean> {
  const src = `${$.plugin.root}/shell`
  const dir = shellDir(home)
  const files = EDITION.files.map(f => `"$2/${f}"`).join(' ')
  const ran = await sh($, `mkdir -p "$1" && for f in ${files}; do [ -e "$f" ] && cp "$f" "$1/"; done; chmod +x "$1"/*.sh && printf %s "$3" > "$1/.version"`, [dir, src, version])
  return ran.ok
}

export async function setupCommand($: EngineInterface, home: string, apply: boolean): Promise<string> {
  const version = await pluginVersion($)
  const rcPath = `~/${EDITION.rc}`
  const rc = splitRc(await readRc($, home))
  const stamp = await $.fs.read(`${shellDir(home)}/.version`).catch(() => null)
  const tmux = await sh($, `${PATHS}; command -v tmux`)
  // `python3 -c 1`, not `command -v`: macOS has a /usr/bin/python3 stub without the Command Line Tools.
  const python = await sh($, `${PATHS}; python3 -c 1 >/dev/null 2>&1 && command -v python3`)

  const plan: string[] = []
  plan.push(`${stamp?.trim() === version ? '✓' : '→'} shell scripts in ~/.claude/retro-deck/shell/ (version ${version || '?'})`)
  plan.push(`${rc.hasBlock ? '✓' : '→'} block in ${rcPath} between "${BEGIN}" and "${END}", defines LOAD and RUN`)
  plan.push(tmux.ok ? `✓ tmux found (${tmux.out})` : `! tmux missing: ${EDITION.tmuxHint} — without it LOAD starts claude without the frame`)
  if (!python.ok) plan.push('! python3 missing: sudo apt install python3 — without it LOAD shows three lines instead of the boot screen')
  if (rc.strays.length > 0) plan.push(`! ${rcPath} line ${rc.strays.join(', ')} loads another copy of ${EDITION.loader}; remove it by hand so only the block counts`)

  if (!apply) {
    return ['Retro Deck setup — nothing changed yet:', ...plan, '', 'Run /deck setup apply to do the → steps.'].join('\n')
  }

  const done: string[] = []
  if (!(await copyShell($, home, version))) return `Setup stopped: could not copy the shell scripts to ${shellDir(home)}.`
  done.push('✓ shell scripts copied')
  const block = [BEGIN, '# Claude Code Retro Deck: LOAD "*",8,1 — remove with /deck uninstall', EDITION.line, END].join('\n')
  const next = (rc.rest === '' ? '' : `${rc.rest}\n\n`) + `${block}\n`
  const wrote = await $.fs.write(`${home}/${EDITION.rc}`, next).then(() => true).catch(() => false)
  done.push(wrote ? `✓ block in ${rcPath}` : `! could not write ${rcPath}`)
  if (!tmux.ok) done.push(`! tmux still missing: ${EDITION.tmuxHint}`)
  return ['Retro Deck set up:', ...done, '', 'Open a new terminal tab and type  LOAD "*",8,1', 'Sessions started by LOAD draw in C64 colors (theme dark-ansi for that session only); a plain `claude` keeps your theme.'].join('\n')
}

/** Whether the shared C64 server runs. */
async function frameRuns($: EngineInterface): Promise<boolean> {
  return (await sh($, `${PATHS}; tmux -L c64 has-session 2>/dev/null </dev/null`)).ok
}

export async function uninstallCommand($: EngineInterface, home: string, apply: boolean, ownSock: string): Promise<string> {
  const rcPath = `~/${EDITION.rc}`
  const rc = splitRc(await readRc($, home))
  const runs = await frameRuns($)
  const inFrame = ownSock !== ''
  const data = await sh($, 'test -d "$1"', [`${home}/.claude/retro-deck`])

  const plan: string[] = []
  plan.push(!runs ? '✓ no Retro Deck frame running'
    : inFrame ? '· the Retro Deck frame runs, this session inside it: /exit and close the terminal afterwards, that ends it'
    : '→ end the Retro Deck frame — Claude sessions in its windows stop; conversations stay available via claude --resume')
  plan.push(rc.hasBlock ? `→ remove the block from ${rcPath}` : `✓ no block in ${rcPath}`)
  plan.push(data.ok ? '→ delete ~/.claude/retro-deck/ (shell copies, deck cache, restore list)' : '✓ ~/.claude/retro-deck/ is gone')
  if (rc.strays.length > 0) plan.push(`! ${rcPath} line ${rc.strays.join(', ')} loads ${EDITION.loader} outside the block; remove it by hand`)

  const last = [
    'Then, in a shell:',
    `  claude plugin uninstall ${EDITION.plugin}`,
    '  claude plugin marketplace remove cc-retro-deck',
  ]
  if (!apply) {
    return ['Retro Deck uninstall — nothing removed yet:', ...plan, '', 'Run /deck uninstall apply to do the → steps.', ...last].join('\n')
  }

  const done: string[] = []
  if (runs && !inFrame) {
    await sh($, `${PATHS}; tmux -L c64 kill-server`, [], 5000)
    done.push('✓ frame ended')
  }
  if (rc.hasBlock) {
    const wrote = await $.fs.write(`${home}/${EDITION.rc}`, rc.rest === '' ? '' : `${rc.rest}\n`).then(() => true).catch(() => false)
    done.push(wrote ? `✓ block removed from ${rcPath}` : `! could not write ${rcPath}`)
  }
  if (data.ok) {
    await sh($, 'rm -rf "$1"', [`${home}/.claude/retro-deck`])
    done.push('✓ ~/.claude/retro-deck/ deleted')
  }
  if (inFrame) done.push('· this session runs in the Retro Deck frame: /exit and close the terminal, that ends the frame')
  done.push('· other Claude sessions with the plugin still loaded may write a few cache files until they end')
  return ['Retro Deck uninstalled outside the plugin:', ...done, '', ...last].join('\n')
}
