import sys

with open('asciiquarium.py', 'r') as f:
    content = f.read()

content = content.replace('shape=sprites.shark_image[d],', 'shape=sprites.shark_image[d % len(sprites.shark_image)],')
content = content.replace('color_mask=sprites.shark_mask[d],', 'color_mask=sprites.shark_mask[d % len(sprites.shark_mask)],')

content = content.replace('shape=sprites.ship_image[d],', 'shape=sprites.ship_image[d % len(sprites.ship_image)],')
content = content.replace('color_mask=sprites.ship_mask[d],', 'color_mask=sprites.ship_mask[d % len(sprites.ship_mask)],')

content = content.replace('anim_frames.append("\\n\\n\\n" + sprites.whale_image[d])', 'anim_frames.append("\\n\\n\\n" + sprites.whale_image[d % len(sprites.whale_image)])')
content = content.replace('anim_masks.append(sprites.whale_mask[d])', 'anim_masks.append(sprites.whale_mask[d % len(sprites.whale_mask)])')

content = content.replace('anim_frames.append(aligned + "\\n" + sprites.whale_image[d])', 'anim_frames.append(aligned + "\\n" + sprites.whale_image[d % len(sprites.whale_image)])')

content = content.replace('shape=sprites.new_monster_image[d],', 'shape=sprites.new_monster_image[d % len(sprites.new_monster_image)],')
content = content.replace('color_mask=[sprites.new_monster_mask[d]] * len(sprites.new_monster_image[d]),', 'color_mask=[sprites.new_monster_mask[d % len(sprites.new_monster_mask)]] * len(sprites.new_monster_image[d % len(sprites.new_monster_image)]),')

content = content.replace('shape=sprites.old_monster_image[d],', 'shape=sprites.old_monster_image[d % len(sprites.old_monster_image)],')
content = content.replace('color_mask=[sprites.old_monster_mask[d]] * len(sprites.old_monster_image[d]),', 'color_mask=[sprites.old_monster_mask[d % len(sprites.old_monster_mask)]] * len(sprites.old_monster_image[d % len(sprites.old_monster_image)]),')

content = content.replace('mask = rand_color(masks[d])', 'mask = rand_color(masks[d % len(masks)])')
content = content.replace('shape=images[d],', 'shape=images[d % len(images)],')

with open('asciiquarium.py', 'w') as f:
    f.write(content)
print('Replaced successfully.')
