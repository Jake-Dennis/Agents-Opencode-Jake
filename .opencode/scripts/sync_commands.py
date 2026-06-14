"""Sync .opencode/commands/*.md files into the global config's command block.

Usage: python sync_commands.py <repo_dir> <global_config_path>
"""
import json
import os
import re
import sys


def read_command(path):
    """Parse a command .md file, return (frontmatter_dict, body_text)."""
    with open(path, encoding='utf-8') as f:
        content = f.read()
    m = re.match(r'^---\n(.+?)\n---\n\n(.+)', content, re.DOTALL)
    if m:
        fm = {}
        for line in m.group(1).split('\n'):
            if ':' in line:
                k, v = line.split(':', 1)
                fm[k.strip()] = v.strip()
        body = m.group(2).strip()
        return fm, body
    return {}, content.strip()


def main():
    if len(sys.argv) < 3:
        print(f'Usage: {sys.argv[0]} <repo_dir> <global_config>')
        sys.exit(1)

    repo_dir = sys.argv[1]
    global_config = sys.argv[2]
    commands_dir = os.path.join(repo_dir, '.opencode', 'commands')

    # Discover all .md files in the commands directory
    if not os.path.isdir(commands_dir):
        print('  [SKIP] no .opencode/commands/ directory')
        return

    md_files = sorted([f for f in os.listdir(commands_dir) if f.endswith('.md')])
    if not md_files:
        print('  [SKIP] no .md files in .opencode/commands/')
        return

    # Parse each command
    commands = {}
    for fname in md_files:
        fpath = os.path.join(commands_dir, fname)
        fm, body = read_command(fpath)
        cmd_name = fname.replace('.md', '')
        commands[cmd_name] = {
            'description': fm.get('description', ''),
            'template': body
        }

    # Read global config
    with open(global_config, encoding='utf-8') as f:
        content = f.read()

    # Serialize the command block
    cmd_json = json.dumps(commands, indent=2, ensure_ascii=False)

    # Inject before "agent" key
    old = ',\n  "agent": {'
    new = f',\n  "command": {cmd_json},\n  "agent": {{'

    if old in content:
        content = content.replace(old, new, 1)
        with open(global_config, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'  [OK] added {len(commands)} commands to global config')
    else:
        # Check if command block already exists, update it
        if '"command"' in content:
            # Replace existing command block
            import re as re2
            # Find the existing command block and replace agent insertion
            content = re2.sub(
                r',\s*"command":\s*\{[^}]*\}(,\s*"agent":\s*\{)',
                f',\n  "command": {cmd_json},\\1',
                content,
                count=1
            )
            with open(global_config, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f'  [OK] updated {len(commands)} commands in global config')
        else:
            print('  [WARN] could not inject commands — "agent" key not found')


if __name__ == '__main__':
    main()
