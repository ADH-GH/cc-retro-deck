// /deck setup and /deck uninstall: everything the plugin needs outside its own folder, set up
// and taken back. Each shows what it would do first and acts only with `apply`.
//
// The plugin folder changes with every version (the install is a copy under the plugin
// cache), so the shell line cannot point there: the shell files are copied to
// ~/.claude/retro-deck/shell/ and kept current on every session start (refreshShell).
//
// macOS edition. The Linux edition has its own copy of this file (ADR 0003).
import type { EngineInterface } from 'claude-code'

const EDITION = {
  rc: '.zshrc',
  loader: 'load.zsh',
  line: '[[ -r ~/.claude/retro-deck/shell/load.zsh ]] && source ~/.claude/retro-deck/shell/load.zsh',
  files: ['load.zsh', 'frame.sh', 'boot.py', 'trek.py', 'nyc.py', 'magenta.py', 'berlin.py', 'sf.py', 'cologne.py', 'ultipa.py', 'hoiv.py', 'c64.tmux.conf'],
  tmuxHint: 'brew install tmux',
  plugin: 'cc-retro-deck-mac@cc-retro-deck',
}
const BEGIN = '# >>> cc-retro-deck >>>'
const END = '# <<< cc-retro-deck <<<'
const PROFILES = ['C64', 'C64 Rahmen']
const PATHS = 'PATH=/opt/homebrew/bin:/usr/local/bin:$PATH'

// Terminal.app: which of our profiles exist, and which is the default for new windows.
const PROFILES_STATE = `
tell application "Terminal"
  set out to {}
  repeat with nm in {"C64", "C64 Rahmen"}
    if exists settings set (nm as text) then set end of out to (nm as text)
  end repeat
  set AppleScript's text item delimiters to "|"
  return (out as text)
end tell`

// Import a .terminal file: `open` does it, and opens a window with it; that window is closed
// again (the ids before and after tell which one it was).
const PROFILE_IMPORT = `
on run argv
  tell application "Terminal"
    set before to id of every window
    do shell script "open " & quoted form of (item 1 of argv)
    delay 1.5
    repeat with w in windows
      if before does not contain (id of w) then close w saving no
    end repeat
  end tell
end run`

// Delete our profiles. Tabs wearing one go back to Basic (window kept as it is), and so does
// the default or startup profile if it was ours.
const PROFILE_DELETE = `
tell application "Terminal"
  set gone to {}
  repeat with nm in {"C64", "C64 Rahmen"}
    set nm to nm as text
    if exists settings set nm then
      if name of default settings is nm then set default settings to settings set "Basic"
      if name of startup settings is nm then set startup settings to settings set "Basic"
      repeat with w in windows
        repeat with t in tabs of w
          if name of current settings of t is nm then
            set b to bounds of w
            set current settings of t to settings set "Basic"
            set bounds of w to b
          end if
        end repeat
      end repeat
      delete settings set nm
      set end of gone to nm
    end if
  end repeat
  set AppleScript's text item delimiters to ", "
  return (gone as text)
end tell`

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

async function profilesPresent($: EngineInterface): Promise<string[] | null> {
  if (await $.env.get('CC_RETRO_DECK_NO_TERMINAL')) return null      // tests: leave Terminal.app alone
  const ran = await $.process.run(['osascript', '-e', PROFILES_STATE], { timeoutMs: 8000 }).catch(() => null)
  if (!ran || ran.exitCode !== 0) return null
  return ran.stdout.trim().split('|').filter(Boolean)
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
  const profiles = await profilesPresent($)
  const tmux = await sh($, `${PATHS}; command -v tmux`)
  // `python3 -c 1`, not `command -v`: macOS has a /usr/bin/python3 stub without the Command Line Tools.
  const python = await sh($, `${PATHS}; python3 -c 1 >/dev/null 2>&1 && command -v python3`)

  const plan: string[] = []
  plan.push(`${stamp?.trim() === version ? '✓' : '→'} shell scripts in ~/.claude/retro-deck/shell/ (version ${version || '?'})`)
  plan.push(`${rc.hasBlock ? '✓' : '→'} block in ${rcPath} between "${BEGIN}" and "${END}", defines LOAD and RUN`)
  if (profiles === null) plan.push('· Terminal profiles: Terminal.app not reachable, skipped')
  else for (const p of PROFILES) plan.push(`${profiles.includes(p) ? '✓' : '→'} Terminal profile "${p}"`)
  plan.push(tmux.ok ? `✓ tmux found (${tmux.out})` : `! tmux missing: ${EDITION.tmuxHint} — without it LOAD starts claude without the frame`)
  if (!python.ok) plan.push('! python3 missing: xcode-select --install — without it LOAD shows three lines instead of the boot screen')
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
  if (profiles !== null) {
    for (const p of PROFILES) {
      if (profiles.includes(p)) continue
      const ran = await $.process
        .run(['osascript', '-e', PROFILE_IMPORT, '--', `${$.plugin.root}/terminal/${p}.terminal`], { timeoutMs: 15000 })
        .catch(() => null)
      done.push(ran && ran.exitCode === 0 ? `✓ Terminal profile "${p}" imported` : `! Terminal profile "${p}" not imported`)
    }
  }
  if (!tmux.ok) done.push(`! tmux still missing: ${EDITION.tmuxHint}`)
  return ['Retro Deck set up:', ...done, '', 'Open a new terminal tab and type  LOAD "*",8,1', 'Sessions started by LOAD draw in C64 colors (theme dark-ansi for that session only); a plain `claude` keeps your theme.'].join('\n')
}

/** Frame servers other than the one this session runs in. */
async function otherFrames($: EngineInterface, ownSock: string): Promise<string[]> {
  const ran = await sh($, `${PATHS}; for s in "\${TMUX_TMPDIR:-/private/tmp}/tmux-$(id -u)"/c64-*; do tmux -S "$s" has-session 2>/dev/null </dev/null && echo "\${s##*/}"; done; true`)
  return ran.out.split('\n').filter(s => s !== '' && s !== ownSock)
}

export async function uninstallCommand($: EngineInterface, home: string, apply: boolean, ownSock: string): Promise<string> {
  const rcPath = `~/${EDITION.rc}`
  const rc = splitRc(await readRc($, home))
  const frames = await otherFrames($, ownSock)
  const profiles = await profilesPresent($)
  const data = await sh($, 'test -d "$1"', [`${home}/.claude/retro-deck`])

  const plan: string[] = []
  plan.push(frames.length > 0
    ? `→ end ${frames.length} running Retro Deck frame(s) — Claude sessions inside them stop; conversations stay available via claude --resume`
    : '✓ no other Retro Deck frame running')
  plan.push(rc.hasBlock ? `→ remove the block from ${rcPath}` : `✓ no block in ${rcPath}`)
  if (profiles === null) plan.push('· Terminal profiles: Terminal.app not reachable, skipped')
  else plan.push(profiles.length > 0 ? `→ delete Terminal profile(s) ${profiles.map(p => `"${p}"`).join(', ')} (tabs wearing them go back to Basic)` : '✓ no Terminal profiles left')
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
  for (const s of frames) await sh($, `${PATHS}; tmux -L "$1" kill-server`, [s], 5000)
  if (frames.length > 0) done.push(`✓ ${frames.length} frame(s) ended`)
  if (rc.hasBlock) {
    const wrote = await $.fs.write(`${home}/${EDITION.rc}`, rc.rest === '' ? '' : `${rc.rest}\n`).then(() => true).catch(() => false)
    done.push(wrote ? `✓ block removed from ${rcPath}` : `! could not write ${rcPath}`)
  }
  if (profiles !== null && profiles.length > 0) {
    const ran = await $.process.run(['osascript', '-e', PROFILE_DELETE], { timeoutMs: 15000 }).catch(() => null)
    done.push(ran && ran.exitCode === 0 ? `✓ Terminal profiles deleted: ${ran.stdout.trim()}` : '! Terminal profiles not deleted (Terminal → Settings → Profiles)')
  }
  if (data.ok) {
    await sh($, 'rm -rf "$1"', [`${home}/.claude/retro-deck`])
    done.push('✓ ~/.claude/retro-deck/ deleted')
  }
  if (ownSock !== '') done.push('· this tab runs in a Retro Deck frame: /exit and close it when you are done')
  done.push('· other Claude sessions with the plugin still loaded may write a few cache files until they end')
  return ['Retro Deck uninstalled outside the plugin:', ...done, '', ...last].join('\n')
}
