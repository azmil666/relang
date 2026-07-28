#!/usr/bin/env python3
import sys
import os
import argparse
import textwrap
import re
import random

COWS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cows")

def list_cows():
    cows = [f[:-4] for f in os.listdir(COWS_DIR) if f.endswith(".cow")]
    print("  ".join(sorted(cows)))

def generate_bubble(text, wrap_length, is_think, no_wrap):
    text = text.expandtabs(8)
    
    if not no_wrap:
        lines = []
        for line in text.split('\n'):
            wrapped = textwrap.wrap(line, width=wrap_length)
            if not wrapped:
                lines.append('')
            else:
                lines.extend(wrapped)
    else:
        lines = text.split('\n')
        
    max_len = max((len(line) for line in lines), default=0)
    
    top = ' ' + '_' * (max_len + 2)
    bottom = ' ' + '-' * (max_len + 2)
    
    bubble = [top]
    
    if len(lines) == 1:
        border_l, border_r = ('(', ')') if is_think else ('<', '>')
        bubble.append(f"{border_l} {lines[0].ljust(max_len)} {border_r}")
    else:
        for i, line in enumerate(lines):
            if is_think:
                border_l, border_r = '(', ')'
            elif i == 0:
                border_l, border_r = '/', '\\'
            elif i == len(lines) - 1:
                border_l, border_r = '\\', '/'
            else:
                border_l, border_r = '|', '|'
            bubble.append(f"{border_l} {line.ljust(max_len)} {border_r}")
            
    bubble.append(bottom)
    return '\n'.join(bubble)

def load_cow(cow_name, eyes, tongue, thoughts):
    if os.path.isabs(cow_name) or os.path.exists(cow_name):
        cow_path = cow_name
    else:
        if not cow_name.endswith('.cow'):
            cow_name += '.cow'
        cow_path = os.path.join(COWS_DIR, cow_name)
        
    if not os.path.exists(cow_path):
        print(f"cowsay: Could not find {cow_name} cowfile!", file=sys.stderr)
        sys.exit(1)
        
    with open(cow_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Extract heredoc block
    # Match `$the_cow = <<"EOC";` or similar up to `EOC`
    match = re.search(r'<<"[A-Z]+";\r?\n(.*?)\r?\n[A-Z]+', content, re.DOTALL)
    if match:
        template = match.group(1)
    else:
        template = content
        
    # Replace variables
    template = template.replace('$eyes', eyes)
    template = template.replace('${eyes}', eyes)
    template = template.replace('$tongue', tongue)
    template = template.replace('${tongue}', tongue)
    template = template.replace('$thoughts', thoughts)
    template = template.replace('${thoughts}', thoughts)
    
    # In perl templates, \\ is a literal backslash.
    template = template.replace('\\\\', '\\')
    template = template.replace('\\@', '@')
    
    return template

def main():
    parser = argparse.ArgumentParser(add_help=False, usage='%(prog)s [-e eye_string] [-f cowfile] [-h] [-l] [-n] [-T tongue_string] [-W column] [-bdgpstwy] text')
    
    parser.add_argument('text', nargs='*', help=argparse.SUPPRESS)
    parser.add_argument('-e', default='oo', help="Select the appearance of the cow's eyes.")
    parser.add_argument('-T', default='  ', help="The tongue is configurable similarly to the eyes through -T and tongue_string.")
    parser.add_argument('-W', default=40, type=int, help="Specifies roughly where the message should be wrapped.")
    parser.add_argument('-f', default='default', help="Specifies a cow picture file.")
    parser.add_argument('--think', action='store_true', help="Think the message instead of saying it aloud.")
    parser.add_argument('-n', action='store_true', help="If it is specified, the given message will not be word-wrapped.")
    parser.add_argument('-r', action='store_true', help="Select a random cow.")
    parser.add_argument('-l', action='store_true', help="List all cowfiles included in this package.")
    parser.add_argument('-h', '--help', action='store_true', help="Display this help message")
    
    # Face Modes
    parser.add_argument('-b', action='store_true', help="Mode: Borg")
    parser.add_argument('-d', action='store_true', help="Mode: Dead")
    parser.add_argument('-g', action='store_true', help="Mode: Greedy")
    parser.add_argument('-p', action='store_true', help="Mode: Paranoia")
    parser.add_argument('-s', action='store_true', help="Mode: Stoned")
    parser.add_argument('-t', action='store_true', help="Mode: Tired")
    parser.add_argument('-w', action='store_true', help="Mode: Wired")
    parser.add_argument('-y', action='store_true', help="Mode: Youthful")
    
    args, unknown = parser.parse_known_args()
    
    if args.help:
        parser.print_help()
        sys.exit(0)
        
    if args.l:
        list_cows()
        sys.exit(0)
        
    text = " ".join(args.text + unknown)
    if not text:
        if not sys.stdin.isatty():
            text = sys.stdin.read().rstrip('\r\n')
        
    if not text:
        parser.print_help()
        sys.exit(0)
        
    eyes, tongue = args.e, args.T
    
    if args.b: eyes, tongue = '==', '  '
    if args.d: eyes, tongue = 'xx', 'U '
    if args.g: eyes, tongue = '$$', '  '
    if args.p: eyes, tongue = '@@', '  '
    if args.s: eyes, tongue = '**', 'U '
    if args.t: eyes, tongue = '--', '  '
    if args.w: eyes, tongue = 'OO', '  '
    if args.y: eyes, tongue = '..', '  '

    cow_name = args.f
    if args.r:
        cows = [f for f in os.listdir(COWS_DIR) if f.endswith(".cow")]
        cow_name = random.choice(cows)
        
    is_think = args.think or 'cowthink' in os.path.basename(sys.argv[0])
    thoughts = 'o' if is_think else '\\'
    
    eyes = (eyes + '  ')[:2]
    tongue = (tongue + '  ')[:2]
    
    bubble = generate_bubble(text, args.W, is_think, args.n)
    cow = load_cow(cow_name, eyes, tongue, thoughts)
    
    print(bubble)
    print(cow, end="")

if __name__ == '__main__':
    main()
