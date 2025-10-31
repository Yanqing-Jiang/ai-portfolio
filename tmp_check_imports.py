import ast
import importlib
import pathlib
import sys

root = pathlib.Path('backend').resolve()
sys.path.insert(0, str(root))
missing = []
modules_cache = {}

for path in root.rglob('*.py'):
    rel = path.relative_to(root)
    module_name = '.'.join(rel.with_suffix('').parts)
    parts = module_name.split('.') if module_name else []
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except Exception:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ''
            level = node.level or 0
            if level:
                if level > len(parts):
                    base_parts = []
                else:
                    base_parts = parts[:-level]
                base = '.'.join(base_parts)
                if module:
                    full_module = f"{base}.{module}" if base else module
                else:
                    full_module = base
            else:
                full_module = module
            if not full_module:
                continue
            full_module = full_module.replace('..', '.')
            if full_module.startswith('.'):
                continue
            mod = modules_cache.get(full_module)
            if mod is None:
                try:
                    mod = importlib.import_module(full_module)
                except Exception as e:
                    modules_cache[full_module] = None
                    missing.append((str(rel), node.lineno, full_module, None, repr(e)))
                    continue
                modules_cache[full_module] = mod
            if mod is None:
                continue
            for alias in node.names:
                if alias.name == '*':
                    continue
                if not hasattr(mod, alias.name):
                    missing.append((str(rel), node.lineno, full_module, alias.name, 'missing attribute'))

for entry in missing:
    print(entry)
