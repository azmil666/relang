# Asciiquarium (Python Migration)

This is a complete Python migration of the original Perl `asciiquarium` implementation.

## Requirements

- Python 3.6+
- Runs entirely using the standard library. No external dependencies or pip packages are needed. (The `curses` module is built into Python on Unix/Linux systems).

## Build

No build step is required for Python. 
Just ensure Python 3 is installed.

## Run

Run the script from the terminal:
```bash
python3 asciiquarium.py
```

### Command Line Options:
```bash
# Classic mode (only classic fish and monsters)
python3 asciiquarium.py -c
```

### Keybindings (While Running):
- **`q`** : Quit the animation.
- **`p`** : Pause or unpause the animation.
- **`r`** : Redraw screen (refreshes all entities and the environment instantly).

## Supported Features
- Dynamic Z-ordering (Castle -> Seaweed -> Fish -> Bubbles -> UI).
- Color masks exactly matching the original Perl version.
- Multi-frame sprite animations (whales spouting water, seaweed swaying).
- Event callbacks (bubbles spawning, bloody splats on collision).
- Transparent characters (spaces and `?` are dynamically handled to prevent overlapping rectangles).
- Automatic seamless resizing.

## Validate / Submit

For the relang hackathon (Easy tier):
```bash
source ../setup.sh
relang "python3 asciiquarium/target/asciiquarium.py"
```
