#!/usr/bin/env python3
"""Erzeugt zwei Terminal.app-Profile in C64-Farben (Colodore-Palette) als .terminal-Dateien.

  C64         dunkelblauer Bildschirm, hellblaue Schrift: der READY.-Bildschirm
  C64 Rahmen  hellblauer Grund, weisse Schrift: die Rahmenfarbe als Grund

Import: `open C64.terminal` (Terminal legt das Profil unter Einstellungen > Profile ab).
Die 16 ANSI-Farben sind auf die 16 VIC-II-Farben gelegt; damit zeichnet auch Claude Code
mit `/theme dark-ansi` in C64-Farben. Farben ab 16 (256er-Wuerfel) sind nicht einstellbar.
ANSI 8 (hellschwarz) traegt die Grundfarbe des Profils: Claude Code malt damit den Grund
hinter getippten Prompts, Tafeln und deren Rahmenlinien, und grau passt nicht ins Bild.
"""
import pathlib
import plistlib

C64 = dict(black='#000000', white='#FFFFFF', red='#813338', cyan='#75CEC8', purple='#8E3C97',
           green='#56AC4D', blue='#2E2C9B', yellow='#EDF171', orange='#8E5029', brown='#553800',
           lightRed='#C46C71', darkGrey='#4A4A4A', grey='#7B7B7B', lightGreen='#A9FF9F',
           lightBlue='#706DEB', lightGrey='#B2B2B2')


def nscolor(hexcol, alpha=None):
    """Ein NSColor als NSKeyedArchiver-Blob, so wie Terminal.app ihn selbst ablegt."""
    r, g, b = (int(hexcol[i:i + 2], 16) / 255 for i in (1, 3, 5))
    rgb = f'{r:.10g} {g:.10g} {b:.10g}' + (f' {alpha}' if alpha is not None else '')
    arch = {'$version': 100000, '$archiver': 'NSKeyedArchiver', '$top': {'root': plistlib.UID(1)},
            '$objects': ['$null',
                         {'NSRGB': rgb.encode() + b'\x00', 'NSColorSpace': 1, '$class': plistlib.UID(2)},
                         {'$classname': 'NSColor', '$classes': ['NSColor', 'NSObject']}]}
    return plistlib.dumps(arch, fmt=plistlib.FMT_BINARY)


# Schrift des C64-Profils heller als das VIC-Hellblau: Claude Code zeichnet Platzhalter und
# Nebentext mit SGR 2 (dim), und Terminal.app mischt das halb mit dem Grund. Mit #706DEB war
# der Platzhalter auf Blau kaum lesbar; mit #A3A1FF steht er so hell wie vorher der Text (ADH).
TEXT = '#A3A1FF'

ANSI = dict(Black=C64['black'], Red=C64['red'], Green=C64['green'], Yellow=C64['yellow'],
            Blue=C64['lightBlue'], Magenta=C64['purple'], Cyan=C64['cyan'], White=C64['lightGrey'],
            BrightBlack=C64['grey'], BrightRed=C64['lightRed'], BrightGreen=C64['lightGreen'],
            BrightYellow=C64['yellow'], BrightBlue=C64['lightBlue'], BrightMagenta=C64['purple'],
            BrightCyan=C64['cyan'], BrightWhite=C64['white'])


def profile(name, bg, fg, bold, cursor, selection):
    # ANSI 8 (bright black) is what Claude Code paints behind a typed prompt, a pane's body
    # and its frame lines; as grey it breaks the C64 picture, so it takes the ground color.
    p = {'name': name, 'type': 'Window Settings', 'ProfileCurrentVersion': 2.09,
         'BackgroundColor': nscolor(bg), 'TextColor': nscolor(fg), 'TextBoldColor': nscolor(bold),
         'CursorColor': nscolor(cursor), 'SelectionColor': nscolor(selection, 0.6),
         'CursorType': 0, 'CursorBlink': True, 'FontAntialias': True, 'useOptionAsMetaKey': True,
         'ShowActiveProcessArgumentsInTitle': True, 'ShowShellCommandInTitle': True,
         'columnCount': 140, 'rowCount': 42}
    for k, v in ANSI.items():
        p[f'ANSI{k}Color'] = nscolor(v)
    p['ANSIBrightBlackColor'] = nscolor(bg)
    return p


here = pathlib.Path(__file__).parent
for name, args in {
    'C64': (C64['blue'], TEXT, C64['white'], C64['lightBlue'], C64['grey']),
    'C64 Rahmen': (C64['lightBlue'], C64['white'], C64['yellow'], C64['white'], C64['blue']),
}.items():
    with open(here / f'{name}.terminal', 'wb') as f:
        plistlib.dump(profile(name, *args), f, fmt=plistlib.FMT_XML)
    print('geschrieben:', here / f'{name}.terminal')
