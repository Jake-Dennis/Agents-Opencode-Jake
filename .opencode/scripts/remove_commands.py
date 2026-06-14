"""Remove the "command" block from the global config.

Usage: python remove_commands.py <global_config_path>
"""
import json
import re
import sys


def main():
    if len(sys.argv) < 2:
        print(f'Usage: {sys.argv[0]} <global_config>')
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding='utf-8') as f:
        content = f.read()

    # Remove the command block. It's inserted as: ,\n  "command": { ... },\n  "agent": {
    pattern = r',\s*\n\s*"command":\s*\{[^}]*\}\s*(\n\s*,?\s*\n?\s*"agent":\s*\{)'
    new_content = re.sub(pattern, r'\1', content, count=1)

    if new_content == content:
        print('  [SKIP] no command block found to remove')
    else:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print('  [OK] command block removed from global config')


if __name__ == '__main__':
    main()
