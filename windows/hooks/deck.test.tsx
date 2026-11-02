import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import { encodeCommand } from './win'

// Not C:/…: the kit runs on the Mac and would read a drive path as relative to the plugin.
const HOME = '/win/home/test'
const ROOT = `${HOME}/projects/042-demo`
const LOCAL = `${HOME}/AppData/Local`
const QUIET = { options: { crab: false, banner: false, autoOpen: false, header: false } }
const BAND = { hasSurvey: false, isWorking: true, maxRows: 8, bodyColumns: 120, scroll: { offset: 0, bodyRows: 7 }, view: {} }
const FOOTER = { modes: ['focus'] }

/** The verb of a scripts/win.ps1 call, or '' for any other process. */
function verbOf(argv: readonly string[]): string {
  const i = argv.findIndex(a => a.endsWith('/scripts/win.ps1'))
  return i < 0 ? '' : argv[i + 1] ?? ''
}

// What stands for the engine beneath the mod: the session's figures and the
// host calls (files, processes) the kit does not answer by itself.
function engine(on: On, registered: string[], stdoutFor: (argv: readonly string[]) => string | null = () => '', files: Record<string, string> = {}) {
  mock.env(on, {
    USERPROFILE: HOME.replace(/\//g, '\\'), LOCALAPPDATA: LOCAL.replace(/\//g, '\\'), WT_SESSION: 'wt-test',
    PATH: `C:\\Windows\\system32;${HOME.replace(/\//g, '\\')}\\.local\\bin`,
  })
  mock.store(on)
  on('session.start', () => ({ cwd: ROOT }))
  on('session.id', () => ({ value: 'sid-test' }))
  on('session.root', () => ({ value: ROOT }))
  on('session.model', () => ({ value: 'claude-fable-5-1' }))
  on('session.turns', () => ({ value: 3 }))
  on('session.usage', () => ({
    value: { startedAt: 0, context: { window: 200000, tokens: 50000, percent: 25 }, rateLimits: [{ kind: 'five_hour', percentUsed: 12 }], cost: { usd: 1.23 } },
  }))
  on('command.register', ($, e) => {
    if (e.name === 'tasks') throw new Error('"/tasks" refused: it is the built-in /tasks')
    registered.push(e.name)
    return { value: { command: e.name } }
  })
  on('fs.list', ($, e) => ({
    value: Object.keys(files).filter(f => f.startsWith(`${e.path}/`)).map(f => ({ name: f.slice(e.path.length + 1), kind: 'file' as const, size: 0, mtimeMs: 0, isLink: false })),
  }))
  on('fs.read', ($, e) => {
    if (e.path.endsWith('/.claude-plugin/plugin.json')) return { value: '{"version":"0.12.0-beta.2"}' }
    if (e.path.includes('/shell/') && !e.path.startsWith(HOME)) return { value: `rem cc-retro-deck-windows ${e.path}` }
    if (e.path.endsWith('/terminal/c64-fragment.json')) return { value: '{"profiles":[]}' }
    if (!(e.path in files)) throw new Error(`ENOENT: ${e.path}`)
    return { value: files[e.path] }
  })
  on('fs.write', ($, e) => { files[e.path] = e.text; return { value: undefined } })
  on('fs.exists', ($, e) => ({ value: Object.keys(files).some(f => f === e.path || f.startsWith(`${e.path}/`)) }))
  on('process.run', ($, e) => {
    const out = stdoutFor(e.argv)
    return { value: { exitCode: out === null ? 1 : 0, stdout: out ?? '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('ui.toast', () => ({ value: undefined }))
  on('ui.notify', () => ({ value: { isSent: true, channel: 'terminal_bell' } }))
  on('turn.start', ($, e) => ({ turnId: e.turnId }))
  on('turn.complete', () => ({ text: '' }))
  on('classic.PermissionRequest', () => ({}))
  on('ui.render', ($, e) => { const { Text } = $.ui.resolve(e); return <Text>{'engine'}</Text> })
}

const deckRun = (args: string) => ({ command: 'deck', args, origin: { kind: 'composer' as const }, presentation: { isFullscreen: true, columns: 120 } })

test('registers /deck and draws the figures in the prompt footer while a turn runs', QUIET, async ($, on) => {
  const registered: string[] = []
  mock.clock(on)
  engine(on, registered)

  await $.session.start({ cwd: ROOT, surface: 'terminal', isInteractive: true })
  expect(registered).toContain('deck')
  expect(registered).toContain('pure')
  expect(registered).toContain('emul')

  await $.turn.start({ text: 'hello', turnId: 't1' })
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'cc-retro-deck-windows', surface, component: 'SessionMode', props: FOOTER })
    expect(await ui.find({ type: 'Text', text: /BUSY/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /042-demo/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /\$1\.23/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /5h 12%/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /7d/ })).toBeUndefined()
    await ui.unmount()
  }
})

test('the header band shows logo, sky, the two crabs hand in hand and the banner, and they walk over', { options: { autoOpen: false, introEvery: 0 } }, async ($, on) => {
  const clock = mock.clock(on)
  engine(on, [])
  await $.session.start({ cwd: ROOT, surface: 'terminal', isInteractive: true })

  const walking = await $.ui.mount({ plugin: 'cc-retro-deck-windows', surface: 'terminal', component: 'AbovePrompt', props: BAND })
  expect(await walking.find({ type: 'Text', text: /CLAUDE CODE/ })).toBeDefined()
  expect(await walking.find({ type: 'Text', text: /retro deck/ })).toBeDefined()
  expect(await walking.find({ type: 'Text', text: /Lovable/ })).toBeDefined()     // n8n stands behind the crabs at the start
  expect(await walking.find({ type: 'Text', text: /━━●━━/ })).toBeDefined()
  expect(await walking.find({ type: 'Text', text: /RETRO DECK V0\.12/ })).toBeDefined()
  expect(await walking.find({ type: 'Text', text: /proudly presented by Alf/ })).toBeDefined()
  await walking.unmount()

  await clock.advance(30000)              // over, and standing: the band stays
  const standing = await $.ui.mount({ plugin: 'cc-retro-deck-windows', surface: 'terminal', component: 'AbovePrompt', props: BAND })
  expect(await standing.find({ type: 'Text', text: /━━●━━/ })).toBeDefined()
  expect(await standing.find({ type: 'Text', text: /RETRO DECK V0\.12/ })).toBeDefined()
  await standing.unmount()
})

test('without the header the single crab and banner come and go, in block glyphs', { options: { autoOpen: false, introEvery: 0, header: false } }, async ($, on) => {
  const clock = mock.clock(on)
  engine(on, [])
  await $.session.start({ cwd: ROOT, surface: 'terminal', isInteractive: true })
  await clock.advance(200)
  const during = await $.ui.mount({ plugin: 'cc-retro-deck-windows', surface: 'terminal', component: 'AbovePrompt', props: BAND })
  expect(await during.find({ type: 'Text', text: /▜██████/ })).toBeDefined()
  await during.unmount()
  await clock.advance(7000)
  const after = await $.ui.mount({ plugin: 'cc-retro-deck-windows', surface: 'terminal', component: 'AbovePrompt', props: BAND })
  expect(await after.find({ type: 'Text', text: /▜██████/ })).toBeUndefined()
  await after.unmount()
})

test('the deck lists living sessions by the PowerShell tab they run in, and a row jumps there', QUIET, async ($, on) => {
  const session = (pid: number, sessionId: string, project: string) =>
    JSON.stringify({ pid, sessionId, cwd: `${HOME}/projects/${project}`, status: 'idle', updatedAt: 0 })
  const calls: string[][] = []
  mock.clock(on)
  engine(on, [], argv => {
    calls.push([...argv])
    if (verbOf(argv) === 'procs') return '100 4100\n200 4200\n'          // 300 is gone
    if (verbOf(argv) === 'jump') return argv[argv.length - 1] === '4200' ? 'ok' : 'none'
    return ''
  }, {
    [`${HOME}/.claude/sessions/100.json`]: session(100, 'sid-test', '042-demo'),
    [`${HOME}/.claude/sessions/200.json`]: session(200, 'sid-other', '043-other'),
    [`${HOME}/.claude/sessions/300.json`]: session(300, 'sid-gone', '044-gone'),
  })
  on('ui.open', () => ({ value: { isPlaced: true } }))
  await $.session.start({ cwd: ROOT, surface: 'terminal', isInteractive: true })
  await $.command.run(deckRun(''))
  for (let i = 0; i < 200; i++) await Promise.resolve()

  const props = { title: 'DECK', isFocused: true, bodyColumns: 120, placement: 'dock' as const, scroll: { offset: 0, bodyRows: 30 }, view: {} }
  const pane = await $.ui.mount({ plugin: 'cc-retro-deck-windows', surface: 'terminal', component: 'Pane', requestId: 'deck', props })
  expect(await pane.find({ type: 'Text', text: /2 TABS/ })).toBeDefined()
  expect(await pane.find({ type: 'Text', text: /043-other/ })).toBeDefined()
  expect(await pane.find({ type: 'Text', text: /044-gone/ })).toBeUndefined()
  await pane.unmount()

  // Both rows are idle at the same age, so which one is 001 is open: try both.
  let jumped = await $.command.run(deckRun('jump 002'))
  if (!/043-other/.test(jumped.text ?? '')) jumped = await $.command.run(deckRun('jump 001'))
  expect(jumped.text).toMatch(/Jumped to 043-other \(wt:4200\)/)
  expect(calls.some(argv => verbOf(argv) === 'jump' && argv[argv.length - 1] === '4200')).toBe(true)
})

test('the footer zoom buttons send Ctrl+= and Ctrl+- through win.ps1', QUIET, async ($, on) => {
  const calls: string[][] = []
  mock.clock(on)
  engine(on, [], argv => { calls.push([...argv]); return verbOf(argv) === 'zoom' ? 'ok' : '' })
  await $.session.start({ cwd: ROOT, surface: 'terminal', isInteractive: true })
  await $.turn.start({ text: 'hello', turnId: 't1' })
  const ui = await $.ui.mount({ plugin: 'cc-retro-deck-windows', surface: 'terminal', component: 'SessionMode', props: FOOTER })
  await ui.press({ key: 'zoom-out' })
  await ui.unmount()
  const zoom = calls.find(argv => verbOf(argv) === 'zoom')
  expect(zoom?.[zoom.length - 1]).toBe('-')
})

test('/deck restore opens a tab per closed session with LOAD --resume, encoded past wt.exe', QUIET, async ($, on) => {
  const calls: string[][] = []
  const files: Record<string, string> = {
    [`${HOME}/.claude/retro-deck/last-deck.json`]: JSON.stringify({ savedAt: 0, sessions: [{ sessionId: 'sid-old', cwd: `${HOME}/projects/045-old`, project: '045-old', tty: 'wt:9' }] }),
  }
  const clock = mock.clock(on)
  engine(on, [], argv => {
    calls.push([...argv])
    if (argv[0] === 'pwsh.exe') return null                        // only Windows PowerShell here
    return ''
  }, files)
  await $.session.start({ cwd: ROOT, surface: 'terminal', isInteractive: true })
  const running = $.command.run(deckRun('restore'))
  for (let i = 0; i < 20; i++) await clock.advance(200)   // the tabs open one after the other
  const done = await running
  expect(done.text).toMatch(/045-old/)
  const wt = calls.find(argv => argv[0] === 'wt.exe')
  expect(wt?.slice(0, 6)).toEqual(['wt.exe', '-w', '0', 'new-tab', '-d', `${HOME}/projects/045-old`])
  expect(wt).toContain('powershell.exe')
  expect(wt?.[wt.length - 1]).toBe(encodeCommand("if (Get-Command LOAD -ErrorAction SilentlyContinue) { LOAD '*,8,1' FAST '--resume' 'sid-old' } else { claude '--resume' 'sid-old' }"))
})

test('encodeCommand is UTF-16LE base64, as -EncodedCommand reads it', async () => {
  expect(encodeCommand('dir')).toBe('ZABpAHIA')
  expect(encodeCommand("LOAD '*,8,1'")).toBe('TABPAEEARAAgACcAKgAsADgALAAxACcA')
})

test('/deck setup: LOAD.cmd for cmd, the block where a policy runs it, no new profile where it cannot, uninstall takes all back', QUIET, async ($, on) => {
  const ps5 = `${HOME}/Documents/WindowsPowerShell/Microsoft.PowerShell_profile.ps1`
  const ps7 = `${HOME}/OneDrive/Documents/PowerShell/Microsoft.PowerShell_profile.ps1`
  const bin = `${HOME}/.local/bin`
  const files: Record<string, string> = { [ps5]: 'Set-Alias ll ls\r\n. C:\\old\\load.ps1\r\n' }
  const calls: string[][] = []
  let policy5 = 'Restricted'
  mock.clock(on)
  engine(on, [], argv => {
    calls.push([...argv])
    const asks = argv.some(a => a.startsWith('$PROFILE.CurrentUserCurrentHost'))
    if (argv[0] === 'powershell.exe' && asks) return `${ps5.replace(/\//g, '\\')}\r\n${policy5}\r\n`
    if (argv[0] === 'pwsh.exe' && asks) return `${ps7.replace(/\//g, '\\')}\r\nRemoteSigned\r\n`
    if (argv[0] === 'powershell.exe' && argv.some(a => a.startsWith('Set-ExecutionPolicy'))) { policy5 = 'RemoteSigned'; return '' }
    if (argv[0] === 'py') return '3.13.3\n'
    if (verbOf(argv) === 'rm') { for (const p of argv.slice(argv.indexOf('rm') + 1)) for (const f of Object.keys(files)) if (f === p || f.startsWith(`${p}/`)) delete files[f]; return '' }
    return ''
  }, files)
  await $.session.start({ cwd: ROOT, surface: 'terminal', isInteractive: true })

  const plan = await $.command.run(deckRun('setup'))
  expect(plan.text).toMatch(/nothing changed/)
  expect(plan.text).toMatch(/LOAD\.cmd and SYS\.cmd in .*\.local\/bin/)
  expect(plan.text).toMatch(/inert under the policy "Restricted"/)
  expect(plan.text).toMatch(/line 2 loads another copy/)
  expect(plan.text).toMatch(/optional: \/deck setup apply policy/)
  expect(files[ps5]).toBe('Set-Alias ll ls\r\n. C:\\old\\load.ps1\r\n')

  const done = await $.command.run(deckRun('setup apply'))
  expect(done.text).toMatch(/set up/)
  expect(files[`${bin}/LOAD.cmd`]).toContain('cc-retro-deck-windows')
  expect(files[`${bin}/SYS.cmd`]).toContain('cc-retro-deck-windows')
  expect((files[ps5] ?? '').startsWith('Set-Alias ll ls\r\n. C:\\old\\load.ps1\r\n\r\n# >>> cc-retro-deck >>>\r\n')).toBe(true)
  expect(files[ps7]).toContain('# >>> cc-retro-deck >>>\n')
  expect(files[`${LOCAL}/Microsoft/Windows Terminal/Fragments/cc-retro-deck/c64.json`]).toBe('{"profiles":[]}')
  expect(files[`${HOME}/.claude/retro-deck/shell/.version`]).toBe('0.12.0-beta.2')
  expect(calls.some(argv => argv.some(a => a.startsWith('Set-ExecutionPolicy')))).toBe(false)   // never on its own

  await $.command.run(deckRun('setup apply'))                 // twice: still one block
  expect((files[ps5] ?? '').split('# >>> cc-retro-deck >>>').length).toBe(2)

  const gone = await $.command.run(deckRun('uninstall apply'))
  expect(gone.text).toMatch(/claude plugin uninstall cc-retro-deck-windows@cc-retro-deck/)
  expect(files[ps5]).toBe('Set-Alias ll ls\r\n. C:\\old\\load.ps1\r\n')
  expect(files[ps7]).toBeUndefined()                         // only our block in it: the file goes
  expect(files[`${bin}/LOAD.cmd`]).toBeUndefined()
  expect(files[`${bin}/SYS.cmd`]).toBeUndefined()
  expect(files[`${LOCAL}/Microsoft/Windows Terminal/Fragments/cc-retro-deck/c64.json`]).toBeUndefined()
})

test('/deck setup creates no profile a Restricted policy would refuse, and "apply policy" opens it on request', QUIET, async ($, on) => {
  const ps5 = `${HOME}/Documents/WindowsPowerShell/Microsoft.PowerShell_profile.ps1`
  const files: Record<string, string> = {}
  let policy5 = 'Restricted'
  mock.clock(on)
  engine(on, [], argv => {
    const asks = argv.some(a => a.startsWith('$PROFILE.CurrentUserCurrentHost'))
    if (argv[0] === 'powershell.exe' && asks) return `${ps5.replace(/\//g, '\\')}\r\n${policy5}\r\n`
    if (argv[0] === 'pwsh.exe') return null
    if (argv[0] === 'powershell.exe' && argv.some(a => a.startsWith('Set-ExecutionPolicy -Scope CurrentUser RemoteSigned'))) { policy5 = 'RemoteSigned'; return '' }
    return ''
  }, files)
  await $.session.start({ cwd: ROOT, surface: 'terminal', isInteractive: true })

  const first = await $.command.run(deckRun('setup apply'))
  expect(first.text).toMatch(/no profile created \(policy "Restricted"\)/)
  expect(files[ps5]).toBeUndefined()

  const opened = await $.command.run(deckRun('setup apply policy'))
  expect(opened.text).toMatch(/execution policy for this user set to RemoteSigned/)
  expect(files[ps5]).toContain('# >>> cc-retro-deck >>>')
})
