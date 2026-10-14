#!/usr/bin/env python3
"""Generate deterministic invented catalogue data and original SVG covers."""
import argparse
import json
from pathlib import Path


TITLES = [
    ('Amber Orbit', 'demo:orbit', 'handheld', 'Handheld', '#bc7747', 'playing', '32'),
    ('Tidal Garden', 'demo:garden', 'console', 'Console', '#719b8a', 'backlog', ''),
    ('Paper Horizon', 'demo:horizon', 'pc', 'PC', '#8873a6', 'finished', '0'),
    ('Small Hours', 'demo:hours', 'handheld', 'Handheld', '#8a9daf', 'unknown', ''),
]


def generate(output):
    output = Path(output)
    # Refuse to touch an existing library, including an empty directory or symlink.
    output.mkdir(parents=True, exist_ok=False)
    (output / 'art').mkdir()
    (output / 'catalog').mkdir()
    games, metadata = [], ['collection: Nova Demo', 'shortname: nova-demo', '']
    for index, (title, identity, system, system_name, color, status, minutes) in enumerate(TITLES):
        stem = identity.split(':')[1]
        marker = f'catalog/{stem}.catalog'
        cover = f'art/{stem}.svg'
        (output / marker).write_text('Synthetic catalogue marker. Not a game executable.\n')
        (output / cover).write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="480" height="640" viewBox="0 0 480 640">'
            f'<rect width="480" height="640" fill="{color}"/>'
            '<circle cx="240" cy="245" r="130" fill="none" stroke="#ffffff" stroke-opacity=".5" stroke-width="2"/>'
            f'<path d="M80 {300+index*20} L400 {150+index*30}" stroke="#ffffff" stroke-width="16" stroke-opacity=".4"/>'
            f'<text x="36" y="560" font-family="sans-serif" font-size="32" fill="#ffffff">{title}</text></svg>\n')
        extra = {'edition-id': identity, 'system-id': system, 'system-name': system_name,
                 'home': 'true' if index < 2 else 'false', 'launchable': 'false',
                 'route-label': 'Synthetic catalogue; no launch route', 'ready-devices': '[]',
                 'progress-state': status, 'minutes-value': minutes, 'catalog-source': 'Invented demo fixture'}
        game = {'title': title, 'sortBy': title, 'developer': 'Demo Studio', 'genre': 'Demo',
                'missing': False, 'lastPlayed': '', 'file': marker, 'cover': cover, 'extra': extra}
        games.append(game)
        metadata.extend([f'game: {title}', f'file: {marker}', f'assets.boxFront: {cover}'])
        metadata.extend(f'x-{key}: {value}' for key, value in extra.items() if value != '')
        metadata.append('')
    (output / 'games.json').write_text(json.dumps(games, indent=2) + '\n')
    (output / 'metadata.txt').write_text('\n'.join(metadata))
    # Wrapper imports this file; art paths resolve relative to the generated JS URL.
    (output / 'games.js').write_text('.pragma library\nvar games = ' + json.dumps(games, indent=2) + ';\n')
    return games


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'demo/generated')
    args = parser.parse_args()
    try:
        games = generate(args.output)
    except FileExistsError:
        parser.exit(1, 'Output already exists; select a new empty path or remove only your generated demo.\n')
    print(f'Generated {len(games)} synthetic non-launchable entries.')
