# LOAD "*",8,1  --  startet Claude Code, wie ein C64 ein Programm von Diskette laedt (Windows, PowerShell).
#
# Eingebunden ueber /deck setup: es kopiert diese Dateien nach ~\.claude\retro-deck\shell\ und
# traegt in das PowerShell-Profil ($PROFILE, fuer Windows PowerShell und PowerShell 7) einen
# markierten Block ein, der sie laedt. /deck uninstall nimmt beides zurueck.
#
#   LOAD "*",8,1            Tab in C64-Farben, Einschaltbildschirm: der Star-Trek-Tribut (trek.py),
#                           bei zu kleinem Fenster die tanzende Krabbe (boot.py), dann der Rahmen:
#                           oben ein Feld mit Kopfleiste und Banner (head.py), darunter claude
#   LOAD "*",8,1 --resume   alles nach dem C64-Teil geht an claude weiter
#   LOAD "*",8,1 RAHMEN     hellblauer Grund statt dunkelblauem Bildschirm
#   LOAD "*",8,1 FAST       ohne Einschaltbildschirm, nur die drei Zeilen
#   LOAD "*",8,1 FLACH      ohne Rahmen: claude direkt im Tab, die Kopfleiste zeichnet der Mod
#   LOAD "ERIC",8,1         wie "*", aber mit New York statt der Enterprise (nyc.py): die
#                           Fassung fuer Eric, n8n Ambassador NYC; LOAD "BERTRAND",8,1 ebenso
#   LOAD "ARNO",8,1         Telekom in Magenta (magenta.py), fuer Arno von der Telekom
#   LOAD "JAN",8,1          Berlin im neuen n8n-Branding (berlin.py), fuer Jan Oberhauser
#                           dann selbst ueber der Eingabe
#   RUN                     nur claude, ohne alles
#   SYS 64738               Reset: Farben, Titel und Prompt des Tabs wie vorher
#
# Der Rahmen: tmux wie auf dem Mac gibt es hier nicht, Windows Terminal kann einen Tab aber in
# Felder teilen, nur nicht nachtraeglich auf eine Groesse setzen. Darum startet LOAD Claude Code in
# einem neuen Feld und schliesst sein eigenes; im neuen Feld legt head.py --frame dieselben Felder
# an wie frame.sh (oben neun Zeilen Kopfleiste, links und rechts drei Spalten, unten zwei Zeilen
# Rahmenfarbe), einmal; bei Groessenaenderung verteilt Windows Terminal sie anteilig. Endet Claude Code,
# schliessen sich die Hilfsfelder, und das Feld bleibt als PowerShell mit READY. als Prompt.
# Ohne Windows Terminal oder ohne Python: FLACH.
# Die Farben setzt LOAD per Steuersequenz (OSC 4/10/11/12) je Feld; Windows Terminal versteht das.
#
# Der Tabtitel bekommt die PID dieser PowerShell in eckigen Klammern, "C64 042-demo [1234]".
# Daran findet die Tafel den Tab wieder, wenn sie hinspringt. Damit Claude Code den Titel nicht
# ueberschreibt, laeuft es mit CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1.
#
# Reines ASCII: Windows PowerShell 5.1 liest Dateien ohne BOM als ANSI.

$global:C64Dir = $PSScriptRoot
$global:C64Esc = [char]27
$global:C64Bel = [char]7

# Colodore-Palette, ANSI 0-15 belegt wie in den Mac-Profilen und der Linux-Fassung.
# ANSI 8 traegt die Grundfarbe: Claude Code malt damit Flaechen, und grau passt nicht ins Bild.
function global:C64-Colors([string]$look) {
  $c = @{ black = '000000'; white = 'FFFFFF'; red = '813338'; cyan = '75CEC8'; purple = '8E3C97'; green = '56AC4D'
          blue = '2E2C9B'; yellow = 'EDF171'; lightRed = 'C46C71'; lightGreen = 'A9FF9F'; lightBlue = '706DEB'; lightGrey = 'B2B2B2' }
  if ($look -eq 'rahmen') { $bg = $c.lightBlue; $fg = $c.white; $cur = $c.white }
  else { $bg = $c.blue; $fg = $c.lightBlue; $cur = $c.lightBlue }
  $pal = @($c.black, $c.red, $c.green, $c.yellow, $c.lightBlue, $c.purple, $c.cyan, $c.lightGrey,
           $bg, $c.lightRed, $c.lightGreen, $c.yellow, $c.lightBlue, $c.purple, $c.cyan, $c.white)
  $rgb = { param($h) 'rgb:{0}/{1}/{2}' -f $h.Substring(0, 2), $h.Substring(2, 2), $h.Substring(4, 2) }
  $out = ''
  for ($i = 0; $i -lt 16; $i++) { $out += "$C64Esc]4;$i;$(& $rgb $pal[$i])$C64Bel" }
  $out += "$C64Esc]10;$(& $rgb $fg)$C64Bel$C64Esc]11;$(& $rgb $bg)$C64Bel$C64Esc]12;$(& $rgb $cur)$C64Bel"
  [Console]::Write($out)
}

# Ein Python, das wirklich startet: der Platzhalter aus dem Microsoft Store tut es nicht.
function global:C64-Python {
  foreach ($cand in @(@('py', '-3'), @('python'), @('python3'))) {
    $cmd = Get-Command $cand[0] -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $cmd) { continue }
    $pre = @($cand | Select-Object -Skip 1)
    # Den echten Interpreter zurueckgeben, nicht py.exe: der Launcher erkennt -3 nur ohne
    # Anfuehrungszeichen, Start-Process setzt sie aber, und Python bricht dann mit "Unknown option" ab.
    # Ganz auslesen: Select-Object -First 1 im Fluss bricht den Prozess ab und verfaelscht $LASTEXITCODE.
    try { $out = @(& $cmd.Source @pre -c 'import sys; print(sys.executable)' 2>$null) } catch { continue }
    if ($LASTEXITCODE -ne 0) { continue }
    $real = [string]($out | Select-Object -First 1)
    if ($real -and (Test-Path -LiteralPath $real)) { return $real }
    return (@($cmd.Source) + $pre) -join '|'
  }
  return ''
}

function global:C64-Project {
  $parts = (Get-Location).Path -split '[\\/]' | Where-Object { $_ }
  $hit = $parts | Where-Object { $_ -match '^\d{3}-' } | Select-Object -First 1
  if ($hit) { $hit } else { $parts[-1] }
}

# Claude Code im Rahmen: dieses Feld legt C64-Frame als letztes Hilfsfeld an, es bleibt. Farben,
# Tabtitel mit der PID dieser PowerShell, und ~/.claude/retro-deck/<id>.pid, an der die Hilfsfelder
# sehen, dass die Sitzung laeuft. Endet Claude Code, schliessen sie sich, und dieses Feld hat den Tab
# mit READY. als Prompt.
function global:C64-Run([string]$look, [string]$id, [string]$py, [string[]]$pass) {
  C64-Colors $look
  $Host.UI.RawUI.WindowTitle = "C64 $(C64-Project) [$PID]"
  Set-Item function:global:prompt { "`n$([char]27)[94mREADY.$([char]27)[0m`n" }
  $dir = Join-Path $HOME '.claude\retro-deck'
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  $pidFile = Join-Path $dir "$id.pid"
  Set-Content -Path $pidFile -Value $PID -Encoding ASCII
  C64-Log $id "C64-Run python '$py'"
  $env:C64_FRAME = $id
  $env:CLAUDE_CODE_DISABLE_TERMINAL_TITLE = '1'
  try { & claude --settings (Join-Path $C64Dir 'c64-settings.json') @pass }
  finally {
    Remove-Item $pidFile, (Join-Path $dir "$id.alive") -ErrorAction SilentlyContinue
    Remove-Item env:C64_FRAME, env:CLAUDE_CODE_DISABLE_TERMINAL_TITLE -ErrorAction SilentlyContinue
  }
}

# Laeuft diese Konsole in Windows Terminal? WT_SESSION fehlt, wenn Windows eine ausserhalb gestartete
# Konsole an Windows Terminal uebergibt (Standardterminal, etwa cmd aus dem Startmenue). Dann gehoert
# das versteckte Konsolenfenster aber dem Fenster von Windows Terminal; in conhost nicht.
function global:C64-InWT {
  if ($env:WT_SESSION) { return $true }
  try {
    if (-not ('C64Host' -as [type])) {
      Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices;
public static class C64Host {
  [DllImport("kernel32.dll")] static extern IntPtr GetConsoleWindow();
  [DllImport("user32.dll")] static extern IntPtr GetAncestor(IntPtr h, uint f);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  public static uint OwnerPid() {
    IntPtr w = GetConsoleWindow(); if (w == IntPtr.Zero) return 0;
    IntPtr root = GetAncestor(w, 3); uint pid; GetWindowThreadProcessId(root == IntPtr.Zero ? w : root, out pid);
    return pid;
  }
}
'@
    }
    $owner = [C64Host]::OwnerPid()
    return [bool]($owner -and (Get-Process -Id $owner -ErrorAction SilentlyContinue).ProcessName -eq 'WindowsTerminal')
  } catch { return $false }
}

# LOAD.cmd aus einer PowerShell ohne unseren Profilblock (etwa Windows PowerShell 5.1): LOAD.cmd
# laeuft dann als Kind und kann die PowerShell darueber nicht beenden, ihr Feld bliebe ueber dem
# Rahmen stehen. Darum Esc, "exit 0" und Enter in den Eingabepuffer der gemeinsamen Konsole; die
# PowerShell liest das, sobald LOAD.cmd fertig ist, und endet mit 0 (Windows Terminal schliesst ein
# Feld nur bei 0). Aus cmd direkt aufgerufen ist der Elternteil von LOAD.cmd keine Shell: nichts zu tun.
function global:C64-ExitParentShell {
  try {
    $cmdPid = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
    $cmdProc = Get-CimInstance Win32_Process -Filter "ProcessId=$cmdPid"
    if ($cmdProc.Name -ne 'cmd.exe') { return }
    $shell = Get-CimInstance Win32_Process -Filter "ProcessId=$($cmdProc.ParentProcessId)"
    if ($shell.Name -notin @('powershell.exe', 'pwsh.exe')) { return }
    if (-not ('C64Input' -as [type])) {
      Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices;
public static class C64Input {
  [StructLayout(LayoutKind.Explicit, CharSet = CharSet.Unicode)]
  struct Rec { [FieldOffset(0)] public ushort Type; [FieldOffset(4)] public int Down; [FieldOffset(8)] public ushort Repeat;
               [FieldOffset(10)] public ushort Vk; [FieldOffset(12)] public ushort Scan; [FieldOffset(14)] public char Ch;
               [FieldOffset(16)] public uint State; }
  [DllImport("kernel32.dll", SetLastError = true)] static extern IntPtr GetStdHandle(int n);
  [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
  static extern bool WriteConsoleInputW(IntPtr h, Rec[] r, int n, out int written);
  public static bool Type(string keys) {
    var recs = new Rec[keys.Length * 2];
    for (int i = 0; i < keys.Length; i++) {
      char c = keys[i];
      ushort vk = c == '\r' ? (ushort)0x0D : c == (char)27 ? (ushort)0x1B : (ushort)0;
      recs[2 * i] = new Rec { Type = 1, Down = 1, Repeat = 1, Vk = vk, Ch = c };
      recs[2 * i + 1] = new Rec { Type = 1, Down = 0, Repeat = 1, Vk = vk, Ch = c };
    }
    int w; return WriteConsoleInputW(GetStdHandle(-10), recs, recs.Length, out w);
  }
}
'@
    }
    [void][C64Input]::Type("$([char]27)exit 0`r")
  } catch { }
}

# ~/.claude/retro-deck/<id>.log: was der Rahmen tat; zum Einsenden, wenn er ausbleibt.
function global:C64-Log([string]$id, [string]$msg) {
  $dir = Join-Path $HOME '.claude\retro-deck'
  Add-Content -Path (Join-Path $dir "$id.log") -Value "$(Get-Date -Format HH:mm:ss) $msg" -ErrorAction SilentlyContinue
}

# Der Rahmen, ganz ohne swap-pane: Schliesst ein Feld, dessen Inhalt getauscht wurde, stuerzt Windows
# Terminal 1.24 bei der naechsten Groessenaenderung ab und nimmt alle Fenster mit. Ein neues Feld
# entsteht aber immer unten oder rechts, darum in dieser Reihenfolge:
#   1. dieses Feld (LOAD) teilt unten ab: das neue Feld ist der linke Rand, dieses wird die Kopfleiste
#   2. der linke Rand teilt rechts ab: das neue Feld ist Claude Code (C64-Run), es bleibt
#   3. Claude Code teilt rechts den rechten Rand ab, dann unten den unteren
#   4. hier laeuft danach head.py --head im Vordergrund, bis die Sitzung endet
# Die Felder bleiben stehen; bei Groessenaenderung verteilt Windows Terminal sie anteilig, in der
# Groesse vom Start stimmt der Rahmen genau. Endet Claude Code, enden alle Hilfsfelder und dieses
# Feld; das von Claude Code bleibt als PowerShell mit READY.
function global:C64-Frame([string]$look, [string]$py, [string[]]$pass, [int]$cols, [int]$rows) {
  $id = 'wt-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
  $dir = Join-Path $HOME '.claude\retro-deck'
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  $wt = (Get-Command wt.exe).Source
  $feld = '{6b3c64c6-4c0d-4f8e-9a64-0c64de5c0de2}'     # Profil "C64 Retro Deck Feld": ohne Innenabstand
  $cwd = (Get-Location).Path
  $exe, $pre = $py -split '\|'; $pre = @($pre | Where-Object { $_ })
  $head = Join-Path $C64Dir 'head.py'
  $inv = [Globalization.CultureInfo]::InvariantCulture
  $share = { param($x) [Math]::Min(0.995, [Math]::Max(0.005, $x)).ToString('0.000', $inv) }
  $split = {
    param([string]$dirFlag, $x, [string[]]$cmd)
    & $wt -w 0 split-pane $dirFlag -s (& $share $x) -p $feld -d $cwd @cmd
    C64-Log $id "split-pane $dirFlag $(& $share $x) $(if ($cmd[-1].Length -gt 20) { 'claude' } else { $cmd[-1] }) -> $LASTEXITCODE"
  }
  $waitFor = {
    param([string]$file)
    $end = (Get-Date).AddSeconds(8)
    while ((Get-Date) -lt $end) { if (Test-Path (Join-Path $dir $file)) { return $true }; Start-Sleep -Milliseconds 100 }
    C64-Log $id "$file did not come up"; return $false
  }
  $focus = { param([string]$to) & $wt -w 0 move-focus $to; C64-Log $id "move-focus $to -> $LASTEXITCODE" }
  C64-Log $id "frame ${cols}x$rows python '$py' wt $wt"
  $fill = { param([string]$role) @($exe) + $pre + @($head, '--fill', $id, $role) }

  # 1. Linker Rand unten neu (gross); dieses Feld behaelt gut neun Zeilen fuer die Kopfleiste. Es hat
  #    das Profil des Tabs, mit Innenabstand oben und unten: gemessen kostet er gut anderthalb Zeilen.
  & $split '-H' (($rows - 10.8) / $rows) (& $fill 'left')
  if (& $waitFor "$id.left.up") {
    Start-Sleep -Milliseconds 400
    # 2. Claude Code rechts neben dem linken Rand; der Fokus wandert ins neue Feld und bleibt dort.
    $list = ($pass | ForEach-Object { "'" + ($_ -replace "'", "''") + "'" }) -join ','
    $run = ". '$((Join-Path $C64Dir 'load.ps1') -replace "'", "''")'; C64-Run '$look' '$id' '$($py -replace "'", "''")' @($list)"
    $b64 = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($run))
    $claude = @('powershell.exe', '-NoLogo', '-NoProfile', '-NoExit', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $b64)
    & $split '-V' (($cols - 3) / $cols) $claude
    if (& $waitFor "$id.pid") {
      Start-Sleep -Milliseconds 600
      # 3. Rechter und unterer Rand schmal, einzeln, mit Pause; danach zurueck zu Claude Code.
      & $split '-V' (3.4 / ($cols - 3)) (& $fill 'right')
      if (& $waitFor "$id.right.up") { Start-Sleep -Milliseconds 400; & $focus 'left'; Start-Sleep -Milliseconds 600 }
      & $split '-H' (2.4 / ($rows - 9)) (& $fill 'bottom')
      if (& $waitFor "$id.bottom.up") { Start-Sleep -Milliseconds 400; & $focus 'up' }
    }
  }
  # Kam Claude Code nicht hoch (Windows Terminal lehnte die Teilung ab): LOAD startet es hier ohne Rahmen.
  if (-not (Test-Path (Join-Path $dir "$id.pid"))) { C64-Log $id 'no claude pane: flat'; $global:C64FrameOk = $false; return }
  # 4. Dieses Feld ist die Kopfleiste, bis die Sitzung endet (head.py sieht es an <id>.pid).
  $env:PYTHONUTF8 = '1'
  & $exe @pre $head '--head' $id
  C64-Log $id 'head done, LOAD pane closes'
  $global:C64FrameOk = $true
}

function global:LOAD {
  $look = 'screen'; $fast = $false; $flat = $false; $viaCmd = $false; $disk = '*'; $pass = @()
  foreach ($a in $args) {
    if ($a -is [array]) { $a = ($a -join ',') }          # LOAD "*",8,1 kommt als ein Array an
    switch -Regex ([string]$a) {
      '^\*(,8(,1)?)?$' { break }                         # der C64-Teil, verschluckt
      '^(?i)(eric|bertrand|arno|jan)(,8(,1)?)?$' { $disk = $Matches[1].ToUpper(); break }   # aus cmd kommt der Name allein
      '^(?i)rahmen$' { $look = 'rahmen'; break }
      '^(?i)fast$' { $fast = $true; break }
      '^(?i)(flach|flat)$' { $flat = $true; break }
      '^__CMD__$' { $viaCmd = $true; break }              # von LOAD.cmd: cmd schliesst danach
      default { $pass += [string]$a }
    }
  }
  $interactive = -not [Console]::IsOutputRedirected
  if ($interactive) { C64-Colors $look }
  if (-not (Test-Path variable:global:C64OldTitle)) { $global:C64OldTitle = $Host.UI.RawUI.WindowTitle }
  $Host.UI.RawUI.WindowTitle = "C64 $(C64-Project) [$PID]"

  $py = if ($interactive) { C64-Python } else { '' }
  if ($fast -or -not $py) {
    ''; "SEARCHING FOR $disk"; Start-Sleep -Milliseconds 400
    'LOADING'; Start-Sleep -Milliseconds 400
    'READY.'; Start-Sleep -Milliseconds 300
  } else {
    $env:PYTHONUTF8 = '1'
    $exe, $pre = $py -split '\|'; $pre = @($pre | Where-Object { $_ })
    if ($disk -ne '*') { & $exe @pre (Join-Path $C64Dir $(switch ($disk) { 'ARNO' { 'magenta.py' } 'JAN' { 'berlin.py' } default { 'nyc.py' } })) $disk }
    else { & $exe @pre (Join-Path $C64Dir 'trek.py') }
    if ($LASTEXITCODE -ne 0) { & $exe @pre (Join-Path $C64Dir 'boot.py') }
  }

  # Die Shell danach im C64-Ton: READY. als Prompt (ANSI 12 = Hellblau), Eingabe darunter.
  if (-not (Test-Path function:global:C64OldPrompt)) {
    Set-Item function:global:C64OldPrompt (Get-Item function:prompt).ScriptBlock
  }
  Set-Item function:global:prompt { "`n$([char]27)[94mREADY.$([char]27)[0m`n" }

  # Das C64-Theme gilt nur fuer Sitzungen aus LOAD (dark-ansi zeichnet in den 16 Farben oben);
  # als Datei, weil Windows PowerShell 5.1 Anfuehrungszeichen in Argumenten verschluckt.
  $wt = Get-Command wt.exe -ErrorAction SilentlyContinue
  $inWT = $wt -and (C64-InWT)
  $size = $Host.UI.RawUI.WindowSize
  if (-not $flat -and $interactive -and $py -and $inWT -and $size.Width -ge 20 -and $size.Height -ge 16) {
    # Als Anweisung, nicht in if (...): sonst finge PowerShell die Ausgabe der Kopfleiste ein.
    C64-Frame $look $py $pass $size.Width $size.Height
    if ($global:C64FrameOk) {
      # Die Sitzung ist zu Ende. cmd schliesst LOAD.cmd bei Rueckgabe 64 (und endet mit 0); eine
      # PowerShell ueber LOAD.cmd bekommt "exit 0" getippt; eine PowerShell mit LOAD als Funktion
      # endet hier selbst mit 0. Windows Terminal schliesst ein Feld nur bei 0.
      if ($viaCmd) { C64-ExitParentShell }
      [Environment]::Exit($(if ($viaCmd) { 64 } else { 0 }))
    }
  }
  if (-not $flat) {
    C64-Log 'load' "no frame: interactive=$interactive python='$py' wt=$([bool]$wt) inWT=$inWT size=$($size.Width)x$($size.Height)"
  }
  $env:CLAUDE_CODE_DISABLE_TERMINAL_TITLE = '1'
  try { & claude --settings (Join-Path $C64Dir 'c64-settings.json') @pass }
  finally { Remove-Item env:CLAUDE_CODE_DISABLE_TERMINAL_TITLE -ErrorAction SilentlyContinue }
}

# RUN allein startet ebenfalls -- fuer alle, die nach LOAD aus Gewohnheit RUN tippen.
function global:RUN { & claude @args }

# SYS 64738 ist der Reset-Vektor des C64: Farben, Titel und Prompt des Tabs zurueck.
function global:SYS {
  if ("$($args[0])" -ne '64738') { '?SYNTAX  ERROR'; return }
  [Console]::Write("$C64Esc]104$C64Bel$C64Esc]110$C64Bel$C64Esc]111$C64Bel$C64Esc]112$C64Bel")
  if (Test-Path function:global:C64OldPrompt) {
    Set-Item function:global:prompt (Get-Item function:global:C64OldPrompt).ScriptBlock
    Remove-Item function:global:C64OldPrompt
  }
  if (Test-Path variable:global:C64OldTitle) { $Host.UI.RawUI.WindowTitle = $global:C64OldTitle; Remove-Variable C64OldTitle -Scope Global }
  Clear-Host
}
