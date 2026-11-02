# Retro Deck fuer Windows -- Pruefskript.
#
# Klopft vor dem Bau die Stellen ab, an denen die Windows-Fassung scheitern koennte, und
# schreibt das Ergebnis auf den Desktop (retro-deck-probe.txt). Aendert nichts dauerhaft.
#
#   In Windows Terminal, in einem PowerShell-Tab:
#   powershell -ExecutionPolicy Bypass -File .\probe.ps1
#   (oder pwsh statt powershell; am besten beide einmal)
#
# Einige Pruefungen fragen, was auf dem Bildschirm zu sehen ist: mit j oder n antworten.
# Die Datei ist bewusst reines ASCII: Windows PowerShell 5.1 liest Dateien ohne BOM als ANSI.

$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
$E = [char]27
$BEL = [char]7
$out = New-Object System.Collections.Generic.List[string]
function Note($key, $value) { $line = '{0,-22} {1}' -f $key, $value; $out.Add($line); Write-Host $line }
function Ask($q) { $a = Read-Host "$q [j/n]"; if ($a -match '^[jJyY]') { 'ja' } else { 'nein' } }

Write-Host ''
Write-Host 'Retro Deck -- Pruefung fuer Windows' -ForegroundColor Cyan
Write-Host ''

# 1. System
Note 'windows' ([Environment]::OSVersion.VersionString)
try { Note 'build' ((Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').DisplayVersion) } catch {}
Note 'powershell' ("$($PSVersionTable.PSEdition) $($PSVersionTable.PSVersion)")
Note 'architektur' $env:PROCESSOR_ARCHITECTURE
Note 'profil-datei' $PROFILE
Note 'profil-existiert' (Test-Path $PROFILE)
Note 'execution-policy' (Get-ExecutionPolicy)

# 2. Windows Terminal
Note 'WT_SESSION' $(if ($env:WT_SESSION) { $env:WT_SESSION } else { 'FEHLT (nicht in Windows Terminal?)' })
try {
  $wt = Get-AppxPackage -Name 'Microsoft.WindowsTerminal*' -ErrorAction Stop | Select-Object -First 1
  Note 'windows-terminal' $(if ($wt) { "$($wt.Name) $($wt.Version)" } else { 'nicht als App-Paket gefunden' })
} catch { Note 'windows-terminal' "Abfrage scheiterte: $($_.Exception.Message)" }
$wtexe = Get-Command wt.exe -ErrorAction SilentlyContinue
Note 'wt.exe' $(if ($wtexe) { $wtexe.Source } else { 'FEHLT' })

# 3. Fragment-Ordner beschreibbar (Profil "C64" ohne Eingriff in settings.json)
$frag = Join-Path $env:LOCALAPPDATA 'Microsoft\Windows Terminal\Fragments\cc-retro-deck-probe'
try {
  New-Item -ItemType Directory -Force -Path $frag | Out-Null
  $f = Join-Path $frag 'probe.json'
  Set-Content -Path $f -Value '{"schemes":[]}' -Encoding UTF8
  Remove-Item -Recurse -Force $frag
  Note 'fragment-ordner' 'beschreibbar'
} catch { Note 'fragment-ordner' "FEHLER: $($_.Exception.Message)" }

# 4. Prozesskette: wer ist Elternteil dieser Shell?
try {
  $chain = @(); $id = $PID
  for ($i = 0; $i -lt 6 -and $id; $i++) {
    $p = Get-CimInstance Win32_Process -Filter "ProcessId=$id" -ErrorAction Stop
    if (-not $p) { break }
    $chain += "$($p.Name)($id)"; $id = $p.ParentProcessId
  }
  Note 'prozesskette' ($chain -join ' <- ')
} catch { Note 'prozesskette' "FEHLER: $($_.Exception.Message)" }

# 5. Python (Einschaltbild trek.py / boot.py). Der Store-Platzhalter in WindowsApps zaehlt nicht.
foreach ($n in 'py', 'python', 'python3') {
  $c = Get-Command $n -ErrorAction SilentlyContinue
  if (-not $c) { Note "python:$n" 'fehlt'; continue }
  $v = try { (& $c.Source --version 2>&1 | Out-String).Trim() } catch { 'startet nicht' }
  if (-not $v) { $v = '(keine Ausgabe -- Store-Platzhalter?)' }
  Note "python:$n" "$v  [$($c.Source)]"
}

# 6. Claude Code und Git Bash
$cl = Get-Command claude -ErrorAction SilentlyContinue
Note 'claude' $(if ($cl) { "$((& $cl.Source --version 2>&1 | Out-String).Trim())  [$($cl.Source)]" } else { 'FEHLT' })
$git = Get-Command git -ErrorAction SilentlyContinue
Note 'git' $(if ($git) { $git.Source } else { 'fehlt' })
Note 'CLAUDE_CODE_GIT_BASH' $(if ($env:CLAUDE_CODE_GIT_BASH_PATH) { $env:CLAUDE_CODE_GIT_BASH_PATH } else { '(nicht gesetzt)' })

# 7. LOAD "*",8,1 in PowerShell: wie kommen die Argumente an?
function LOAD { $script:loadArgs = $args }
LOAD "*",8,1
$desc = ($script:loadArgs | ForEach-Object { if ($_ -is [array]) { 'Array(' + ($_ -join ',') + ')' } else { "$_" } }) -join ' | '
Note 'LOAD-argumente' "$($script:loadArgs.Count): $desc"

# 8. 24-Bit-Farbe und Viertelblock-Zeichen (Krabbe, Enterprise)
$q = -join ([char]0x2596, [char]0x2597, [char]0x2598, [char]0x259D, [char]0x259A, [char]0x259E, [char]0x2588, [char]0x2580, [char]0x2584)
Write-Host ''
Write-Host "$E[48;2;64;49;141m$E[38;2;134;122;222m   $q  C64 BLAU / HELLBLAU  $q   $E[0m"
Write-Host "$E[48;2;64;49;141m$E[38;2;218;86;80m   $q  ROT AUF BLAU          $q   $E[0m"
Note 'farbe-24bit' (Ask 'Siehst du zwei Zeilen auf violett-blauem Grund, Schrift hellblau und rot, ohne Kaestchen oder Fragezeichen?')

# 9. Farben des ganzen Tabs per OSC umstellen (wie die Linux-Fassung)
Write-Host -NoNewline "$E]11;rgb:40/31/8d$BEL$E]10;rgb:86/7a/de$BEL"
Write-Host 'Der Tab sollte jetzt blau mit hellblauer Schrift sein.'
$osc = Ask 'Ist der GANZE Tab blau geworden?'
Write-Host -NoNewline "$E]111$BEL$E]110$BEL"
$back = Ask 'Und jetzt wieder in den alten Farben?'
Note 'osc-farben' "umstellen=$osc zurueck=$back"

# 10. Tabtitel setzen und den eigenen Tab per UI Automation finden und anwaehlen
$tag = 'C64-PROBE-' + (Get-Random -Maximum 99999)
Write-Host -NoNewline "$E]0;$tag$BEL"
$Host.UI.RawUI.WindowTitle = $tag
Start-Sleep -Milliseconds 600
try {
  Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes -ErrorAction Stop
  $A = [System.Windows.Automation.AutomationElement]
  $cond = New-Object System.Windows.Automation.PropertyCondition($A::ClassNameProperty, 'CASCADIA_HOSTING_WINDOW_CLASS')
  $wins = $A::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children, $cond)
  Note 'wt-fenster' $wins.Count
  $tabCond = New-Object System.Windows.Automation.PropertyCondition($A::ControlTypeProperty, [System.Windows.Automation.ControlType]::TabItem)
  $mine = $null; $names = @()
  foreach ($w in $wins) {
    foreach ($t in $w.FindAll([System.Windows.Automation.TreeScope]::Descendants, $tabCond)) {
      $names += $t.Current.Name
      if ($t.Current.Name -like "*$tag*") { $mine = $t; $mineWin = $w }
    }
  }
  Note 'wt-tabs' ($names -join ' | ')
  Note 'eigener-tab' $(if ($mine) { 'gefunden' } else { 'NICHT gefunden' })
  if ($mine) {
    Write-Host ''
    Write-Host 'Sprungtest: Klicke in den naechsten 8 Sekunden auf einen ANDEREN Tab (vorher einen zweiten oeffnen, Strg+Umschalt+T).' -ForegroundColor Yellow
    Start-Sleep -Seconds 8
    $sel = $mine.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern)
    $sel.Select()
    try {
      Add-Type -Namespace W -Name U -MemberDefinition '[DllImport("user32.dll")] public static extern bool SetForegroundWindow(System.IntPtr h);' -ErrorAction Stop
      [void][W.U]::SetForegroundWindow([System.IntPtr]$mineWin.Current.NativeWindowHandle)
    } catch {}
    Start-Sleep -Milliseconds 500
    Note 'tab-sprung' (Ask 'Bist du jetzt wieder automatisch in DIESEM Tab gelandet?')
  }
} catch { Note 'ui-automation' "FEHLER: $($_.Exception.Message)" }

# 11. Neuen Tab per wt.exe oeffnen (fuer /deck restore)
if ($wtexe) {
  & $wtexe.Source -w 0 new-tab --title 'C64-PROBE-NEU' -d $HOME powershell -NoExit -Command "Write-Host 'Neuer Tab aus dem Pruefskript. Kann geschlossen werden.'"
  Start-Sleep -Seconds 2
  Note 'wt-neuer-tab' (Ask 'Hat sich im SELBEN Fenster ein neuer Tab "C64-PROBE-NEU" geoeffnet?')
}

# Ergebnis
$file = Join-Path ([Environment]::GetFolderPath('Desktop')) 'retro-deck-probe.txt'
$out.Insert(0, "Retro Deck probe $(Get-Date -Format s)")
Set-Content -Path $file -Value $out -Encoding UTF8
Write-Host ''
Write-Host "Fertig. Ergebnis: $file -- bitte an Claude schicken (Inhalt einfuegen genuegt)." -ForegroundColor Cyan
