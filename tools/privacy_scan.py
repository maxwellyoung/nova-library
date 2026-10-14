#!/usr/bin/env python3
"""Scan the source candidate for common private data and accidental binaries.

This scanner covers source files, not ignored local output or Git history.
It prints rule names and paths only, never matched private content.
"""
import argparse
import ipaddress
import re
from pathlib import Path


SKIP_DIRS = {'.git', '.venv', '__pycache__', 'node_modules', 'runtime', 'input',
             'library', 'evidence', 'outputs', 'build'}
FORBIDDEN_SUFFIXES = {'.apk', '.aab', '.db', '.sqlite', '.log', '.vault', '.pem', '.key', '.mp4', '.png', '.jpg'}
RULES = {
    'machine path': re.compile(r'/(?:Users|Volumes)/[^\s"\'<>]+'),
    'private chat': re.compile(r'Discord ' + r'thread|team ' + r'comms|BEGIN ' + r'PRIVATE KEY|BEGIN ' + r'OPENSSH PRIVATE KEY', re.I),
    'access token': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{25,}|sk-[A-Za-z0-9_-]{25,}|AKIA[A-Z0-9]{16})\b'),
    'email address': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
}
IPV4 = re.compile(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])')


def findings(path, text):
    result = []
    for name, pattern in RULES.items():
        for line in text.splitlines():
            for match in pattern.finditer(line):
                synthetic_email = name == 'email address' and str(path) == 'native/nova-library.patch' and match.group() == 'pass@' + 'example.test' and 'Enrollment e;' in line
                if not synthetic_email:
                    result.append(name)
    for line in text.splitlines():
        for match in IPV4.finditer(line):
            try:
                address = ipaddress.ip_address(match.group())
            except ValueError:
                continue
            private = address in ipaddress.ip_network('10.0.0.0/8') or address in ipaddress.ip_network('172.16.0.0/12') or address in ipaddress.ip_network('192.168.0.0/16') or address in ipaddress.ip_network('100.64.0.0/10')
            # Synthetic boundary test belongs to the complete native patch.
            fixture = str(path) == 'native/nova-library.patch' and address == ipaddress.ip_address('100.100.1.1') and 'Enrollment e;' in line
            policy_definition = str(path) == 'tools/privacy_scan.py' and (
                ('ip_network(' in line and line[match.end():].startswith('/')) or
                ('fixture =' in line and str(address) == '100.100.1.1'))
            if private and not fixture and not policy_definition:
                result.append('private network address')
    return sorted(set(result))


def scan(root):
    root = Path(root)
    failures = []
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if path.name == '.DS_Store':
            continue
        if any(part in SKIP_DIRS for part in relative.parts) or relative.parts[:2] == ('demo', 'generated'):
            continue
        if path.is_symlink():
            failures.append((str(relative), 'symlink outside curated source boundary'))
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() in FORBIDDEN_SUFFIXES or path.name.startswith('.env') or path.name == 'enrollment.json':
            failures.append((str(relative), 'private/generated artifact'))
            continue
        try:
            content = path.read_text()
        except UnicodeDecodeError:
            failures.append((str(relative), 'binary file requires explicit review'))
            continue
        failures.extend((str(relative), rule) for rule in findings(relative, content))
    return failures


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', nargs='?', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    failures = scan(args.root)
    for path, rule in failures:
        print(f'{path}: {rule}')
    if failures:
        parser.exit(1, f'Privacy scan failed: {len(failures)} finding(s).\n')
    print('Source privacy scan passed; review the full publication diff separately.')
