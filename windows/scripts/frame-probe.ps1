# frame-probe.ps1 -- misst, wie Windows Terminal Felder teilt, tauscht und bei Groessenaenderung
# verteilt. Nur fuer die Entwicklung der Windows-Fassung (Rahmen von LOAD); aendert nichts.
#
# Aufruf in einem frischen Windows-Terminal-Tab, Fenster maximiert, waehrend des Laufs nichts
# anklicken (etwa 2 Minuten):
#   powershell -NoProfile -ExecutionPolicy Bypass -File frame-probe.ps1
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
$log = New-Object System.Collections.Generic.List[string]
function Say([string]$s) { $log.Add($s); Write-Host $s }

Say "frame-probe $(Get-Date -Format s)"
Say "wt: $wt  $((Get-Item $wt).VersionInfo.ProductVersion)"
Say "window: $($win.Current.ClassName)  $($win.Current.BoundingRectangle)"
Say "this pane: $($Host.UI.RawUI.WindowSize.Width) x $($Host.UI.RawUI.WindowSize.Height) cells"
$fragment = Join-Path $env:LOCALAPPDATA 'Microsoft\Windows Terminal\Fragments\cc-retro-deck\c64.json'
Say "fragment has Feld profile: $((Test-Path $fragment) -and ((Get-Content $fragment -Raw) -match 'Feld'))"

function Pane([string]$name, [int]$life) {
  $cmd = "[Console]::Title='$name'; Write-Host '$name'; Start-Sleep $life"
  @('powershell.exe', '-NoLogo', '-NoProfile', '-Command', $cmd)
}

function Dump([string]$label) {
  Start-Sleep -Milliseconds 1500
  Say "--- $label"
  $tabs = $win.FindAll($T::Descendants, (New-Object System.Windows.Automation.PropertyCondition($A::ControlTypeProperty, [System.Windows.Automation.ControlType]::TabItem)))
  foreach ($t in $tabs) {
    $sel = try { $t.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Current.IsSelected } catch { $false }
    if ($sel) { Say "  focused (tab title): $($t.Current.Name)" }
  }
  $panes = $win.FindAll($T::Descendants, (New-Object System.Windows.Automation.PropertyCondition($A::ClassNameProperty, 'TermControl')))
  if ($panes.Count -eq 0) {
    $names = $win.FindAll($T::Descendants, [System.Windows.Automation.Condition]::TrueCondition) |
      ForEach-Object { $_.Current.ClassName } | Sort-Object -Unique
    Say "  no TermControl; classes: $($names -join ', ')"
    return
  }
  foreach ($p in $panes) {
    $r = $p.Current.BoundingRectangle
    $text = try { $p.GetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern).DocumentRange.GetText(400) } catch { '' }
    $id = ([regex]::Match($text, '\bP\d+\b')).Value
    if (-not $id) { $id = 'this' }
    Say ("  {0,-5} x={1,5} y={2,5} w={3,5} h={4,5}  focus={5}" -f $id, [int]$r.X, [int]$r.Y, [int]$r.Width, [int]$r.Height, $p.Current.HasKeyboardFocus)
  }
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
  Wt (@('split-pane', '-V', '-s', $s) + $feld + (Pane "P$($s.Replace('0.', ''))" 6))
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

$log | Set-Content -Path $out -Encoding UTF8
Write-Host "written: $out"
