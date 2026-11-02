# LOAD "*",8,1  --  startet Claude Code, wie ein C64 ein Programm von Diskette laedt (Windows, PowerShell).
#
# Eingebunden ueber /deck setup: es kopiert diese Dateien nach ~\.claude\retro-deck\shell\ und
# traegt in das PowerShell-Profil ($PROFILE, fuer Windows PowerShell und PowerShell 7) einen
# markierten Block ein, der sie laedt. /deck uninstall nimmt beides zurueck.
#
#   LOAD "*",8,1            Tab in C64-Farben, Einschaltbildschirm: der Star-Trek-Tribut (trek.py),
#                           bei zu kleinem Fenster die tanzende Krabbe (boot.py), dann claude
#   LOAD "*",8,1 --resume   alles nach dem C64-Teil geht an claude weiter
#   LOAD "*",8,1 RAHMEN     hellblauer Grund statt dunkelblauem Bildschirm
#   LOAD "*",8,1 FAST       ohne Einschaltbildschirm, nur die drei Zeilen
#   RUN                     nur claude, ohne alles
#   SYS 64738               Reset: Farben, Titel und Prompt des Tabs wie vorher
#
# Einen tmux-Rahmen wie auf dem Mac gibt es hier nicht: Kopfleiste und Banner zeichnet der Mod
# selbst ueber der Eingabe. Die Farben setzt LOAD per Steuersequenz (OSC 4/10/11/12) nur in
# diesem Tab; Windows Terminal versteht das.
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

function global:LOAD {
  $look = 'screen'; $fast = $false; $pass = @()
  foreach ($a in $args) {
    if ($a -is [array]) { $a = ($a -join ',') }          # LOAD "*",8,1 kommt als ein Array an
    switch -Regex ([string]$a) {
      '^\*(,8(,1)?)?$' { break }                         # der C64-Teil, verschluckt
      '^(?i)rahmen$' { $look = 'rahmen'; break }
      '^(?i)fast$' { $fast = $true; break }
      '^(?i)(flach|flat)$' { break }                     # gibt es hier nicht: nie ein Rahmen
      default { $pass += [string]$a }
    }
  }
  $interactive = -not [Console]::IsOutputRedirected
  if ($interactive) { C64-Colors $look }
  if (-not (Test-Path variable:global:C64OldTitle)) { $global:C64OldTitle = $Host.UI.RawUI.WindowTitle }
  $Host.UI.RawUI.WindowTitle = "C64 $(C64-Project) [$PID]"

  $py = if ($fast -or -not $interactive) { '' } else { C64-Python }
  if (-not $py) {
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
