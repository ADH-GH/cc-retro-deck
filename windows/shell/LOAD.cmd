@echo off
rem LOAD "*",8,1 fuer die Eingabeaufforderung (cmd) und fuer PowerShell ohne Profil (Richtlinie
rem "Restricted"). cmd kann weder Farben setzen noch die Tafel mit dem Tab verbinden: das macht
rem load.ps1 in einer PowerShell, die nur dafuer Skripte ausfuehren darf. Endet Claude Code, ist
rem man zurueck in cmd, mit READY. als Prompt.
rem cc-retro-deck-windows: angelegt von /deck setup apply, entfernt von /deck uninstall apply.
setlocal EnableDelayedExpansion
set "rest="
:next
if "%~1"=="" goto run
set "a=%~1"
rem Der C64-Teil kommt in cmd als "*" 8 1 an, aus PowerShell als * 8 1: verschluckt.
if not "!a!"=="*" if not "!a!"=="8" if not "!a!"=="1" if not "!a!"=="*,8,1" set "rest=!rest! '!a!'"
shift
goto next
:run
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command ". (Join-Path $HOME '.claude\retro-deck\shell\load.ps1'); LOAD '*,8,1'!rest!"
endlocal & prompt $_$E[94mREADY.$E[0m$_
