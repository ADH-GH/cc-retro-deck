import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

import { C64 } from './basic'

const HOME = '/tmp/retro-deck-test-home'
const ROOT = `${HOME}/projects/042-demo`
const QUIET = { options: { crab: false, banner: false, autoOpen: false } }
const PANE = { title: 'C64', isFocused: true, bodyColumns: 120, placement: 'dock' as const, scroll: { offset: 0, bodyRows: 30 }, view: {} }
const cmd = (command: string, args: string) => ({ command, args, origin: { kind: 'composer' as const }, presentation: { isFullscreen: true, columns: 120 } })

function engine(on: On) {
  mock.env(on, { USERPROFILE: HOME, WT_SESSION: 'wt-test' })
  mock.store(on)
  on('session.start', () => ({ cwd: ROOT }))
  on('session.id', () => ({ value: 'sid-test' }))
  on('session.root', () => ({ value: ROOT }))
  on('session.model', () => ({ value: 'claude-fable-5-1' }))
  on('session.turns', () => ({ value: 3 }))
  on('session.usage', () => ({
    value: { startedAt: 0, context: { window: 200000, tokens: 50000, percent: 25 }, rateLimits: [], cost: { usd: 1.23 } },
  }))
  on('command.register', ($, e) => ({ value: { command: e.name } }))
  on('fs.list', () => ({ value: [] }))
  on('fs.read', () => ({ value: '' }))
  on('fs.write', () => ({ value: undefined }))
  on('process.run', () => ({ value: { exitCode: 0, stdout: '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.render', ($, e) => { const { Text } = $.ui.resolve(e); return <Text>{'engine'}</Text> })   // the engine's own drawing beneath the mod
}

// ---- the interpreter on its own -------------------------------------------

test('BASIC V2: a FOR loop prints, a string function works, errors read like the real ones', async () => {
  const c = new C64(() => 0)
  c.clearScreen()
  c.submit('10 FOR I=1 TO 3')
  c.submit('20 PRINT "HI";I')
  c.submit('30 NEXT I')
  c.submit('40 PRINT LEFT$("COMMODORE",4);LEN("64")')
  c.submit('RUN')
  while (c.step(100)) { /* run to the end */ }
  const text = c.snapshot().rows.map(r => r.text.trimEnd()).filter(Boolean)
  expect(text).toEqual(['HI 1', 'HI 2', 'HI 3', 'COMM 2', 'READY.'])

  c.clearScreen()
  c.submit('PRINT 1/0')
  expect(c.snapshot().rows[1].text.trimEnd()).toBe('?DIVISION BY ZERO ERROR')

  c.clearScreen()
  c.submit('POKE 53280,0:POKE 53281,1')
  const shot = c.snapshot()
  expect(shot.border).toBe(0)
  expect(shot.background).toBe(1)
})

test('BASIC V2: INPUT waits for the keyboard and GOTO loops until RUN/STOP', async () => {
  const c = new C64(() => 0)
  c.clearScreen()
  c.submit('10 INPUT "NAME";N$')
  c.submit('20 PRINT "HELLO ";N$')
  c.submit('30 GOTO 30')
  c.submit('RUN')
  c.step(10)
  expect(c.snapshot().waiting).toBe('input')
  c.submit('ADH')
  c.step(50)
  expect(c.snapshot().rows[1].text.trimEnd()).toBe('HELLO ADH')
  expect(c.isRunning).toBe(true)
  c.submit('')                     // any line while running is RUN/STOP
  expect(c.isRunning).toBe(false)
  expect(c.snapshot().rows.some(r => r.text.startsWith('BREAK IN 30'))).toBe(true)
})

// ---- /pure ---------------------------------------------------------------

test('/pure reads BASIC as deck actions: LIST, POKE 53280 recolors the band, PRINT evaluates', QUIET, async ($, on) => {
  mock.clock(on)
  engine(on)
  await $.session.start({ cwd: ROOT, surface: 'terminal', isInteractive: true })

  const list = await $.command.run(cmd('pure', 'LIST'))
  expect(list.text).toBe('READY.')                      // the kit runs no other session
  const dir = await $.command.run(cmd('pure', 'LOAD "$",8'))
  expect(dir.text).toMatch(/^0 "CLAUDE CODE/)
  expect(dir.text).toMatch(/BLOCKS FREE\./)

  const poke = await $.command.run(cmd('pure', 'POKE 53280,0'))
  expect(poke.text).toBe('READY.')
  const footer = await $.ui.mount({ plugin: 'cc-retro-deck-windows', surface: 'terminal', component: 'SessionMode', props: { modes: [] } })
  expect(await footer.find({ type: 'Text', text: /042-demo/ })).toBeDefined()
  await footer.unmount()

  const print = await $.command.run(cmd('pure', 'PRINT 6*7;CHR$(65)'))
  expect(print.text).toBe(' 42 A\nREADY.')

  const nonsense = await $.command.run(cmd('pure', 'FROBNICATE'))
  expect(nonsense.text).toMatch(/\?SYNTAX  ERROR/)
})

// ---- /emul ---------------------------------------------------------------

test('/emul types a program blind and draws the screen in its pane', QUIET, async ($, on) => {
  const clock = mock.clock(on)
  engine(on)
  await $.session.start({ cwd: ROOT, surface: 'terminal', isInteractive: true })

  await $.command.run(cmd('emul', '10 PRINT "RETRO DECK"'))
  const ran = await $.command.run(cmd('emul', 'RUN'))
  await clock.advance(500)
  expect(ran.text).toContain('READY.')

  for (const surface of ['terminal', 'desktop'] as const) {
    const pane = await $.ui.mount({ plugin: 'cc-retro-deck-windows', surface, component: 'Pane', requestId: 'c64', props: PANE })
    expect(await pane.find({ type: 'Text', text: /RETRO DECK/ })).toBeDefined()
    expect(await pane.find({ type: 'Text', text: /COMMODORE 64 BASIC V2/ })).toBeDefined()
    await pane.unmount()
  }
})
