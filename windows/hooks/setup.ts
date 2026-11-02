// /deck setup and /deck uninstall: everything the plugin needs outside its own folder, set up
// and taken back. Each shows what it would do first and acts only with `apply`.
//
// The plugin folder changes with every version (the install is a copy under the plugin
// cache), so the profile line cannot point there: the shell files are copied to
// ~/.claude/retro-deck/shell/ and kept current on every session start (refreshShell).
//
// Windows edition. The macOS and Linux editions have their own copy of this file (ADR 0003).
// Outside the plugin it touches: the PowerShell profiles (Windows PowerShell 5.1 and, when
// installed, PowerShell 7), a Windows Terminal fragment with the "C64 Retro Deck" profile, and
// ~/.claude/retro-deck/. settings.json of Windows Terminal stays as it is.
import type { EngineInterface } from 'claude-code'

import { exe, ps, slashes, win } from './win'

const EDITION = {
  loader: 'load.ps1',
  files: ['load.ps1', 'boot.py', 'trek.py', 'c64-settings.json'],
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

type Profile = { name: string; path: string; text: string; isReadable: boolean }

/** Each installed PowerShell's own profile file, as that PowerShell names it (Documents may be on OneDrive). */
async function profiles($: EngineInterface): Promise<Profile[]> {
  const out: Profile[] = []
  for (const sh of SHELLS) {
    const ran = await exe($, [sh.exe, '-NoProfile', '-NonInteractive', '-Command', '$PROFILE.CurrentUserCurrentHost'], 20000)
    if (!ran.ok || ran.out === '') continue                 // pwsh.exe not installed
    const path = slashes(ran.out.split('\n')[0]!.trim())
    const text = await $.fs.read(path).catch(() => null)
    // A profile saved as ANSI (umlauts in cp1252) reads back with U+FFFD; writing it would break them.
    out.push({ name: sh.name, path, text: text ?? '', isReadable: text === null || !text.includes('�') })
  }
  return out
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
}

async function copyShell($: EngineInterface, home: string, version: string): Promise<boolean> {
  const dir = shellDir(home)
  try {
    for (const f of EDITION.files) await $.fs.write(`${dir}/${f}`, await $.fs.read(`${$.plugin.root}/shell/${f}`))
    await $.fs.write(`${dir}/.version`, version)
    return true
  } catch { return false }
}

export async function setupCommand($: EngineInterface, home: string, apply: boolean): Promise<string> {
  const version = await pluginVersion($)
  const localAppData = slashes((await $.env.get('LOCALAPPDATA')) ?? '')
  const stamp = await $.fs.read(`${shellDir(home)}/.version`).catch(() => null)
  const found = await profiles($)
  const policy = (await win($, 'policy')).out.split('\n').map(s => s.trim())
  const effective = policy[1] ?? ''
  const py = await python($)
  const fragment = localAppData === '' ? null : `${fragmentDir(localAppData)}/c64.json`
  const hasFragment = fragment !== null && (await $.fs.exists(fragment).catch(() => false))

  const plan: string[] = []
  plan.push(`${stamp?.trim() === version ? '✓' : '→'} shell scripts in ~/.claude/retro-deck/shell/ (version ${version || '?'})`)
  if (found.length === 0) plan.push('! no PowerShell answered: LOAD cannot be set up')
  for (const p of found) {
    const rc = splitRc(p.text)
    if (!p.isReadable) plan.push(`! ${p.name} profile ${p.path} is not UTF-8; left alone — add the line from the README by hand`)
    else plan.push(`${rc.hasBlock ? '✓' : '→'} block in the ${p.name} profile ${p.path}, defines LOAD, RUN and SYS`)
    if (rc.strays.length > 0) plan.push(`! ${p.path} line ${rc.strays.join(', ')} loads another copy of ${EDITION.loader}; remove it by hand`)
  }
  if (fragment === null) plan.push('· Windows Terminal profile: LOCALAPPDATA unknown, skipped')
  else plan.push(`${hasFragment ? '✓' : '→'} Windows Terminal profile "C64 Retro Deck" (fragment, settings.json untouched)`)
  if (/^(Restricted|AllSigned|Undefined)$/i.test(effective)) {
    plan.push(`! Windows PowerShell runs no profile under the policy "${effective}": LOAD exists only in PowerShell 7 and in the "C64 Retro Deck" tab. To change it, run once:  ${OPEN_POLICY}`)
  }
  plan.push(py ? `✓ Python found (${py})` : '! Python missing: winget install Python.Python.3.12 — without it LOAD shows three lines instead of the boot screen')

  if (!apply) {
    return ['Retro Deck setup — nothing changed yet:', ...plan, '', 'Run /deck setup apply to do the → steps.'].join('\n')
  }

  const done: string[] = []
  if (!(await copyShell($, home, version))) return `Setup stopped: could not copy the shell scripts to ${shellDir(home)}.`
  done.push('✓ shell scripts copied')
  for (const p of found) {
    if (!p.isReadable) { done.push(`! ${p.name} profile left alone (not UTF-8)`); continue }
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
  if (/^(Restricted|AllSigned|Undefined)$/i.test(effective)) done.push(`! for LOAD in Windows PowerShell, run once:  ${OPEN_POLICY}`)
  return ['Retro Deck set up:', ...done, '',
    'Open a new Windows Terminal tab and type  LOAD "*",8,1  — or open the profile "C64 Retro Deck".',
    'Sessions started by LOAD draw in C64 colors (theme dark-ansi for that session only); a plain `claude` keeps your theme.',
    'Check the system with /deck doctor and send the result if anything looks wrong.'].join('\n')
}

export async function uninstallCommand($: EngineInterface, home: string, apply: boolean): Promise<string> {
  const localAppData = slashes((await $.env.get('LOCALAPPDATA')) ?? '')
  const found = await profiles($)
  const frag = localAppData === '' ? null : fragmentDir(localAppData)
  const hasFragment = frag !== null && (await $.fs.exists(frag).catch(() => false))
  const hasData = await $.fs.exists(`${home}/.claude/retro-deck`).catch(() => false)

  const plan: string[] = []
  for (const p of found) {
    const rc = splitRc(p.text)
    plan.push(rc.hasBlock ? `→ remove the block from the ${p.name} profile ${p.path}` : `✓ no block in the ${p.name} profile`)
    if (rc.strays.length > 0) plan.push(`! ${p.path} line ${rc.strays.join(', ')} loads ${EDITION.loader} outside the block; remove it by hand`)
  }
  plan.push(hasFragment ? '→ delete the Windows Terminal profile "C64 Retro Deck" (fragment)' : '✓ no Windows Terminal profile left')
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
    const wrote = await $.fs.write(p.path, rc.rest === '' ? '' : rc.rest + rc.eol).then(() => true).catch(() => false)
    done.push(wrote ? `✓ block removed from the ${p.name} profile` : `! could not write ${p.path}`)
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
    `${'session-WT_SESSION'.padEnd(24)} ${env.WT_SESSION ?? 'MISSING (not in Windows Terminal?)'}`,
    `${'session-title-off'.padEnd(24)} ${env.TITLE_OFF === '1' ? 'yes (started by LOAD)' : 'no (plain claude: no jump to this tab)'}`,
    `${'session-tab'.padEnd(24)} ${selfTab || '(none found)'}`,
    `${'home'.padEnd(24)} ${home} (USERPROFILE ${env.USERPROFILE ?? '?'})`,
    `${'shell-copy'.padEnd(24)} ${stamp === null ? 'not set up (/deck setup apply)' : `version ${stamp.trim()}`}`,
    ...found.map(p => `${('profile-' + p.name.replace(/ /g, '')).padEnd(24)} ${splitRc(p.text).hasBlock ? 'block present' : 'no block'}${p.isReadable ? '' : ', NOT UTF-8'}  [${p.path}]`),
    report.ok ? report.out : `win.ps1 doctor FAILED: ${report.err || report.out || 'no answer'}`,
  ]
  return lines.join('\n')
}
