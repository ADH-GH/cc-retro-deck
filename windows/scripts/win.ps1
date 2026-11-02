# Retro Deck fuer Windows -- was die Hooks vom System brauchen, in einem Skript.
#
# Die Hooks rufen es mit powershell.exe -NoProfile -ExecutionPolicy Bypass -File win.ps1 <verb> ...
# Jede Antwort ist reiner Text auf stdout, eine Sache je Zeile.
#
#   procs <pid,pid,...>   lebende Prozesse: "pid tab", tab = PID der naechsten PowerShell (oder
#                         cmd) darueber; LOAD schreibt genau diese PID als [pid] in den Tabtitel
#   jump <tab>            den Windows-Terminal-Tab mit [tab] im Titel anwaehlen: ok | none
#   front                 der Tab im vorderen Windows-Terminal-Fenster: seine [pid], sonst nichts
#   tabs                  alle Tabtitel aller Windows-Terminal-Fenster, einer je Zeile
#   zoom <+|->            Schrift des vorderen Tabs (Strg+= / Strg+-): ok
#   head <datei> <bytes>  die ersten Bytes einer Datei als UTF-8-Text
#   rm <pfad>...          Dateien oder Ordner loeschen
#   policy                Ausfuehrungsrichtlinie fuer den aktuellen Benutzer
#   doctor                Bericht fuer die Abnahme (/deck doctor)
#
# Reines ASCII: Windows PowerShell 5.1 liest Dateien ohne BOM als ANSI.

param([Parameter(Position = 0)][string]$Verb = '', [Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest = @())
$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}

$Shells = @('powershell.exe', 'pwsh.exe', 'cmd.exe')

function Get-Procs([string]$list) {
  $want = @($list -split ',' | Where-Object { $_ -match '^\d+$' } | ForEach-Object { [int]$_ })
  if ($want.Count -eq 0) { return }
  $all = @{}
  foreach ($p in Get-CimInstance Win32_Process -Property ProcessId, ParentProcessId, Name) {
    $all[[int]$p.ProcessId] = $p
  }
  foreach ($id in $want) {
    if (-not $all.ContainsKey($id)) { continue }
    $tab = 0; $cur = $all[$id].ParentProcessId; $hops = 0
    while ($cur -and $all.ContainsKey([int]$cur) -and $hops -lt 8) {
      $p = $all[[int]$cur]
      if ($Shells -contains $p.Name.ToLower()) { $tab = [int]$cur; break }
      $cur = $p.ParentProcessId; $hops++
    }
    "$id $tab"
  }
}

function Use-UIA {
  Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
  Add-Type -Namespace C64 -Name W -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(System.IntPtr h);
[DllImport("user32.dll")] public static extern System.IntPtr GetForegroundWindow();
[DllImport("user32.dll")] public static extern bool ShowWindow(System.IntPtr h, int cmd);
[DllImport("user32.dll")] public static extern bool IsIconic(System.IntPtr h);
[DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, System.UIntPtr extra);
'@
}

function Get-WtWindows {
  $A = [System.Windows.Automation.AutomationElement]
  $cond = New-Object System.Windows.Automation.PropertyCondition($A::ClassNameProperty, 'CASCADIA_HOSTING_WINDOW_CLASS')
  $A::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children, $cond)
}

function Get-Tabs($win) {
  $A = [System.Windows.Automation.AutomationElement]
  $cond = New-Object System.Windows.Automation.PropertyCondition($A::ControlTypeProperty, [System.Windows.Automation.ControlType]::TabItem)
  $win.FindAll([System.Windows.Automation.TreeScope]::Descendants, $cond)
}

function Invoke-Jump([string]$tab) {
  if ($tab -notmatch '^\d+$' -or $tab -eq '0') { 'none'; return }
  Use-UIA
  foreach ($w in Get-WtWindows) {
    foreach ($t in Get-Tabs $w) {
      if ($t.Current.Name -notlike "*[[]$tab[]]*") { continue }
      $t.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select()
      $h = [System.IntPtr]$w.Current.NativeWindowHandle
      if ([C64.W]::IsIconic($h)) { [void][C64.W]::ShowWindow($h, 9) }
      # Windows gibt den Vordergrund nur her, wenn eine Taste gerade gedrueckt wurde: ein leeres Alt.
      [C64.W]::keybd_event(0x12, 0, 0, [System.UIntPtr]::Zero)
      [C64.W]::keybd_event(0x12, 0, 2, [System.UIntPtr]::Zero)
      [void][C64.W]::SetForegroundWindow($h)
      'ok'; return
    }
  }
  'none'
}

function Get-Front {
  Use-UIA
  $fg = [C64.W]::GetForegroundWindow()
  foreach ($w in Get-WtWindows) {
    if ([System.IntPtr]$w.Current.NativeWindowHandle -ne $fg) { continue }
    foreach ($t in Get-Tabs $w) {
      $sel = $t.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern)
      if ($sel.Current.IsSelected -and $t.Current.Name -match '\[(\d+)\]') { $Matches[1]; return }
    }
  }
}

function Get-TabNames {
  Use-UIA
  foreach ($w in Get-WtWindows) { foreach ($t in Get-Tabs $w) { $t.Current.Name } }
}

function Invoke-Zoom([string]$dir) {
  Add-Type -AssemblyName System.Windows.Forms
  [System.Windows.Forms.SendKeys]::SendWait($(if ($dir -eq '-') { '^-' } else { '^=' }))
  'ok'
}

function Get-Head([string]$path, [int]$bytes) {
  $fs = [IO.File]::Open($path, 'Open', 'Read', 'ReadWrite')
  try {
    $buf = New-Object byte[] $bytes
    $n = $fs.Read($buf, 0, $bytes)
    [Console]::Out.Write([Text.Encoding]::UTF8.GetString($buf, 0, $n))
  } finally { $fs.Close() }
}

function Get-Doctor {
  function Line($k, $v) { '{0,-24} {1}' -f $k, $v }
  Line 'windows' ([Environment]::OSVersion.VersionString)
  try { Line 'release' ((Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').DisplayVersion) } catch {}
  Line 'helper-powershell' "$($PSVersionTable.PSEdition) $($PSVersionTable.PSVersion)"
  Line 'policy-currentuser' (Get-ExecutionPolicy -Scope CurrentUser)
  Line 'policy-effective' (Get-ExecutionPolicy)
  try {
    $wt = Get-AppxPackage -Name 'Microsoft.WindowsTerminal*' | Select-Object -First 1
    Line 'windows-terminal' $(if ($wt) { "$($wt.Name) $($wt.Version)" } else { 'not found as an app package' })
  } catch { Line 'windows-terminal' "query failed: $($_.Exception.Message)" }
  Line 'wt.exe' $(if (Get-Command wt.exe -ErrorAction SilentlyContinue) { 'found' } else { 'MISSING' })
  Line 'pwsh.exe' $(if (Get-Command pwsh.exe -ErrorAction SilentlyContinue) { 'found' } else { 'not installed (Windows PowerShell 5.1 only)' })
  foreach ($n in 'py', 'python', 'python3') {
    $c = Get-Command $n -ErrorAction SilentlyContinue
    if (-not $c) { Line "python:$n" 'missing'; continue }
    $v = try { (& $c.Source $(if ($n -eq 'py') { '-3' }) --version 2>&1 | Out-String).Trim() } catch { 'does not start' }
    Line "python:$n" "$(if ($v) { $v } else { '(no output: Microsoft Store stub?)' })  [$($c.Source)]"
  }
  try {
    Use-UIA
    $wins = @(Get-WtWindows)
    Line 'wt-windows' $wins.Count
    $names = foreach ($w in $wins) { foreach ($t in Get-Tabs $w) { $t.Current.Name } }
    Line 'wt-tabs' (($names | ForEach-Object { "<$_>" }) -join ' ')
    Line 'front-tab' "[$(Get-Front)]"
  } catch { Line 'ui-automation' "FAILED: $($_.Exception.Message)" }
}

switch ($Verb) {
  'procs'  { Get-Procs ($Rest -join ',') }
  'jump'   { Invoke-Jump ($Rest | Select-Object -First 1) }
  'front'  { Get-Front }
  'tabs'   { Get-TabNames }
  'zoom'   { Invoke-Zoom ($Rest | Select-Object -First 1) }
  'head'   { Get-Head $Rest[0] ([int]$Rest[1]) }
  'rm'     { foreach ($p in $Rest) { if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Recurse -Force } } }
  'policy' { Get-ExecutionPolicy -Scope CurrentUser; Get-ExecutionPolicy }
  'doctor' { Get-Doctor }
  default  { Write-Error "unknown verb: $Verb"; exit 2 }
}
