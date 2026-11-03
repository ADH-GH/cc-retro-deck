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
#                           dann selbst ueber der Eingabe
#   RUN                     nur claude, ohne alles
#   SYS 64738               Reset: Farben, Titel und Prompt des Tabs wie vorher
#
# Der Rahmen: tmux wie auf dem Mac gibt es hier nicht, Windows Terminal kann einen Tab aber in
# Felder teilen. LOAD teilt mit einem `wt`-Aufruf in dieselben Felder wie frame.sh: dieses Feld
# oben wird die Kopfleiste (head.py, neun Zeilen), links und rechts je drei Spalten und unten eine
# Zeile Rahmenfarbe (head.py --fill), in der Mitte claude (C64-Run). Die feinen Linien zwischen
# den Feldern zieht Windows Terminal, wie tmux seine. Endet claude, schliessen sich alle Felder,
# und LOAD kehrt oben zur Shell zurueck, die wieder den ganzen Tab hat.
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
    & $cmd.Source @pre -c 'import sys; sys.exit(0)' 2>$null
    if ($LASTEXITCODE -eq 0) { return (@($cmd.Source) + $pre) -join '|' }
  }
  return ''
}

function global:C64-Project {
  $parts = (Get-Location).Path -split '[\\/]' | Where-Object { $_ }
  $hit = $parts | Where-Object { $_ -match '^\d{3}-' } | Select-Object -First 1
  if ($hit) { $hit } else { $parts[-1] }
}

# Claude Code im unteren Feld des Rahmens: Farben, Tabtitel mit der PID dieser PowerShell, und
# ~/.claude/retro-deck/<id>.pid, an der head.py oben sieht, dass die Sitzung laeuft.
function global:C64-Run([string]$look, [string]$id, [string[]]$pass) {
  C64-Colors $look
  $Host.UI.RawUI.WindowTitle = "C64 $(C64-Project) [$PID]"
  $dir = Join-Path $HOME '.claude\retro-deck'
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  $pidFile = Join-Path $dir "$id.pid"
  Set-Content -Path $pidFile -Value $PID -Encoding ASCII
  $env:C64_FRAME = $id
  $env:CLAUDE_CODE_DISABLE_TERMINAL_TITLE = '1'
  try { & claude --settings (Join-Path $C64Dir 'c64-settings.json') @pass }
  finally { Remove-Item $pidFile, (Join-Path $dir "$id.alive") -ErrorAction SilentlyContinue }
}

function global:LOAD {
  $look = 'screen'; $fast = $false; $flat = $false; $pass = @()
  foreach ($a in $args) {
    if ($a -is [array]) { $a = ($a -join ',') }          # LOAD "*",8,1 kommt als ein Array an
    switch -Regex ([string]$a) {
      '^\*(,8(,1)?)?$' { break }                         # der C64-Teil, verschluckt
      '^(?i)rahmen$' { $look = 'rahmen'; break }
      '^(?i)fast$' { $fast = $true; break }
      '^(?i)(flach|flat)$' { $flat = $true; break }
      default { $pass += [string]$a }
    }
  }
  $interactive = -not [Console]::IsOutputRedirected
  if ($interactive) { C64-Colors $look }
  if (-not (Test-Path variable:global:C64OldTitle)) { $global:C64OldTitle = $Host.UI.RawUI.WindowTitle }
  $Host.UI.RawUI.WindowTitle = "C64 $(C64-Project) [$PID]"

  $py = if ($interactive) { C64-Python } else { '' }
  if ($fast -or -not $py) {
    ''; 'SEARCHING FOR *'; Start-Sleep -Milliseconds 400
    'LOADING'; Start-Sleep -Milliseconds 400
    'READY.'; Start-Sleep -Milliseconds 300
  } else {
    $env:PYTHONUTF8 = '1'
    $exe, $pre = $py -split '\|'; $pre = @($pre | Where-Object { $_ })
    & $exe @pre (Join-Path $C64Dir 'trek.py')
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
  if (-not $flat -and $interactive -and $py -and $env:WT_SESSION -and $wt) {
    $id = 'wt-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
    $list = ($pass | ForEach-Object { "'" + ($_ -replace "'", "''") + "'" }) -join ','
    $run = ". '$((Join-Path $C64Dir 'load.ps1') -replace "'", "''")'; C64-Run '$look' '$id' @($list)"
    $b64 = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($run))
    $exe, $pre = $py -split '\|'; $pre = @($pre | Where-Object { $_ })
    # Groessen sind bei wt Anteile des geteilten Feldes, nicht Zeilen: aus der Tabgroesse gerechnet.
    $cols = [Math]::Max(40, $Host.UI.RawUI.WindowSize.Width)
    $rows = [Math]::Max(20, $Host.UI.RawUI.WindowSize.Height)
    $inv = [Globalization.CultureInfo]::InvariantCulture
    $share = { param($x) ([Math]::Min(0.98, [Math]::Max(0.01, $x))).ToString('0.000', $inv) }
    $cwd = (Get-Location).Path
    $fill = @($exe) + $pre + @((Join-Path $C64Dir 'head.py'), '--fill', $id)
    $claude = @('powershell.exe', '-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $b64)
    # Windows Terminal setzt ein neues Feld immer rechts oder unten an und lehnt ein zu schmales neues
    # Feld ab (so fehlten rechter und unterer Rand); das schmale Feld muss also das alte sein. Darum:
    # unter diesem Feld (9 Zeilen Kopfleiste) ein Randfeld; davon rechts ein zweites, das alte bleibt
    # als linker Rand; davon rechts ein drittes, das alte bleibt als rechter Rand, und swap-pane tauscht
    # beide; unter dem mittleren Claude Code, das alte oben bleibt als unterer Rand, swap-pane tauscht.
    # Der Fokus bleibt bei dem Feld, das getauscht wird, und landet so auf Claude Code.
    # Die neuen Felder nehmen das versteckte Profil "C64 Retro Deck Feld" aus dem Fragment (ohne
    # Innenabstand und Scrollbalken), damit die Anteile in Zeichen aufgehen. Dieses Feld oben behaelt
    # seinen Innenabstand (fast eine Zeile) und bekommt Platz fuer gut 10 Zeilen; der Rest ist Rahmenfarbe.
    $feld = @('-p', '{6b3c64c6-4c0d-4f8e-9a64-0c64de5c0de2}', '-d', $cwd)
    $top = 10.2
    $inner = $cols - 3.3
    $low = $rows - $top
    $plan = @('-w', '0',
      'split-pane', '-H', '-s', (& $share ($low / $rows))) + $feld + $fill + @(';',
      'split-pane', '-V', '-s', (& $share ($inner / $cols))) + $feld + $fill + @(';',
      'split-pane', '-V', '-s', (& $share (($inner - 3.4) / $inner))) + $feld + $fill + @(';',
      'swap-pane', 'left', ';',
      'split-pane', '-H', '-s', (& $share (($low - 1.5) / $low))) + $feld + $claude + @(';',
      'swap-pane', 'up')
    & $wt.Source @plan
    $env:C64_FRAME = $id
    $env:PYTHONUTF8 = '1'
    try { & $exe @pre (Join-Path $C64Dir 'head.py') }
    finally { Remove-Item env:C64_FRAME -ErrorAction SilentlyContinue; C64-Colors $look }
    $Host.UI.RawUI.WindowTitle = "C64 $(C64-Project) [$PID]"
    return
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
