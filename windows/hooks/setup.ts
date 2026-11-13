// /deck setup and /deck uninstall: everything the plugin needs outside its own folder, set up
// and taken back. Each shows what it would do first and acts only with `apply`.
//
// The plugin folder changes with every version (the install is a copy under the plugin
// cache), so the profile line cannot point there: the shell files are copied to
// ~/.claude/retro-deck/shell/ and kept current on every session start (refreshShell).
//
// Windows edition. The macOS and Linux editions have their own copy of this file (ADR 0003).
// Outside the plugin it touches: the PowerShell profiles (Windows PowerShell 5.1 and, when
// installed, PowerShell 7), LOAD.cmd and SYS.cmd in ~/.local/bin (where Claude Code's installer
// puts claude.exe, so it is on the PATH) for cmd and for a PowerShell whose policy runs no
// profile, a Windows Terminal fragment with the "C64 Retro Deck" profile, and
// ~/.claude/retro-deck/. settings.json of Windows Terminal stays as it is. The execution policy
// changes only with `/deck setup apply policy`, never on its own.
import type { EngineInterface } from 'claude-code'

import { exe, ps, slashes, win } from './win'

const EDITION = {
  loader: 'load.ps1',
  files: ['load.ps1', 'boot.py', 'trek.py', 'nyc.py', 'magenta.py', 'berlin.py', 'sf.py', 'cologne.py', 'ultipa.py', 'hoiv.py', 'head.py', 'c64-settings.json', 'LOAD.cmd', 'SYS.cmd'],
  plugin: 'cc-retro-deck-windows@cc-retro-deck',
}
const BEGIN = '# >>> cc-retro-deck >>>'
const END = '# <<< cc-retro-deck <<<'
const BLOCK = [
  BEGIN,
  '# Claude Code Retro Deck: LOAD "*",8,1 - remove with /deck uninstall',
  "$c64Load = Join-Path $HOME '.claude\\retro-deck\\shell\\load.ps1'; if (Test-Path $c64Load) { . $c64Load }",
  END,
]
const SHELLS = [
  { exe: 'powershell.exe', name: 'Windows PowerShell' },
  { exe: 'pwsh.exe', name: 'PowerShell 7' },
]
const OPEN_POLICY = 'Set-ExecutionPolicy -Scope CurrentUser RemoteSigned'
const CMD_FILES = ['LOAD.cmd', 'SYS.cmd']
const CMD_MARK = 'cc-retro-deck-windows'       // the line in LOAD.cmd and SYS.cmd that says they are ours

function shellDir(home: string): string { return `${home}/.claude/retro-deck/shell` }
function fragmentDir(localAppData: string): string { return `${localAppData}/Microsoft/Windows Terminal/Fragments/cc-retro-deck` }

async function pluginVersion($: EngineInterface): Promise<string> {
  try {
    return (JSON.parse(await $.fs.read(`${$.plugin.root}/.claude-plugin/plugin.json`)) as { version?: string }).version ?? ''
  } catch { return '' }
}

/** The profile without our block, the lines outside it that load an older copy, and its line ending. */
function splitRc(text: string): { rest: string; hasBlock: boolean; strays: number[]; eol: string } {
  const eol = text.includes('\r\n') ? '\r\n' : '\n'
  const out: string[] = []
  const strays: number[] = []
  let inside = false
  let hasBlock = false
  text.split(/\r?\n/).forEach((line, i) => {
    if (line.trim() === BEGIN) { inside = true; hasBlock = true; return }
    if (line.trim() === END) { inside = false; return }
    if (inside) return
    if (line.includes(EDITION.loader) && !line.trim().startsWith('#')) strays.push(i + 1)
    out.push(line)
  })
  return { rest: out.join(eol).replace(/(\r?\n)+$/, ''), hasBlock, strays, eol }
}

type Profile = {
  name: string; exe: string; path: string; text: string; exists: boolean; isReadable: boolean
  /** The policy this PowerShell runs a profile under; Restricted and AllSigned run none of ours. */
  policy: string; isBlocked: boolean
}

/**
 * The policy a new tab of that PowerShell runs its profile under. Not Get-ExecutionPolicy: in a
 * session started by LOAD.cmd the Process scope says Bypass (PSExecutionPolicyPreference is
 * inherited), and so would every child (beta.2 read Bypass on a Restricted machine). The scopes
 * in order of precedence without Process; none set means Windows' own default per edition.
 */
const EFFECTIVE_POLICY = "$p = Get-ExecutionPolicy -List | Where-Object { $_.Scope -ne 'Process' -and \"$($_.ExecutionPolicy)\" -ne 'Undefined' } | Select-Object -First 1; " +
  "if ($p) { \"$($p.ExecutionPolicy)\" } elseif ($PSVersionTable.PSEdition -eq 'Core') { 'RemoteSigned' } else { 'Restricted' }"

/**
 * Each installed PowerShell's own profile file, as that PowerShell names it (Documents may be on
 * OneDrive), and its effective execution policy (EFFECTIVE_POLICY).
 */
async function profiles($: EngineInterface): Promise<Profile[]> {
  const out: Profile[] = []
  for (const sh of SHELLS) {
    const ran = await exe($, [sh.exe, '-NoProfile', '-NonInteractive', '-Command', `$PROFILE.CurrentUserCurrentHost; ${EFFECTIVE_POLICY}`], 20000)
    if (!ran.ok || ran.out === '') continue                 // pwsh.exe not installed
    const [first, second] = ran.out.split('\n').map(l => l.trim())
    const path = slashes(first ?? '')
    if (path === '') continue
    const policy = second ?? ''
    const text = await $.fs.read(path).catch(() => null)
    // A profile saved as ANSI (umlauts in cp1252) reads back with U+FFFD; writing it would break them.
    out.push({
      name: sh.name, exe: sh.exe, path, text: text ?? '', exists: text !== null,
      isReadable: text === null || !text.includes('�'),
      policy, isBlocked: /^(Restricted|AllSigned)$/i.test(policy),
    })
  }
  return out
}

/** What to do with one profile: write the block, or skip it (not UTF-8, or a file its policy would refuse). */
function profileAction(p: Profile): 'write' | 'skip-blocked' | 'skip-ansi' {
  if (!p.isReadable) return 'skip-ansi'
  // A profile under a policy that runs none greets every new tab with a red error. So none is
  // made, and one holding nothing but our block (beta.1 made those) goes again.
  if (p.isBlocked && splitRc(p.text).rest.trim() === '') return 'skip-blocked'
  return 'write'
}

/** ~/.local/bin when it is on the PATH (Claude Code's own installer puts claude.exe there), else ''. */
async function cmdDir($: EngineInterface, home: string): Promise<string> {
  const dir = `${home}/.local/bin`
  const path = slashes((await $.env.get('PATH')) ?? '').toLowerCase().split(';').map(p => p.replace(/\/+$/, ''))
  return path.includes(dir.toLowerCase()) ? dir : ''
}

/** Which of LOAD.cmd and SYS.cmd in `bin` are ours; a file of the same name without the mark is someone else's. */
async function cmdState($: EngineInterface, bin: string): Promise<{ ours: string[]; foreign: string[] }> {
  const ours: string[] = []
  const foreign: string[] = []
  if (bin === '') return { ours, foreign }
  for (const f of CMD_FILES) {
    const text = await $.fs.read(`${bin}/${f}`).catch(() => null)
    if (text === null) continue
    ;(text.includes(CMD_MARK) ? ours : foreign).push(f)
  }
  return { ours, foreign }
}

async function python($: EngineInterface): Promise<string> {
  for (const argv of [['py', '-3'], ['python'], ['python3']]) {
    const ran = await exe($, [...argv, '-c', 'import sys; print(sys.version.split()[0])'], 10000)
    if (ran.ok && /^\d/.test(ran.out)) return `${argv.join(' ')} ${ran.out}`
  }
  return ''
}

/** Copy the shell files when setup has been done and the plugin brought another version. */
export async function refreshShell($: EngineInterface, home: string): Promise<void> {
  const stamp = await $.fs.read(`${shellDir(home)}/.version`).catch(() => null)
  if (stamp === null) return                  // never set up (or uninstalled): stay out
  const version = await pluginVersion($)
  if (version === '' || stamp.trim() === version) return
  await copyShell($, home, version)
  // Our LOAD.cmd and SYS.cmd on PATH are copies too; renew them, never a foreign file of that name.
  const bin = await cmdDir($, home)
  for (const f of (await cmdState($, bin)).ours) {
    const text = await $.fs.read(`${$.plugin.root}/shell/${f}`).catch(() => '')
    if (text !== '') await $.fs.write(`${bin}/${f}`, text).catch(() => undefined)
  }
  // The fragment carries the profiles the frame panes open with; renew it only where setup put one.
  const localAppData = slashes((await $.env.get('LOCALAPPDATA')) ?? '')
  const fragment = localAppData === '' ? null : `${fragmentDir(localAppData)}/c64.json`
  if (fragment === null || !(await $.fs.exists(fragment).catch(() => false))) return
  const text = await $.fs.read(`${$.plugin.root}/terminal/c64-fragment.json`).catch(() => '')
  if (text !== '') await $.fs.write(fragment, text).catch(() => undefined)
}

async function copyShell($: EngineInterface, home: string, version: string): Promise<boolean> {
  const dir = shellDir(home)
  try {
    for (const f of EDITION.files) await $.fs.write(`${dir}/${f}`, await $.fs.read(`${$.plugin.root}/shell/${f}`))
    await $.fs.write(`${dir}/.version`, version)
    return true
  } catch { return false }
}

export async function setupCommand($: EngineInterface, home: string, apply: boolean, openPolicy = false): Promise<string> {
  const version = await pluginVersion($)
  const localAppData = slashes((await $.env.get('LOCALAPPDATA')) ?? '')
  const stamp = await $.fs.read(`${shellDir(home)}/.version`).catch(() => null)
  let found = await profiles($)
  const bin = await cmdDir($, home)
  const cmds = await cmdState($, bin)
  const py = await python($)
  const fragment = localAppData === '' ? null : `${fragmentDir(localAppData)}/c64.json`
  const hasFragment = fragment !== null && (await $.fs.exists(fragment).catch(() => false))

  const plan: string[] = []
  plan.push(`${stamp?.trim() === version ? '✓' : '→'} shell scripts in ~/.claude/retro-deck/shell/ (version ${version || '?'})`)
  if (found.length === 0) plan.push('! no PowerShell answered: LOAD cannot be set up')
  if (bin === '') plan.push('! ~/.local/bin is not on the PATH: no LOAD in cmd, and in Windows PowerShell only through its profile')
  else plan.push(`${cmds.ours.length === CMD_FILES.length ? '✓' : '→'} LOAD.cmd and SYS.cmd in ${bin} — LOAD "*",8,1 in cmd, and in any PowerShell, whatever its policy`)
  for (const f of cmds.foreign) plan.push(`! ${bin}/${f} exists and is not ours; left alone`)
  for (const p of found) {
    const rc = splitRc(p.text)
    const action = profileAction(p)
    if (action === 'skip-ansi') plan.push(`! ${p.name} profile ${p.path} is not UTF-8; left alone`)
    else if (action === 'skip-blocked') plan.push(p.exists
      ? `→ ${p.name}: remove ${p.path} — it holds only our block, and the policy "${p.policy}" refuses it (the red error in every new tab)`
      : `· ${p.name}: policy "${p.policy}" runs no profile, so none is created; LOAD.cmd serves this shell`)
    else plan.push(`${rc.hasBlock ? '✓' : '→'} block in the ${p.name} profile ${p.path}${p.isBlocked ? ` (inert under the policy "${p.policy}"; LOAD.cmd serves meanwhile)` : ''}`)
    if (rc.strays.length > 0) plan.push(`! ${p.path} line ${rc.strays.join(', ')} loads another copy of ${EDITION.loader}; remove it by hand`)
  }
  if (fragment === null) plan.push('· Windows Terminal profile: LOCALAPPDATA unknown, skipped')
  else plan.push(`${hasFragment ? '✓' : '→'} Windows Terminal profile "C64 Retro Deck" (fragment, settings.json untouched)`)
  const blocked = found.filter(p => p.isBlocked)
  if (blocked.length > 0) {
    plan.push(`· optional: /deck setup apply policy also runs  ${OPEN_POLICY}  for ${blocked.map(p => p.name).join(' and ')}: then the profile defines LOAD itself. Not needed for LOAD.`)
  }
  plan.push(py ? `✓ Python found (${py})` : '! Python missing: winget install Python.Python.3.12 — without it LOAD shows three lines instead of the boot screen')

  if (!apply) {
    return ['Retro Deck setup — nothing changed yet:', ...plan, '', 'Run /deck setup apply to do the → steps.'].join('\n')
  }

  const done: string[] = []
  if (!(await copyShell($, home, version))) return `Setup stopped: could not copy the shell scripts to ${shellDir(home)}.`
  done.push('✓ shell scripts copied')
  if (bin !== '') {
    for (const f of CMD_FILES) {
      if (cmds.foreign.includes(f)) { done.push(`! ${bin}/${f} is not ours; left alone`); continue }
      const text = await $.fs.read(`${$.plugin.root}/shell/${f}`).catch(() => '')
      const wrote = text !== '' && (await $.fs.write(`${bin}/${f}`, text).then(() => true).catch(() => false))
      done.push(wrote ? `✓ ${f} in ${bin}` : `! could not write ${bin}/${f}`)
    }
  }
  if (openPolicy) {
    for (const p of blocked) {
      const ran = await exe($, [p.exe, '-NoProfile', '-NonInteractive', '-Command', `${OPEN_POLICY} -Force`], 20000)
      done.push(ran.ok ? `✓ ${p.name}: execution policy for this user set to RemoteSigned` : `! ${p.name}: policy not changed (${ran.err || 'refused'}; a group policy may rule it)`)
    }
    if (blocked.length > 0) found = await profiles($)
  }
  for (const p of found) {
    const action = profileAction(p)
    if (action === 'skip-ansi') { done.push(`! ${p.name} profile left alone (not UTF-8)`); continue }
    if (action === 'skip-blocked') {
      if (p.exists) {
        const ran = await win($, 'rm', [p.path])
        done.push(ran.ok ? `✓ ${p.name}: profile removed again (only our block, refused by the policy "${p.policy}": the red error in new tabs is gone)` : `! could not remove ${p.path}`)
      } else done.push(`· ${p.name}: no profile created (policy "${p.policy}"); LOAD.cmd serves it`)
      continue
    }
    const rc = splitRc(p.text)
    const next = (rc.rest === '' ? '' : rc.rest + rc.eol + rc.eol) + BLOCK.join(rc.eol) + rc.eol
    const wrote = await $.fs.write(p.path, next).then(() => true).catch(() => false)
    done.push(wrote ? `✓ block in the ${p.name} profile` : `! could not write ${p.path}`)
  }
  if (fragment !== null) {
    const text = await $.fs.read(`${$.plugin.root}/terminal/c64-fragment.json`).catch(() => '')
    const wrote = text !== '' && (await $.fs.write(fragment, text).then(() => true).catch(() => false))
    done.push(wrote ? '✓ Windows Terminal profile "C64 Retro Deck" (appears after Windows Terminal restarts)' : '! Windows Terminal profile not written')
  }
  return ['Retro Deck set up:', ...done, '',
    'Open a new Windows Terminal tab — cmd or PowerShell — and type  LOAD "*",8,1  — or open the profile "C64 Retro Deck".',
    'Sessions started by LOAD draw in C64 colors (theme dark-ansi for that session only); a plain `claude` keeps your theme.',
    'Check the system with /deck doctor and send the result if anything looks wrong.'].join('\n')
}

export async function uninstallCommand($: EngineInterface, home: string, apply: boolean): Promise<string> {
  const localAppData = slashes((await $.env.get('LOCALAPPDATA')) ?? '')
  const found = await profiles($)
  const frag = localAppData === '' ? null : fragmentDir(localAppData)
  const hasFragment = frag !== null && (await $.fs.exists(frag).catch(() => false))
  const hasData = await $.fs.exists(`${home}/.claude/retro-deck`).catch(() => false)
  const bin = await cmdDir($, home)
  const cmds = await cmdState($, bin)

  const plan: string[] = []
  for (const p of found) {
    const rc = splitRc(p.text)
    plan.push(rc.hasBlock ? `→ remove the block from the ${p.name} profile ${p.path}` : `✓ no block in the ${p.name} profile`)
    if (rc.strays.length > 0) plan.push(`! ${p.path} line ${rc.strays.join(', ')} loads ${EDITION.loader} outside the block; remove it by hand`)
  }
  plan.push(cmds.ours.length > 0 ? `→ delete ${cmds.ours.join(' and ')} from ${bin}` : '✓ no LOAD.cmd or SYS.cmd of ours')
  plan.push(hasFragment ? '→ delete the Windows Terminal profile "C64 Retro Deck" (fragment)' : '✓ no Windows Terminal profile left')
  plan.push('· the execution policy stays as it is (Set-ExecutionPolicy -Scope CurrentUser Undefined takes back /deck setup apply policy)')
  plan.push(hasData ? '→ delete ~/.claude/retro-deck/ (shell copies, deck cache, restore list)' : '✓ ~/.claude/retro-deck/ is gone')

  const last = [
    'Then, in a shell:',
    `  claude plugin uninstall ${EDITION.plugin}`,
    '  claude plugin marketplace remove cc-retro-deck',
  ]
  if (!apply) {
    return ['Retro Deck uninstall — nothing removed yet:', ...plan, '', 'Run /deck uninstall apply to do the → steps.', ...last].join('\n')
  }

  const done: string[] = []
  for (const p of found) {
    const rc = splitRc(p.text)
    if (!rc.hasBlock) continue
    // Nothing but our block in it: setup made the file, so the file goes too.
    const wrote = rc.rest.trim() === ''
      ? (await win($, 'rm', [p.path])).ok
      : await $.fs.write(p.path, rc.rest + rc.eol).then(() => true).catch(() => false)
    done.push(wrote ? `✓ block removed from the ${p.name} profile` : `! could not write ${p.path}`)
  }
  if (cmds.ours.length > 0) {
    const ran = await win($, 'rm', cmds.ours.map(f => `${bin}/${f}`))
    done.push(ran.ok ? `✓ ${cmds.ours.join(' and ')} deleted` : `! ${cmds.ours.join(' and ')} not deleted`)
  }
  if (hasFragment && frag !== null) {
    const ran = await win($, 'rm', [frag])
    done.push(ran.ok ? '✓ Windows Terminal profile deleted (gone after Windows Terminal restarts)' : `! fragment not deleted: ${frag}`)
  }
  if (hasData) {
    const ran = await win($, 'rm', [`${home}/.claude/retro-deck`])
    done.push(ran.ok ? '✓ ~/.claude/retro-deck/ deleted' : '! ~/.claude/retro-deck/ not deleted')
  }
  done.push('· tabs opened by LOAD keep their colors until closed; SYS 64738 resets one now')
  done.push('· other Claude sessions with the plugin still loaded may write a few cache files until they end')
  return ['Retro Deck uninstalled outside the plugin:', ...done, '', ...last].join('\n')
}

/** /deck doctor: what the acceptance needs to know, as text to send back. */
export async function doctorCommand($: EngineInterface, home: string, selfTab: string): Promise<string> {
  const version = await pluginVersion($)
  const env = {
    WT_SESSION: await $.env.get('WT_SESSION'),
    TITLE_OFF: await $.env.get('CLAUDE_CODE_DISABLE_TERMINAL_TITLE'),
    USERPROFILE: await $.env.get('USERPROFILE'),
  }
  const report = await win($, 'doctor', [], 40000)
  const found = await profiles($)
  const stamp = await $.fs.read(`${shellDir(home)}/.version`).catch(() => null)
  const lines = [
    `Retro Deck doctor — cc-retro-deck-windows ${version}`,
    `${'session-WT_SESSION'.padEnd(24)} ${env.WT_SESSION ?? '(not passed to the plugin; not needed, the tab is found by its title)'}`,
    `${'session-title-off'.padEnd(24)} ${env.TITLE_OFF === '1' ? 'yes (started by LOAD)' : 'no (plain claude: no jump to this tab)'}`,
    `${'session-tab'.padEnd(24)} ${selfTab || '(none found)'}`,
    `${'home'.padEnd(24)} ${home} (USERPROFILE ${env.USERPROFILE ?? '?'})`,
    `${'shell-copy'.padEnd(24)} ${stamp === null ? 'not set up (/deck setup apply)' : `version ${stamp.trim()}`}`,
    ...found.map(p => `${('profile-' + p.name.replace(/ /g, '')).padEnd(24)} ${p.exists ? (splitRc(p.text).hasBlock ? 'block present' : 'no block') : 'no file'}${p.isReadable ? '' : ', NOT UTF-8'}, policy ${p.policy}${p.isBlocked ? ' (runs no profile)' : ''}  [${p.path}]`),
    `${'LOAD.cmd'.padEnd(24)} ${(await cmdDir($, home)) || '~/.local/bin not on PATH'}; ours: ${(await cmdState($, await cmdDir($, home))).ours.join(', ') || 'none'}`,
    report.ok ? report.out : `win.ps1 doctor FAILED: ${report.err || report.out || 'no answer'}`,
  ]
  return lines.join('\n')
}
