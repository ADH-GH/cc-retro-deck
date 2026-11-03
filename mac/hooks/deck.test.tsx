import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

const HOME = '/tmp/retro-deck-test-home'
const ROOT = `${HOME}/projects/042-demo`
const QUIET = { options: { crab: false, banner: false, autoOpen: false } }
const BAND = { hasSurvey: false, isWorking: true, maxRows: 8, bodyColumns: 120, scroll: { offset: 0, bodyRows: 7 }, view: {} }
const FOOTER = { modes: ['focus'] }

// What stands for the engine beneath the mod: the session's figures and the
// host calls (files, processes) the kit does not answer by itself.
function engine(on: On, registered: string[], env: Record<string, string> = {}, stdoutFor: (argv: readonly string[]) => string = () => '', files: Record<string, string> = {}) {
  mock.env(on, { HOME, TERM_PROGRAM: 'Apple_Terminal', ...env })
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
    if (e.name === 'tasks') throw new Error('"/tasks" refused: it is the built-in /tasks')   // as Claude Code 2.1.312 answers
    registered.push(e.name)
    return { value: { command: e.name } }
  })
  on('fs.list', ($, e) => ({
    value: Object.keys(files).filter(f => f.startsWith(`${e.path}/`)).map(f => ({ name: f.slice(e.path.length + 1), kind: 'file' as const })),
  }))
  on('fs.read', ($, e) => {
    if (!(e.path in files)) throw new Error(`ENOENT: ${e.path}`)
    return { value: files[e.path] }
  })
  on('fs.write', ($, e) => { files[e.path] = e.text; return { value: undefined } })
  on('process.run', ($, e) => ({ value: { exitCode: 0, stdout: stdoutFor(e.argv), stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }))
  on('ui.toast', () => ({ value: undefined }))
  on('ui.notify', () => ({ value: { isSent: true, channel: 'terminal_bell' } }))
  on('turn.start', ($, e) => ({ turnId: e.turnId }))
  on('turn.complete', () => ({ text: '' }))
  on('classic.PermissionRequest', () => ({}))
  on('ui.render', ($, e) => { const { Text } = $.ui.resolve(e); return <Text>{'engine'}</Text> })   // the engine's own drawing beneath the mod
}

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
    const ui = await $.ui.mount({ plugin: 'cc-retro-deck-mac', surface, component: 'SessionMode', props: FOOTER })
    expect(await ui.find({ type: 'Text', text: /BUSY/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /042-demo/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /\$1\.23/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /25%/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /5h 12%/ })).toBeDefined()        // reported
    expect(await ui.find({ type: 'Text', text: /7d/ })).toBeUndefined()          // not reported: not shown as 0%
    expect(await ui.find({ type: 'Text', text: /focus/ })).toBeDefined()
    await ui.unmount()
  }

  await $.turn.complete({ turnId: 't1', reason: 'answer', answer: 'hi', durationMs: 1200, isAborted: false })
  const done = await $.ui.mount({ plugin: 'cc-retro-deck-mac', surface: 'terminal', component: 'SessionMode', props: FOOTER })
  expect(await done.find({ type: 'Text', text: /DONE/ })).toBeDefined()
  await done.unmount()
})

test('/deck opens the pane and the pane draws its header', QUIET, async ($, on) => {
  mock.clock(on)
  engine(on, [])
  on('ui.open', () => ({ value: { isPlaced: true } }))
  await $.session.start({ cwd: ROOT, surface: 'terminal', isInteractive: true })

  const run = { command: 'deck', args: '', origin: { kind: 'composer' as const }, presentation: { isFullscreen: true, columns: 120 } }
  const opened = await $.command.run(run)
  expect(opened.text).toMatch(/Tasks opened/)
  const themed = await $.command.run({ ...run, args: 'theme amiga' })
  expect(themed.text).toBe('Deck theme: amiga')

  const props = { title: 'DECK', isFocused: true, bodyColumns: 120, placement: 'dock' as const, scroll: { offset: 0, bodyRows: 30 }, view: {} }
  for (const surface of ['terminal', 'desktop'] as const) {
    const pane = await $.ui.mount({ plugin: 'cc-retro-deck-mac', surface, component: 'Pane', requestId: 'deck', props })
    expect(await pane.find({ type: 'Text', text: /CLAUDE CODE TASKS/ })).toBeDefined()
    expect(await pane.find({ type: 'Text', text: /TABS/ })).toBeDefined()
    await pane.unmount()
  }
})

test('Claude Code idling for a minute (idle_prompt) is no question: the footer does not turn to ASK', QUIET, async ($, on) => {
  mock.clock(on)
  engine(on, [])
  on('classic.Notification', () => ({}))
  await $.session.start({ cwd: ROOT, surface: 'terminal', isInteractive: true })
  await $.turn.start({ text: 'hello', turnId: 't1' })
  await $.turn.complete({ turnId: 't1', reason: 'answer', answer: 'hi', durationMs: 1200, isAborted: false })
  await $.classic.Notification({ message: 'Claude is waiting for your input', notification_type: 'idle_prompt' })
  const footer = await $.ui.mount({ plugin: 'cc-retro-deck-mac', surface: 'terminal', component: 'SessionMode', props: FOOTER })
  expect(await footer.find({ type: 'Text', text: /ASK/ })).toBeUndefined()
  expect(await footer.find({ type: 'Text', text: /DONE/ })).toBeDefined()
  await footer.unmount()
})

test('a permission request turns the footer to ASK naming the tool', QUIET, async ($, on) => {
  mock.clock(on)
  engine(on, [])
  await $.session.start({ cwd: ROOT, surface: 'terminal', isInteractive: true })

  await $.classic.PermissionRequest({ tool_name: 'Bash', tool_input: { command: 'ls' } })
  const asking = await $.ui.mount({ plugin: 'cc-retro-deck-mac', surface: 'terminal', component: 'SessionMode', props: FOOTER })
  expect(await asking.find({ type: 'Text', text: /ASK permission: Bash/ })).toBeDefined()
  await asking.unmount()
})

test('the intro shows the banner and the 9x3 crab, then leaves the band empty', { options: { autoOpen: false, introEvery: 0 } }, async ($, on) => {
  const clock = mock.clock(on)
  engine(on, [])
  await $.session.start({ cwd: ROOT, surface: 'terminal', isInteractive: true })
  await clock.advance(200)

  const during = await $.ui.mount({ plugin: 'cc-retro-deck-mac', surface: 'terminal', component: 'AbovePrompt', props: BAND })
  // Apple Terminal form: a body row cut from the band, eyes looking the way it walks, feet below.
  expect(await during.find({ type: 'Text', text: /^▗$/ })).toBeDefined()
  expect(await during.find({ type: 'Text', text: /^ [▝▘]   [▝▘] $/ })).toBeDefined()
  expect(await during.find({ type: 'Text', text: /▘▘|▝▝/ })).toBeDefined()
  expect(await during.find({ type: 'Text', text: /RETRO DECK/ })).toBeDefined()
  await during.unmount()

  await clock.advance(7000)
  const after = await $.ui.mount({ plugin: 'cc-retro-deck-mac', surface: 'terminal', component: 'AbovePrompt', props: BAND })
  expect(await after.find({ type: 'Text', text: /^▗$/ })).toBeUndefined()
  expect(await after.find({ type: 'Text', text: /RETRO DECK/ })).toBeUndefined()
  await after.unmount()
  const footer = await $.ui.mount({ plugin: 'cc-retro-deck-mac', surface: 'terminal', component: 'SessionMode', props: FOOTER })
  expect(await footer.find({ type: 'Text', text: /042-demo/ })).toBeDefined()
  await footer.unmount()
})

test('the footer zoom buttons size the font of the frame\'s Terminal tab', QUIET, async ($, on) => {
  const calls: string[][] = []
  mock.clock(on)
  engine(on, [], { C64_FRAME: 'c64-4242' }, argv => {
    calls.push([...argv])
    return argv[0] === 'tmux' ? '/dev/ttys053\n' : argv[0] === 'osascript' ? '19\n' : ''
  })

  await $.session.start({ cwd: ROOT, surface: 'terminal', isInteractive: true })
  await $.turn.start({ text: 'hello', turnId: 't1' })
  const ui = await $.ui.mount({ plugin: 'cc-retro-deck-mac', surface: 'terminal', component: 'SessionMode', props: FOOTER })
  expect(await ui.find({ type: 'Text', text: /Zoom/ })).toBeDefined()
  await ui.press({ key: 'zoom-out' })
  await ui.unmount()

  const zoom = calls.find(argv => argv[0] === 'osascript' && argv.includes('/dev/ttys053'))
  expect(calls.some(argv => argv[0] === 'tmux' && argv.includes('c64-4242') && argv.includes('list-clients'))).toBe(true)
  expect(zoom?.slice(-2)).toEqual(['/dev/ttys053', '-1'])
})

test('the deck lists only sessions in an open Terminal tab, frames by the tab they are shown in', QUIET, async ($, on) => {
  const session = (pid: number, sessionId: string, project: string) =>
    JSON.stringify({ pid, sessionId, cwd: `${HOME}/projects/${project}`, status: 'idle', updatedAt: 0 })
  mock.clock(on)
  engine(on, [], {}, argv => {
    if (argv[0] === 'ps') return '100 ttys001\n200 ttys050\n300 ttys060\n'
    // Two Terminal tabs; the frame on ttys050 is shown in tab ttys002, the one on ttys060 in none.
    if (argv[0] === 'sh') return 'tab /dev/ttys001\ntab /dev/ttys002\npane /dev/ttys050 /dev/ttys002\n'
    return ''
  }, {
    [`${HOME}/.claude/sessions/100.json`]: session(100, 'sid-test', '042-demo'),
    [`${HOME}/.claude/sessions/200.json`]: session(200, 'sid-open', '043-open'),
    [`${HOME}/.claude/sessions/300.json`]: session(300, 'sid-closed', '044-closed'),
  })
  on('ui.open', () => ({ value: { isPlaced: true } }))
  await $.session.start({ cwd: ROOT, surface: 'terminal', isInteractive: true })
  await $.command.run({ command: 'deck', args: '', origin: { kind: 'composer' as const }, presentation: { isFullscreen: true, columns: 120 } })
  for (let i = 0; i < 200; i++) await Promise.resolve()   // the roster fills after the pane opened

  const props = { title: 'DECK', isFocused: true, bodyColumns: 120, placement: 'dock' as const, scroll: { offset: 0, bodyRows: 30 }, view: {} }
  const pane = await $.ui.mount({ plugin: 'cc-retro-deck-mac', surface: 'terminal', component: 'Pane', requestId: 'deck', props })
  expect(await pane.find({ type: 'Text', text: /2 TABS/ })).toBeDefined()
  expect(await pane.find({ type: 'Text', text: /043-open/ })).toBeDefined()
  expect(await pane.find({ type: 'Text', text: /044-closed/ })).toBeUndefined()
  expect(await pane.find({ type: 'Text', text: /OLD/ })).toBeUndefined()
  await pane.unmount()
})

test('/deck setup shows its plan first, apply adds the marked block, uninstall takes it out again', QUIET, async ($, on) => {
  const files: Record<string, string> = { [`${HOME}/.zshrc`]: 'export A=1\nsource ~/old/load.zsh\n' }
  mock.clock(on)
  engine(on, [], { CC_RETRO_DECK_NO_TERMINAL: '1' }, argv => (argv[0] === 'sh' && String(argv[2]).includes('command -v') ? '/usr/bin/found\n' : ''), files)
  await $.session.start({ cwd: ROOT, surface: 'terminal', isInteractive: true })
  const deck = (args: string) => $.command.run({ command: 'deck', args, origin: { kind: 'composer' as const }, presentation: { isFullscreen: true, columns: 120 } })

  const plan = await deck('setup')
  expect(plan.text).toMatch(/nothing changed/)
  expect(plan.text).toMatch(/line 2 loads another copy/)
  expect(files[`${HOME}/.zshrc`]).toBe('export A=1\nsource ~/old/load.zsh\n')

  const done = await deck('setup apply')
  expect(done.text).toMatch(/set up/)
  const rc = files[`${HOME}/.zshrc`] ?? ''
  expect(rc.startsWith('export A=1\nsource ~/old/load.zsh\n')).toBe(true)
  expect(rc).toContain('# >>> cc-retro-deck >>>\n')
  expect(rc).toContain('source ~/.claude/retro-deck/shell/load.zsh')
  expect(rc.trimEnd().endsWith('# <<< cc-retro-deck <<<')).toBe(true)

  await deck('setup apply')                                 // twice: still one block
  expect((files[`${HOME}/.zshrc`] ?? '').split('# >>> cc-retro-deck >>>').length).toBe(2)

  const gone = await deck('uninstall apply')
  expect(gone.text).toMatch(/claude plugin uninstall/)
  expect(files[`${HOME}/.zshrc`]).toBe('export A=1\nsource ~/old/load.zsh\n')
})
