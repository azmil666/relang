#!/usr/bin/env python3
import curses
import time
import random
import sys
import argparse
import traceback

import sprites

# --- Color Mapping ---
COLOR_MAP = {}
def init_colors():
    curses.use_default_colors()
    colors = {
        'k': curses.COLOR_BLACK,
        'r': curses.COLOR_RED,
        'g': curses.COLOR_GREEN,
        'y': curses.COLOR_YELLOW,
        'b': curses.COLOR_BLUE,
        'm': curses.COLOR_MAGENTA,
        'c': curses.COLOR_CYAN,
        'w': curses.COLOR_WHITE
    }
    
    # Init pairs
    idx = 1
    for k, v in colors.items():
        curses.init_pair(idx, v, -1)
        COLOR_MAP[k] = curses.color_pair(idx)
        COLOR_MAP[k.upper()] = curses.color_pair(idx) | curses.A_BOLD
        idx += 1
        
    COLOR_MAP['default'] = curses.color_pair(0)

# --- Z Depths ---
DEPTH = {
    'gui': 1,
    'shark': 2,
    'water_line3': 2,
    'water_gap3': 3,
    'water_line2': 4,
    'water_gap2': 5,
    'water_line1': 6,
    'water_gap1': 7,
    'water_line0': 8,
    'water_gap0': 9,
    'fish_start': 3,
    'fish_end': 20,
    'seaweed': 21,
    'castle': 22
}

class Entity:
    def __init__(self, name, shape, position, speed=(0,0,0), callback=None, 
                 die_offscreen=False, death_cb=None, color_mask=None, 
                 default_color='default', e_type='generic', frame_delay=1.0, die_time=None):
        self.name = name
        self.type = e_type
        
        # shape and color_mask should be lists of strings (frames)
        if isinstance(shape, str):
            self.frames = [shape]
        else:
            self.frames = shape
            
        if not color_mask:
            self.masks = [None] * len(self.frames)
        elif isinstance(color_mask, str):
            self.masks = [color_mask]
        else:
            self.masks = color_mask
            
        # Ensure masks array length matches frames
        if len(self.masks) < len(self.frames):
            self.masks = [self.masks[0]] * len(self.frames)
            
        self.x, self.y, self.z = position
        self.x_float = float(self.x)
        self.y_float = float(self.y)
        self.z_float = float(self.z)
        
        self.vx, self.vy, self.vz = speed
        self.callback = callback
        self.die_offscreen = die_offscreen
        self.death_cb = death_cb
        self.default_color = default_color
        
        self.frame_idx = 0
        self.frame_delay = frame_delay
        self.frame_timer = 0
        
        self.dead = False
        self.die_time = die_time

    @property
    def width(self):
        return max((len(line) for line in self.frames[self.frame_idx].split('\n')), default=0)

    @property
    def height(self):
        return len(self.frames[self.frame_idx].split('\n'))

    def update(self, engine):
        if self.die_time and time.time() > self.die_time:
            self.kill(engine)
            return
            
        if self.callback:
            self.callback(self, engine)
            
        self.x_float += self.vx
        self.y_float += self.vy
        self.z_float += self.vz
        self.x = int(self.x_float)
        self.y = int(self.y_float)
        self.z = int(self.z_float)
        
        # Animate
        if len(self.frames) > 1:
            self.frame_timer += 1
            if self.frame_timer >= self.frame_delay:
                self.frame_timer = 0
                self.frame_idx = (self.frame_idx + 1) % len(self.frames)
                
        # Die offscreen
        if self.die_offscreen:
            w, h = engine.width, engine.height
            if (self.x + self.width < -10) or (self.x > w + 10) or (self.y + self.height < -10) or (self.y > h + 10):
                self.kill(engine)

    def kill(self, engine):
        if not self.dead:
            self.dead = True
            engine.remove_entity(self)
            if self.death_cb:
                self.death_cb(self, engine)

    def draw(self, stdscr):
        frame = self.frames[self.frame_idx]
        mask = self.masks[self.frame_idx]
        
        lines = frame.split('\n')
        mask_lines = mask.split('\n') if mask else []
        
        max_y, max_x = stdscr.getmaxyx()
        
        def_color = COLOR_MAP.get(self.default_color[0].lower() if self.default_color != 'default' else 'default', COLOR_MAP['default'])
        if self.default_color.isupper() and self.default_color != 'default':
            def_color |= curses.A_BOLD
            
        for dy, line in enumerate(lines):
            screen_y = self.y + dy
            if screen_y < 0 or screen_y >= max_y - 1:
                continue
                
            m_line = mask_lines[dy] if dy < len(mask_lines) else ""
            
            for dx, char in enumerate(line):
                screen_x = self.x + dx
                if screen_x < 0 or screen_x >= max_x - 1:
                    continue
                if char in (' ', '?', '\n', '\r'):
                    continue
                    
                color = def_color
                if dx < len(m_line) and m_line[dx] != ' ':
                    m_char = m_line[dx]
                    color = COLOR_MAP.get(m_char, def_color)
                    
                try:
                    stdscr.addstr(screen_y, screen_x, char, color)
                except curses.error:
                    pass

class AnimationEngine:
    def __init__(self):
        self.entities = []
        self.width = 0
        self.height = 0

    def add_entity(self, ent):
        self.entities.append(ent)

    def remove_entity(self, ent):
        if ent in self.entities:
            self.entities.remove(ent)
            
    def get_entities_of_type(self, e_type):
        return [e for e in self.entities if e.type == e_type]

    def update(self):
        for ent in list(self.entities):
            if not ent.dead:
                ent.update(self)

    def draw(self, stdscr):
        stdscr.erase()
        self.height, self.width = stdscr.getmaxyx()
        
        # Sort by Z descending (higher Z is further back)
        sorted_ents = sorted(self.entities, key=lambda e: e.z, reverse=True)
        for ent in sorted_ents:
            ent.draw(stdscr)
            
        stdscr.refresh()

# --- Game Logic ---
opt_c = False # Classic mode

def rand_color(mask):
    colors = ['c','C','r','R','y','Y','b','B','g','G','m','M']
    for i in range(1, 10):
        c = random.choice(colors)
        mask = mask.replace(str(i), c)
    return mask

def add_environment(engine):
    water_line_segment = sprites.water_line_segment
    segment_size = len(water_line_segment[0])
    segment_repeat = int(engine.width / segment_size) + 2
    
    for i, seg in enumerate(water_line_segment):
        shape = seg * segment_repeat
        engine.add_entity(Entity(
            name=f"water_seg_{i}",
            e_type="waterline",
            shape=shape,
            position=[0, i+5, DEPTH[f'water_line{i}']],
            default_color='c'
        ))

def add_castle(engine):
    engine.add_entity(Entity(
        name="castle",
        shape=sprites.castle_image[0],
        color_mask=sprites.castle_mask[0],
        position=[engine.width - 32, engine.height - 14, DEPTH['castle']],
        default_color='default'
    ))

def add_all_seaweed(engine):
    count = int(engine.width / 15)
    for _ in range(count):
        add_seaweed(None, engine)

def add_seaweed(old_ent, engine):
    h = random.randint(3, 6)
    f1, f2 = "", ""
    for i in range(1, h + 1):
        if i % 2 == 1:
            f1 += "(\n"
            f2 += " )\n"
        else:
            f1 += " )\n"
            f2 += "(\n"
            
    x = random.randint(1, max(2, engine.width - 2))
    y = engine.height - h - 1
    speed = random.uniform(0.25, 0.3)
    
    engine.add_entity(Entity(
        name=f"seaweed_{random.random()}",
        shape=[f1, f2],
        position=[x, y, DEPTH['seaweed']],
        frame_delay=1.0 / speed,
        die_time=time.time() + random.randint(8*60, 12*60),
        death_cb=add_seaweed,
        default_color='g'
    ))

def bubble_collision(bubble, engine):
    for ent in engine.entities:
        if ent.type == 'waterline':
            # Check overlap manually
            if ent.y <= bubble.y <= ent.y + ent.height:
                bubble.kill(engine)
                break

def add_bubble(fish, engine):
    vx = 0
    bx = fish.x
    if fish.vx > 0:
        bx += fish.width
    by = fish.y + fish.height // 2
    bz = fish.z - 1
    
    def bubble_cb(b, eng):
        bubble_collision(b, eng)
        
    engine.add_entity(Entity(
        name="bubble",
        e_type="bubble",
        shape=['.', 'o', 'O', 'O', 'O'],
        position=[bx, by, bz],
        speed=(0, -1, 0),
        frame_delay=2,
        callback=bubble_cb,
        die_offscreen=True,
        default_color='C'
    ))

def fish_collision(fish, engine):
    for ent in engine.get_entities_of_type('teeth'):
        # Check simple overlap
        if ent.x <= fish.x + fish.width and ent.x + ent.width >= fish.x and ent.y <= fish.y + fish.height and ent.y + ent.height >= fish.y:
            if fish.height <= 5:
                add_splat(engine, fish.x, fish.y, fish.z)
                fish.kill(engine)
                break

def fish_callback(fish, engine):
    if random.randint(0, 100) > 97:
        add_bubble(fish, engine)
    fish_collision(fish, engine)

def add_fish(old_ent, engine):
    if not opt_c and random.randint(0, 11) > 8:
        add_new_fish(old_ent, engine)
    else:
        add_old_fish(old_ent, engine)

def add_new_fish(old_ent, engine):
    spawn_fish(engine, sprites.new_fish_image)

def add_old_fish(old_ent, engine):
    spawn_fish(engine, sprites.old_fish_image)

def spawn_fish(engine, fish_array):
    idx = random.randint(0, len(fish_array)//2 - 1)
    shape = fish_array[idx*2]
    mask = rand_color(fish_array[idx*2 + 1].replace('4', 'W'))
    
    speed = random.uniform(0.25, 2.25)
    if idx % 2 != 0:
        speed *= -1
        x = engine.width - 2
    else:
        x = -15
        
    depth = random.randint(DEPTH['fish_start'], DEPTH['fish_end'])
    
    max_h = 9
    min_h = max(10, engine.height - 15)
    y = random.randint(max_h, min_h)
    
    engine.add_entity(Entity(
        name="fish",
        e_type="fish",
        shape=shape,
        color_mask=mask,
        position=[x, y, depth],
        speed=(speed, 0, 0),
        callback=fish_callback,
        die_offscreen=True,
        death_cb=add_fish,
        default_color='default'
    ))

def add_all_fish(engine):
    screen_size = (engine.height - 9) * engine.width
    count = int(screen_size / 350)
    for _ in range(count):
        add_fish(None, engine)

def add_splat(engine, x, y, z):
    engine.add_entity(Entity(
        name="splat",
        shape=sprites.splat_image,
        position=[x - 4, y - 2, z - 2],
        frame_delay=3,
        die_time=time.time() + 1.5,
        default_color='R'
    ))

# --- Random Objects ---
def shark_death(shark, engine):
    for t in engine.get_entities_of_type('teeth'):
        t.kill(engine)
    random_object(shark, engine)
    
def add_shark(old_ent, engine):
    d = random.randint(0, 1)
    speed = 2
    x = -53
    y = random.randint(9, max(10, engine.height - 19))
    teeth_x = -9
    teeth_y = y + 7
    
    if d == 1:
        speed *= -1
        x = engine.width - 2
        teeth_x = x + 9
        
    engine.add_entity(Entity(
        name="teeth",
        e_type="teeth",
        shape="*",
        position=[teeth_x, teeth_y, DEPTH['shark']+1],
        speed=(speed, 0, 0),
        default_color='default'
    ))
    
    engine.add_entity(Entity(
        name="shark",
        e_type="shark",
        shape=sprites.shark_image[d],
        color_mask=sprites.shark_mask[d],
        position=[x, y, DEPTH['shark']],
        speed=(speed, 0, 0),
        die_offscreen=True,
        death_cb=shark_death,
        default_color='C'
    ))

def add_ship(old_ent, engine):
    d = random.randint(0, 1)
    speed = 1
    x = -24
    if d == 1:
        speed *= -1
        x = engine.width - 2
        
    engine.add_entity(Entity(
        name="ship",
        shape=sprites.ship_image[d],
        color_mask=sprites.ship_mask[d],
        position=[x, 0, DEPTH['water_gap1']],
        speed=(speed, 0, 0),
        die_offscreen=True,
        death_cb=random_object,
        default_color='W'
    ))

def add_whale(old_ent, engine):
    d = random.randint(0, 1)
    speed = 1
    if d == 1:
        speed *= -1
        x = engine.width - 2
        spout_align = 1
    else:
        x = -18
        spout_align = 11
        
    anim_frames = []
    anim_masks = []
    
    for _ in range(5):
        anim_frames.append("\n\n\n" + sprites.whale_image[d])
        anim_masks.append(sprites.whale_mask[d])
        
    for sf in sprites.water_spout:
        aligned = "\n".join((" " * spout_align) + line for line in sf.split("\n"))
        anim_frames.append(aligned + "\n" + sprites.whale_image[d])
        anim_masks.append(sprites.whale_mask[d])
        
    engine.add_entity(Entity(
        name="whale",
        shape=anim_frames,
        color_mask=anim_masks,
        position=[x, 0, DEPTH['water_gap2']],
        speed=(speed, 0, 0),
        frame_delay=2,
        die_offscreen=True,
        death_cb=random_object,
        default_color='W'
    ))

def add_monster(old_ent, engine):
    if not opt_c:
        add_new_monster(old_ent, engine)
    else:
        add_old_monster(old_ent, engine)

def add_new_monster(old_ent, engine):
    d = random.randint(0, 1)
    speed = 2
    if d == 1:
        speed *= -1
        x = engine.width - 2
    else:
        x = -54
        
    engine.add_entity(Entity(
        name="monster",
        shape=sprites.new_monster_image[d],
        color_mask=[sprites.new_monster_mask[d]] * len(sprites.new_monster_image[d]),
        position=[x, 2, DEPTH['water_gap2']],
        speed=(speed, 0, 0),
        frame_delay=4,
        die_offscreen=True,
        death_cb=random_object,
        default_color='G'
    ))

def add_old_monster(old_ent, engine):
    d = random.randint(0, 1)
    speed = 2
    if d == 1:
        speed *= -1
        x = engine.width - 2
    else:
        x = -64
        
    engine.add_entity(Entity(
        name="monster",
        shape=sprites.old_monster_image[d],
        color_mask=[sprites.old_monster_mask[d]] * len(sprites.old_monster_image[d]),
        position=[x, 2, DEPTH['water_gap2']],
        speed=(speed, 0, 0),
        frame_delay=4,
        die_offscreen=True,
        death_cb=random_object,
        default_color='G'
    ))

def add_big_fish(old_ent, engine):
    if not opt_c and random.randint(0, 2) > 0:
        add_big_fish_2(old_ent, engine)
    else:
        add_big_fish_1(old_ent, engine)

def add_big_fish_1(old_ent, engine):
    spawn_big_fish(engine, sprites.big_fish_1_image, sprites.big_fish_1_mask)
    
def add_big_fish_2(old_ent, engine):
    spawn_big_fish(engine, sprites.big_fish_2_image, sprites.big_fish_2_mask)

def spawn_big_fish(engine, images, masks):
    d = random.randint(0, 1)
    speed = 3.0
    if d == 1:
        x = engine.width - 1
        speed *= -1
    else:
        x = -34
        
    y = random.randint(9, max(10, engine.height - 15))
    mask = rand_color(masks[d])
    
    engine.add_entity(Entity(
        name="big_fish",
        shape=images[d],
        color_mask=mask,
        position=[x, y, DEPTH['shark']],
        speed=(speed, 0, 0),
        die_offscreen=True,
        death_cb=random_object,
        default_color='Y'
    ))

RANDOM_OBJECTS = [add_ship, add_whale, add_monster, add_big_fish, add_shark]

def random_object(old_ent, engine):
    cb = random.choice(RANDOM_OBJECTS)
    cb(old_ent, engine)

def main(stdscr):
    global opt_c
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', action='store_true', help="classic mode")
    args = parser.parse_args()
    opt_c = args.c

    curses.curs_set(0)
    curses.halfdelay(1)
    stdscr.nodelay(True)
    init_colors()

    engine = AnimationEngine()
    engine.height, engine.width = stdscr.getmaxyx()
    
    add_environment(engine)
    add_castle(engine)
    add_all_seaweed(engine)
    add_all_fish(engine)
    random_object(None, engine)

    paused = False
    
    while True:
        try:
            key = stdscr.getch()
            if key == ord('q') or key == ord('Q'):
                break
            elif key == ord('r') or key == ord('R'):
                engine.entities.clear()
                add_environment(engine)
                add_castle(engine)
                add_all_seaweed(engine)
                add_all_fish(engine)
                random_object(None, engine)
            elif key == ord('p') or key == ord('P'):
                paused = not paused
            elif key == curses.KEY_RESIZE:
                engine.height, engine.width = stdscr.getmaxyx()
                # Re-setup waterline and seaweed for new width
                for e in engine.get_entities_of_type('waterline'):
                    engine.remove_entity(e)
                add_environment(engine)
        except Exception:
            pass

        if not paused:
            engine.update()
            
        try:
            engine.draw(stdscr)
        except Exception:
            pass

if __name__ == '__main__':
    try:
        curses.wrapper(main)
    except Exception as e:
        traceback.print_exc()
