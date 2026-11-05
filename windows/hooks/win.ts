// Windows: everything the hooks need from the system goes through PowerShell. A hook calls
// either a short command (ps) or a verb of scripts/win.ps1 (win), never a Unix tool.
//
// Windows edition only; the macOS and Linux editions have no such file (ADR 0003, 0005).
import type { EngineInterface } from 'claude-code'

export type Ran = { ok: boolean; out: string; err: string }

const POWERSHELL = ['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass']

/** Forward slashes: $.fs takes them on Windows, and paths compare the same way everywhere. */
export function slashes(path: string): string { return path.replace(/\\/g, '/') }

async function run($: EngineInterface, argv: string[], timeoutMs: number): Promise<Ran> {
  const ran = await Promise.race([
    $.process.run(argv, { timeoutMs }).catch(err => ({ exitCode: 1, stdout: '', stderr: String(err) })),
    // Our own deadline: the host's timeout has been seen not to fire (macOS ps, 0.10.6).
    $.clock.sleep(timeoutMs + 1000).then(() => null),
  ])
  if (ran === null) return { ok: false, out: '', err: 'timed out' }
  return { ok: ran.exitCode === 0, out: (ran.stdout ?? '').replace(/\r/g, '').trim(), err: (ran.stderr ?? '').replace(/\r/g, '').trim() }
}

/** A PowerShell command line in Windows PowerShell 5.1, without the person's profile. */
export function ps($: EngineInterface, command: string, timeoutMs = 15000): Promise<Ran> {
  return run($, [...POWERSHELL, '-Command', command], timeoutMs)
}

/** A verb of scripts/win.ps1: procs, jump, front, tabs, zoom, head, rm, policy, doctor. */
export function win($: EngineInterface, verb: string, args: string[] = [], timeoutMs = 15000): Promise<Ran> {
  return run($, [...POWERSHELL, '-File', `${$.plugin.root}/scripts/win.ps1`, verb, ...args], timeoutMs)
}

/** Any other program by name, as the PATH finds it (wt.exe, pwsh.exe, py.exe). */
export function exe($: EngineInterface, argv: string[], timeoutMs = 15000): Promise<Ran> {
  return run($, argv, timeoutMs)
}

/** Text as PowerShell's -EncodedCommand wants it: UTF-16LE, then base64. No `;` reaches wt.exe. */
export function encodeCommand(text: string): string {
  const bytes: number[] = []
  for (let i = 0; i < text.length; i++) {
    const c = text.charCodeAt(i)
    bytes.push(c & 0xff, c >> 8)
  }
  const abc = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
  let out = ''
  for (let i = 0; i < bytes.length; i += 3) {
    const [a, b, c] = [bytes[i] ?? 0, bytes[i + 1], bytes[i + 2]]
    const n = (a << 16) | ((b ?? 0) << 8) | (c ?? 0)
    out += abc[(n >> 18) & 63]! + abc[(n >> 12) & 63]!
    out += b === undefined ? '=' : abc[(n >> 6) & 63]!
    out += c === undefined ? '=' : abc[n & 63]!
  }
  return out
}

/** A string literal for PowerShell: single quotes, a quote inside doubled. */
export function psQuote(text: string): string { return `'${text.replace(/'/g, "''")}'` }
