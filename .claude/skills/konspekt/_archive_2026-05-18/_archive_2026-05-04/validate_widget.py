#!/usr/bin/env python3
"""
PostToolUse hook: validates JS syntax in Виджет*.html files.
Runs automatically after Claude writes or edits any widget file.
"""
import sys
import json
import re
import subprocess
import os


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_input = data.get('tool_input', {})
    file_path = tool_input.get('file_path', '')

    if not file_path:
        sys.exit(0)

    filename = os.path.basename(file_path)

    if not re.match(r'Виджет.*\.html$', filename):
        sys.exit(0)

    try:
        with open(file_path, encoding='utf-8') as f:
            html = f.read()
    except Exception as e:
        print(f'Cannot read widget file: {e}', file=sys.stderr)
        sys.exit(0)

    m = re.search(r'<script>(.*?)</script>', html, re.DOTALL)
    if not m:
        sys.exit(0)

    js = m.group(1)
    tmp_path = file_path + '.__jscheck__.js'

    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write(js)

        result = subprocess.run(
            ['node', '--check', tmp_path],
            capture_output=True, text=True
        )

        if result.returncode != 0:
            err = result.stderr.replace(tmp_path, file_path)
            print(f'\n❌ JS SYNTAX ERROR in {filename}:\n{err}', file=sys.stderr)
            sys.exit(2)
        else:
            print(f'✅ {filename}: JS syntax OK')
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


if __name__ == '__main__':
    main()
