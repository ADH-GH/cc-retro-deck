# Claude Code Retro Deck

[English](README.en.md) · **Deutsch**

Ein Commodore-64-Look für Claude Code: C64-Farben in der Fußzeile, eine Tafel aller laufenden
Sitzungen und `LOAD "*",8,1` mit Einschaltbildschirm und zwei tanzenden Krabben Hand in Hand.

*Inoffizieller Community-Mod, weder von Anthropic noch mit Anthropic. „Claude" und die
Claude-Code-Krabbe gehören Anthropic. Produktnamen in der Kopfleiste gehören ihren Inhabern;
eine Verbindung oder Empfehlung ist damit nicht gemeint.*

## Fassung wählen

| System | Plugin | Terminal |
|---|---|---|
| macOS | `cc-retro-deck-mac` | Terminal.app |
| Linux (Zielsystem: Mint 22) | `cc-retro-deck-linux` | GNOME Terminal |
| Windows 10/11 | `cc-retro-deck-windows` | Windows Terminal (cmd oder PowerShell) |

Genau eine installieren, die für das eigene System. Claude Code kann sie nicht selbst wählen.

## Zwei Arten zu starten

| | Man tippt | Man bekommt |
|---|---|---|
| **Standard** | `claude` | Claude Code wie gewohnt, dazu die C64-Fußzeile und die Tafel (`/deck`) |
| **Retro Deck** | `LOAD "*",8,1` | C64-Farben im Terminal, den Einschaltbildschirm, dann Claude Code im C64-Rahmen mit Krabben-Kopfleiste und Banner |

Standard geht direkt nach der Installation. Retro Deck braucht einmal die Einrichtung (Schritt 3).

## Installieren

**Voraussetzungen.** Standard braucht nur Claude Code ab 2.1.312. Retro Deck braucht dazu
`tmux` und `python3` (Windows: Windows Terminal und Python, kein tmux — siehe
[windows/README.md](windows/README.md), englisch):

| | prüfen | macOS | Linux (Mint/Ubuntu) |
|---|---|---|---|
| tmux | `tmux -V` | `brew install tmux` (Homebrew: [brew.sh](https://brew.sh)) | `sudo apt install tmux` |
| python3 | `python3 --version` | `xcode-select --install` (Command Line Tools) | vorinstalliert; sonst `sudo apt install python3` |

`/deck setup` prüft beides und nennt den Installationsbefehl, wenn etwas fehlt; selbst
installiert es nichts. Ohne tmux startet `LOAD` Claude Code ohne Rahmen, ohne python3 mit drei
Zeilen statt Einschaltbildschirm.

**1. Marktplatz hinzufügen** (in der Shell, oder als `/plugin …` in Claude Code):

```bash
claude plugin marketplace add ADH-GH/cc-retro-deck
```

**2. Die eigene Fassung installieren:**

```bash
claude plugin install cc-retro-deck-mac@cc-retro-deck      # macOS
claude plugin install cc-retro-deck-linux@cc-retro-deck    # Linux
claude plugin install cc-retro-deck-windows@cc-retro-deck  # Windows
```

Claude Code meldet womöglich, dass die Optionen des Plugins nicht gesetzt sind: sie sind
optional, es gelten die Vorgaben (später unter `/plugin` änderbar). `claude` starten — damit
läuft **Standard**.

**3. Für Retro Deck: einrichten**, in Claude Code:

```
/deck setup          zeigt, was es ändern würde, ändert nichts
/deck setup apply    führt es aus
```

Was `apply` tut:

- kopiert die Shell-Skripte nach `~/.claude/retro-deck/shell/` (bei jedem Start aktuell gehalten)
- schreibt einen markierten Block in `~/.zshrc` (macOS) bzw. `~/.bashrc` (Linux), zwischen
  `# >>> cc-retro-deck >>>` und `# <<< cc-retro-deck <<<`; er definiert `LOAD` und `RUN`
- nur macOS: importiert die Terminal-Profile „C64" und „C64 Rahmen"
- meldet, wenn `tmux` fehlt
- Windows: `LOAD.cmd` und `SYS.cmd` im PATH, ein Block in den PowerShell-Profilen und das
  Windows-Terminal-Profil „C64 Retro Deck"; Einzelheiten in [windows/README.md](windows/README.md)

Einen neuen Tab öffnen und `LOAD "*",8,1` tippen.

Zwei Gastdisketten: `LOAD "ERIC",8,1` und `LOAD "BERTRAND",8,1` laden New York statt der
Enterprise: Manhattan bei Nacht, darüber ein Workflow im n8n-Stil, der durchläuft, und eine
Begrüßung mit Namen. Gemacht für Eric, n8n Ambassador NYC, und Bertrand.

Sitzungen aus `LOAD` zeichnen auch Claude Code selbst in C64-Farben (Theme `dark-ansi`, nur
für diese Sitzung). Ein schlichtes `claude` behält das eigene Theme.

## Bedienen

| Befehl | Tut |
|---|---|
| `/deck` | Tafel öffnen; Tab-Nummer plus Enter oder ein Klick springt dorthin |
| `/deck intro` | die Krabben tanzen lassen |
| `/deck zoom +` / `-` | Schrift dieses Tabs einen Punkt größer / kleiner (macOS; auch `(+)` `(-)` in der Fußzeile) |
| `/deck restore` | Sitzungen wieder öffnen, die ein geschlossenes Terminal mitgenommen hat |
| `/deck update` | macOS: zeigt, welche Tabs ein älteres Claude Code laufen haben; `/deck update go` führt `claude update` aus und startet jeden Tab an Ort und Stelle mit seinem Verlauf neu, diesen zuletzt |
| `/deck theme c64\|amiga\|cga` | Palette für diese Sitzung |
| `/pure HELP` | C64-BASIC-Befehle als Tafel-Handlungen |
| `/emul` | ein Commodore 64 in einer Tafel |

Einstellungen (Palette, Auto-Umschalten, Tafel beim Start, Intro): `/plugin` → das Plugin → konfigurieren.

## Ausschalten

**Nur einmal:** `claude` statt `LOAD "*",8,1` tippen — kein Rahmen, keine C64-Farben.

**Deaktivieren, installiert lassen:**

```bash
claude plugin disable cc-retro-deck-mac@cc-retro-deck      # Linux/Windows: cc-retro-deck-linux / cc-retro-deck-windows
```

Ab der nächsten Sitzung sieht Claude Code aus wie ausgeliefert. Zurück mit
`claude plugin enable …`. `LOAD` bleibt in der Shell, bis man deinstalliert.

## Deinstallieren

**1. Entfernen, was die Einrichtung angelegt hat** — in Claude Code, solange das Plugin noch da ist:

```
/deck uninstall          zeigt, was es entfernen würde, entfernt nichts
/deck uninstall apply    führt es aus
```

Es beendet laufende Retro-Deck-Rahmen (nach einer Warnung; die Gespräche bleiben über
`claude --resume` erreichbar), entfernt den markierten Block aus der Shell-Datei, löscht die
Terminal-Profile (macOS) und `~/.claude/retro-deck/`.

**2. Plugin und Marktplatz entfernen:**

```bash
claude plugin uninstall cc-retro-deck-mac@cc-retro-deck    # Linux/Windows: cc-retro-deck-linux / cc-retro-deck-windows
claude plugin marketplace remove cc-retro-deck
```

Gegenprobe: `claude plugin list` nennt es nicht mehr, ein neuer Tab zeigt den gewohnten
Prompt, `LOAD` ist unbekannt.

### Von Hand, falls das Plugin schon weg ist

macOS und Linux unten; Windows: [windows/README.md](windows/README.md).

```bash
# laufende Rahmen beenden (macOS: ein tmux-Server je Tab; Linux: ein gemeinsamer)
for s in "${TMUX_TMPDIR:-/tmp}/tmux-$(id -u)"/c64-*; do tmux -S "$s" kill-server; done   # macOS
tmux -L c64 kill-server                                                                   # Linux
rm -rf ~/.claude/retro-deck
rm -rf ~/.claude/plugins/cache/cc-retro-deck     # Kopie von Claude Code selbst, falls noch da
```

Dann den Block zwischen `# >>> cc-retro-deck >>>` und `# <<< cc-retro-deck <<<` aus
`~/.zshrc` bzw. `~/.bashrc` löschen. Unter macOS die Profile „C64" und „C64 Rahmen" in
Terminal › Einstellungen › Profile entfernen (vorher ein anderes Profil als Standard setzen).

## Branding

Krabben-Kopfleiste und Banner („proudly presented by Alf") sind die Signatur der Builder
dieses Mods und nicht einstellbar. Der Code steht unter MIT: Forks sind frei — wer Kopfleiste
oder Banner ändert, gibt seiner Fassung bitte einen eigenen Namen.

## Star-Trek-Tribut

Der Einschaltbildschirm nach `LOAD "*",8,1` ist ein Tribut an Sir Patrick Stewart. Er ist
**inoffizielle Fan-Art**: Das Schiff ist von Grund auf im Code gezeichnet, Bilder oder Musik
aus Star Trek sind nicht enthalten. Star Trek und zugehörige Namen, Schiffe und Zitate sind
Marken und urheberrechtlich geschützt von CBS Studios Inc. / Paramount; der Tribut steht in
keiner Verbindung zu ihnen und ist nicht von ihnen gebilligt. Die MIT-Lizenz gilt nur für
den Code dieses Projekts und gewährt keine Rechte an fremden Marken oder Designs. Siehe
[NOTICE](NOTICE).

## Lizenz

[MIT](LICENSE) · [NOTICE](NOTICE)
