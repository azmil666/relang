# Cowsay (Python Migration)

This is a complete Python migration of the original Node.js `cowsay` reference implementation.

## Requirements

- Python 3.6+
- Runs entirely using the standard library. No external dependencies are needed.

## Build

No build step is required for Python. 
Just ensure Python 3 is installed. If using Ubuntu/Linux, you can install it via:
```bash
sudo apt update
sudo apt install python3
```

## Run

Run the script by passing your message as arguments:
```bash
python3 cowsay.py "Hello, world!"
```

Or you can use stdin:
```bash
echo "Hello, world!" | python3 cowsay.py
```

### Examples with CLI options:
```bash
# Use Borg mode
python3 cowsay.py -b "Resistance is futile"

# Specify a custom cow
python3 cowsay.py -f ghostbusters "Who you gonna call?"

# Think mode instead of say
python3 cowsay.py --think "Hmm... I should eat grass."

# No word wrap
python3 cowsay.py -n "This is a very long line that will not be wrapped at all by cowsay."
```

## Supported Features
- Word wrapping (defaults to 40 columns, customizable with `-W`)
- Disable wrapping (`-n`)
- Pipe/Stdin reading support
- All predefined character modes (`-b`, `-d`, `-g`, `-p`, `-s`, `-t`, `-w`, `-y`)
- Custom eyes (`-e`) and tongue (`-T`)
- Custom cows (`-f`)
- Think mode (`--think`)
- List all available cows (`-l`)
- Random cow (`-r`)

## Validate / Submit

For the relang hackathon (Easy tier):
```bash
source ../setup.sh
relang "python3 cowsay/target/cowsay.py"
```
