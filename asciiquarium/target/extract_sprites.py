import re
import json

PERL_FILE = "../source/asciiquarium"
OUT_FILE = "sprites.py"

def extract_perl_arrays():
    with open(PERL_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    out = ["# Auto-generated sprites from Perl source\n"]

    # Match my @name = ( ... ); or my $name = ...;
    # But for strings, they use q{...} or q#...#
    
    def extract_q_strings(text):
        strings = []
        # find q{ ... } or q# ... #
        # We can just look for q{ or q#
        i = 0
        while True:
            m1 = text.find('q{', i)
            m2 = text.find('q#', i)
            if m1 == -1 and m2 == -1:
                break
            
            if m1 != -1 and (m2 == -1 or m1 < m2):
                start = m1 + 2
                end = text.find('}', start)
                strings.append(text[start:end])
                i = end + 1
            else:
                start = m2 + 2
                end = text.find('#', start)
                strings.append(text[start:end])
                i = end + 1
        return strings

    blocks = {
        'water_line_segment': r'my @water_line_segment = \((.*?)\);',
        'castle_image': r'my \$castle_image = (q\{.*?\});',
        'castle_mask': r'my \$castle_mask = (q\{.*?\});',
        'splat_image': r'my @splat_image = \((.*?)\);',
        'shark_image': r'my @shark_image = \((.*?)\);',
        'shark_mask': r'my @shark_mask = \((.*?)\);',
        'ship_image': r'my @ship_image = \((.*?)\);',
        'ship_mask': r'my @ship_mask = \((.*?)\);',
        'whale_image': r'my @whale_image = \((.*?)\);',
        'whale_mask': r'my @whale_mask = \((.*?)\);',
        'water_spout': r'my @water_spout = \((.*?)\);',
    }

    for name, pattern in blocks.items():
        m = re.search(pattern, content, re.DOTALL)
        if m:
            block_content = m.group(1)
            strings = extract_q_strings(block_content)
            out.append(f"{name} = {repr(strings)}\n")

    # Monster and Big Fish have a nested array structure or different logic?
    # Actually, in Perl it's: my @monster_image = ( [ q{...}, q{...} ], [ q{...}, ... ] );
    # Let's extract new_fish, old_fish, new_monster, old_monster, big_fish_1, big_fish_2
    
    def extract_from_sub(sub_name, var_name, pattern):
        m = re.search(r'sub ' + sub_name + r' \{.*?my ' + pattern + r' = \((.*?)\);', content, re.DOTALL)
        if m:
            return extract_q_strings(m.group(1))
        return []

    out.append(f"new_fish_image = {repr(extract_from_sub('add_new_fish', '@fish_image', r'@fish_image'))}\n")
    out.append(f"old_fish_image = {repr(extract_from_sub('add_old_fish', '@fish_image', r'@fish_image'))}\n")
    
    out.append(f"new_monster_image = {repr(extract_from_sub('add_new_monster', '@monster_image', r'@monster_image'))}\n")
    out.append(f"new_monster_mask = {repr(extract_from_sub('add_new_monster', '@monster_mask', r'@monster_mask'))}\n")
    
    out.append(f"old_monster_image = {repr(extract_from_sub('add_old_monster', '@monster_image', r'@monster_image'))}\n")
    out.append(f"old_monster_mask = {repr(extract_from_sub('add_old_monster', '@monster_mask', r'@monster_mask'))}\n")

    out.append(f"big_fish_1_image = {repr(extract_from_sub('add_big_fish_1', '@big_fish_image', r'@big_fish_image'))}\n")
    out.append(f"big_fish_1_mask = {repr(extract_from_sub('add_big_fish_1', '@big_fish_mask', r'@big_fish_mask'))}\n")
    
    out.append(f"big_fish_2_image = {repr(extract_from_sub('add_big_fish_2', '@big_fish_image', r'@big_fish_image'))}\n")
    out.append(f"big_fish_2_mask = {repr(extract_from_sub('add_big_fish_2', '@big_fish_mask', r'@big_fish_mask'))}\n")

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))

if __name__ == '__main__':
    extract_perl_arrays()
