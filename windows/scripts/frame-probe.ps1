# frame-probe.ps1 -- misst, wie Windows Terminal Felder teilt, tauscht und bei Groessenaenderung
# verteilt. Nur fuer die Entwicklung der Windows-Fassung (Rahmen von LOAD); aendert nichts.
#
# Aufruf in einem frischen Windows-Terminal-Tab, Fenster maximiert, waehrend des Laufs nichts
# anklicken (etwa 2 Minuten, gegen Ende einmal verkleinern und wieder maximieren):
#   powershell -NoProfile -ExecutionPolicy Bypass -File frame-probe.ps1     (auch aus cmd)
# Ergebnis: frame-probe.txt im aktuellen Ordner. Jedes Testfeld zeigt seinen Namen (P1, P2 ...)
# und schliesst sich nach einer Weile selbst.

$ErrorActionPreference = 'Continue'
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
Add-Type -Namespace Probe -Name W -MemberDefinition @'
[DllImport("user32.dll")] public static extern System.IntPtr GetForegroundWindow();
'@
$A = [System.Windows.Automation.AutomationElement]
$T = [System.Windows.Automation.TreeScope]
$out = Join-Path (Get-Location).Path 'frame-probe.txt'
$wt = (Get-Command wt.exe).Source
$win = $A::FromHandle([Probe.W]::GetForegroundWindow())
$dir = Join-Path $env:TEMP 'c64-frame-probe'
Remove-Item $dir -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$log = New-Object System.Collections.Generic.List[string]
function Say([string]$s) { $log.Add($s); Write-Host $s }

Say "frame-probe v3 $(Get-Date -Format s)"
Say "window: $($win.Current.ClassName)  $($win.Current.BoundingRectangle)"
Say "this pane: $($Host.UI.RawUI.WindowSize.Width) x $($Host.UI.RawUI.WindowSize.Height) cells"
$fragment = Join-Path $env:LOCALAPPDATA 'Microsoft\Windows Terminal\Fragments\cc-retro-deck\c64.json'
Say "fragment has Feld profile: $((Test-Path $fragment) -and ((Get-Content $fragment -Raw) -match 'Feld'))"

# Jedes Testfeld schreibt alle 0,3 s seinen Namen und seine Groesse in Zellen in eine Datei und
# setzt den Titel auf seinen Namen (der Tabtitel zeigt so das Feld mit dem Fokus). Als
# -EncodedCommand, weil wt.exe ein Semikolon im Befehl als eigenen Unterbefehl liest.
function Pane([string]$name, [int]$life) {
  $f = Join-Path $dir "$name.txt"
  $code = "[Console]::Title='$name'; Write-Host '$name'; `$end=(Get-Date).AddSeconds($life); " +
          "while ((Get-Date) -lt `$end) { `$s=`$Host.UI.RawUI.WindowSize; " +
          "Set-Content -Path '$f' -Value ('{0} x {1}' -f `$s.Width, `$s.Height); Start-Sleep -Milliseconds 300 }; " +
          "Remove-Item '$f' -ErrorAction SilentlyContinue"
  @('powershell.exe', '-NoLogo', '-NoProfile', '-EncodedCommand', [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($code)))
}

function Dump([string]$label) {
  Start-Sleep -Milliseconds 1500
  Say "--- $label"
  $tabs = $win.FindAll($T::Descendants, (New-Object System.Windows.Automation.PropertyCondition($A::ControlTypeProperty, [System.Windows.Automation.ControlType]::TabItem)))
  foreach ($t in $tabs) {
    $sel = try { $t.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Current.IsSelected } catch { $false }
    if ($sel) { Say "  focus (tab title): $($t.Current.Name)" }
  }
  Say ("  this  {0} x {1}" -f $Host.UI.RawUI.WindowSize.Width, $Host.UI.RawUI.WindowSize.Height)
  Get-ChildItem $dir -Filter '*.txt' | Where-Object { $_.LastWriteTime -gt (Get-Date).AddSeconds(-2) } | Sort-Object Name |
    ForEach-Object { Say ("  {0,-5} {1}" -f $_.BaseName, (Get-Content $_.FullName -Raw).Trim()) }
}

function Wt([string[]]$a) { & $wt @(@('-w', '0') + $a) }
$feld = @('-p', '{6b3c64c6-4c0d-4f8e-9a64-0c64de5c0de2}')

[Console]::Title = 'P0'
Dump 'start'
# Jeder Test beginnt im Feld 0, dem dieses Skripts (frischer Tab: Feld-Kennung 0); schliessen sich
# Testfelder, hat sonst kein Feld mehr den Fokus, und wt teilt nirgends.
function Home { Wt @('focus-pane', '-t', '0'); Start-Sleep -Milliseconds 800 }

# D: swap-pane -- wandert die Groesse mit oder nur der Inhalt, und wohin geht der Fokus
Home
Wt (@('split-pane', '-V', '-s', '0.8') + $feld + (Pane 'D1' 8)); Dump 'D: D1 new, right, 80%'
Wt @('swap-pane', 'left'); Dump 'D: after swap-pane left (focus was D1)'
Wt @('move-focus', 'right'); Dump 'D: after move-focus right'
Start-Sleep 9
Dump 'D: D1 ended (does its pane close, is P0 whole again?)'

# G: kleinste Hoehe eines neuen Feldes unten, mit Pause angelegt
foreach ($s in '0.045', '0.035', '0.025') {
  Home
  Wt (@('split-pane', '-H', '-s', $s) + $feld + (Pane "G$($s.Replace('0.', ''))" 5))
  Dump "G: new pane below with -s $s"
  Start-Sleep 5
}

# H: Kopf per Tausch -- unten ein grosses neues Feld, dann swap-pane up: landet P0 unten gross?
Home
Wt (@('split-pane', '-H', '-s', '0.86') + $feld + (Pane 'H1' 10)); Start-Sleep 1
Wt @('swap-pane', 'up'); Dump 'H: after split below 86% and swap-pane up'
Wt @('move-focus', 'down'); Dump 'H: after move-focus down'
Start-Sleep 9

# E: Groessenaenderung -- verteilt Windows Terminal anteilig?
Home
Wt (@('split-pane', '-V', '-s', '0.97') + $feld + (Pane 'E1' 40)); Start-Sleep 2
Wt (@('split-pane', '-H', '-s', '0.9') + $feld + (Pane 'E2' 38)); Start-Sleep 1
Dump 'E: maximized'
Say '  >>> make the window small now (double-click the title bar), within 8 s'
Write-Host '>>> JETZT Fenster verkleinern (Doppelklick auf die Titelleiste)' -ForegroundColor Yellow
Start-Sleep 8
Dump 'E: small'
Write-Host '>>> JETZT wieder maximieren (Doppelklick auf die Titelleiste)' -ForegroundColor Yellow
Start-Sleep 8
Dump 'E: maximized again'
Start-Sleep 22

Remove-Item $dir -Recurse -Force -ErrorAction SilentlyContinue
$log | Set-Content -Path $out -Encoding UTF8
Write-Host "written: $out"
