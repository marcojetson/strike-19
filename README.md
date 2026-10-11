# STRIKE-19

A local artillery game for **Batocera Linux** arcade cabinets, written in Python 3 + pygame.
Play 1 player against the CPU or 2 players, over classic or brawl modes.

![STRIKE-19 gameplay](docs/screenshot.png)

## Build & test

```bash
pip install -r requirements.txt                  # pygame-ce
python3 build_sounds.py                          # regenerate sounds/ (rarely needed)
python3 strike-19.pygame --windowed             # play on the desktop
python3 tests/smoke_test.py                      # self-checks + headless play-through
```

`tests/smoke_test.py` exercises the pure logic and plays a scripted round with the SDL dummy
driver (no display, no audio, no external deps), so it works over SSH on the cabinet too.

## Deploy to a Batocera cabinet

Copy the project folder to `roms/pygame/strike-19/` on the Batocera
share, then add a gamelist entry (or run "Update gamelists" on the box). Batocera runs the
`.pygame` file directly with its bundled pygame.
