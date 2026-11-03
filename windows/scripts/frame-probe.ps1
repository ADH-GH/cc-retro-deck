# frame-probe.ps1 -- misst, wie Windows Terminal Felder teilt, tauscht und bei Groessenaenderung
# verteilt. Nur fuer die Entwicklung der Windows-Fassung (Rahmen von LOAD); aendert nichts.
#
# Aufruf in einem frischen Windows-Terminal-Tab, Fenster maximiert, waehrend des Laufs nichts
# anklicken (etwa 2 Minuten):
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

Say "frame-probe v2 $(Get-Date -Format s)"
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

Dump 'start'

# A: wie LOAD in beta.6/7 -- alles in einem Aufruf, winzige neue Felder rechts und unten
Wt (@('split-pane', '-H', '-s', '0.85') + $feld + (Pane 'P1' 20) + @(';',
      'split-pane', '-V', '-s', '0.97') + $feld + (Pane 'P2' 20) + @(';',
      'split-pane', '-V', '-s', '0.015') + $feld + (Pane 'P3' 20) + @(';',
      'move-focus', 'left', ';',
      'split-pane', '-H', '-s', '0.03') + $feld + (Pane 'P4' 20) + @(';', 'move-focus', 'up'))
Dump 'A: one call, tiny new panes right (P3) and bottom (P4)'
Start-Sleep 22

# B: dieselben Schritte einzeln, mit Pause dazwischen
Wt (@('split-pane', '-H', '-s', '0.85') + $feld + (Pane 'P1' 30)); Start-Sleep 2
Wt (@('split-pane', '-V', '-s', '0.97') + $feld + (Pane 'P2' 30)); Start-Sleep 2
Wt (@('split-pane', '-V', '-s', '0.015') + $feld + (Pane 'P3' 30)); Dump 'B: after tiny right (P3), separate calls'
Wt @('move-focus', 'left'); Start-Sleep 1
Wt (@('split-pane', '-H', '-s', '0.03') + $feld + (Pane 'P4' 30)); Dump 'B: after tiny bottom (P4)'
Start-Sleep 20

# C: Groessen -- welcher kleinste Anteil wird noch angenommen (neues Feld rechts)
foreach ($s in '0.05', '0.03', '0.02', '0.015', '0.01') {
  Wt (@('split-pane', '-V', '-s', $s) + $feld + (Pane "S$($s.Replace('0.', ''))" 6))
  Dump "C: new pane right with -s $s"
  Start-Sleep 6
}

# D: swap-pane -- wandert die Groesse mit oder nur der Inhalt, und wohin geht der Fokus
Wt (@('split-pane', '-V', '-s', '0.8') + $feld + (Pane 'P5' 14)); Start-Sleep 2
Dump 'D: before swap (P5 new, right, 80%)'
Wt @('swap-pane', 'left')
Dump 'D: after swap-pane left'
Start-Sleep 12

# E: Groessenaenderung -- verteilt Windows Terminal Felder anteilig?
Wt (@('split-pane', '-H', '-s', '0.9') + $feld + (Pane 'P6' 20)); Start-Sleep 2
Dump 'E: maximized, P6 below (90%)'
Say '  >>> now restore the window to a small size (double-click the title bar) within 8 s'
Start-Sleep 8
Dump 'E: after making the window small'
Start-Sleep 12

Remove-Item $dir -Recurse -Force -ErrorAction SilentlyContinue
$log | Set-Content -Path $out -Encoding UTF8
Write-Host "written: $out"
