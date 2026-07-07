# Browser Revamp — Signature Dark-Industrial Retheme

Visual-only pass. No feature logic changed, so nothing that worked before is affected.
Drop these files over your existing `src/` (back up first if you like — a `new_tab.html.bak`
was already made locally during the rewrite).

## Palette (7h3v01d signature)
| token    | hex       | role                        |
|----------|-----------|-----------------------------|
| obsidian | `#0b0f14` | page background             |
| panel    | `#0e141b` | raised surfaces / cards     |
| input    | `#11171f` | fields                      |
| border   | `#1c2733` | hairlines                   |
| steel    | `#253341` | strong border / scrollbar   |
| teal     | `#2fd6c3` | primary accent              |
| amber    | `#ffb454` | secondary accent            |
| phosphor | `#4be08a` | live / secure state         |
| red      | `#ff5c66` | danger / close              |

Typography: JetBrains Mono → Cascadia Mono → Consolas → monospace.
Chrome: flat, zero-radius, 1px borders throughout.

## Files changed
- **browser.py** — rewrote `DARK_QSS` (global sheet: toolbar, tabs, URL bar,
  menus, docks, tables, trees, scrollbars, progress, checkboxes, tooltips).
  Active tab now carries a teal underline; secure state goes phosphor.
  Also rethemed the reading-mode article template (obsidian bg, mono HUD bar,
  teal links, `// READER` tag, `EXIT` button).
- **new_tab.html** — full repaint. Mono clock with teal seconds, greeting +
  amber `//` date line, flat search bar, corner-bracket speed-dial cards
  (muted → teal on hover), flat zero-radius add-site modal, and a HUD footer
  readout (CONNECTION SECURE · date · tile count). All original JS behaviour
  preserved (localStorage tiles, favicons, add/remove, DuckDuckGo routing);
  clock now ticks every second instead of every 10s.
- **dialogs.py** — retinted the few hardcoded accents (notes toggle buttons,
  domain label, clear button, list labels) to teal/red/dim.
- **main_gui.py** — download progress states retuned: done=phosphor,
  error=red, stopped=amber.
- **plugins/screenshot_plugin.py** — region-select marquee + wash moved from
  red to teal.

Everything else inherits the global sheet automatically, so bookmarks/history/
downloads/notes panels and all plugin menus pick up the new look with no edits.

## Note
`notes.txt` in the project root still contains live xAI and Gemini API keys in
plaintext. Scrub + rotate those before this goes anywhere near git.
