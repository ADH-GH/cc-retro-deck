@echo off
rem SYS 64738 fuer cmd: Farben, Titel und Prompt des Tabs zurueck, wie nach dem Einschalten.
rem cc-retro-deck-windows: angelegt von /deck setup apply, entfernt von /deck uninstall apply.
if not "%~1"=="64738" (
  echo ?SYNTAX  ERROR
  exit /b 1
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$e=[char]27; $b=[char]7; [Console]::Write($e+']104'+$b+$e+']110'+$b+$e+']111'+$b+$e+']112'+$b)"
title Eingabeaufforderung
prompt $P$G
cls
