import os
import re
from pathlib import Path

# Root of the project (can be overridden via env)
PROJECT_ROOT = Path(os.getenv('PROJECT_ROOT', '/home/ahsan/Desktop/agy_projects/sentinel'))

# Directories containing source code
PYTHON_DIRS = [
    PROJECT_ROOT / 'sidecars' / 'hunter' / 'src_py',
    PROJECT_ROOT / 'sidecars' / 'rag' / 'src_py'
]
TS_DIRS = [
    PROJECT_ROOT / 'sidecars' / 'hunter' / 'src',
    PROJECT_ROOT / 'sidecars' / 'rag' / 'src'
]

def write_md(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

# ---------------------------------------------------------------------------
# 1. Documentation coverage (Python top‑level docstrings)
# ---------------------------------------------------------------------------
missing_doc = []
for d in PYTHON_DIRS:
    for py_file in d.rglob('*.py'):
        try:
            text = py_file.read_text(encoding='utf-8')
        except Exception:
            continue
        # Look for a triple‑quoted string at the very start of the file
        if not re.search(r'^\s*""".*?"""', text, re.DOTALL):
            missing_doc.append(py_file.relative_to(PROJECT_ROOT))

doc_md = "# Documentation Coverage Report\n\n"
if missing_doc:
    doc_md += "The following Python modules lack a top‑level docstring:\n\n"
    for p in missing_doc:
        doc_md += f"- `{p}`\n"
else:
    doc_md += "All scanned Python files contain a top‑level docstring.\n"
write_md(PROJECT_ROOT / 'documentation_report.md', doc_md)

# ---------------------------------------------------------------------------
# 2. Missing imports detection (Python only)
# ---------------------------------------------------------------------------
import_rx = re.compile(r'^(?:from\s+([\.\w]+)\s+import|import\s+([\.\w]+))')
missing_imports = []
for d in PYTHON_DIRS:
    for py_file in d.rglob('*.py'):
        for lineno, line in enumerate(py_file.read_text(encoding='utf-8').splitlines(), start=1):
            m = import_rx.search(line)
            if not m:
                continue
            module = m.group(1) or m.group(2)
            # Resolve to a possible file path inside the repo
            if module.startswith('.'):
                # Relative import – resolve against the file's directory
                rel = module.lstrip('.')
                candidate = (py_file.parent / (rel.replace('.', os.sep) + '.py')).resolve()
            else:
                candidate = (PROJECT_ROOT / (module.replace('.', os.sep) + '.py')).resolve()
            if not candidate.is_file():
                missing_imports.append({
                    'file': str(py_file.relative_to(PROJECT_ROOT)),
                    'line': lineno,
                    'import': module,
                    'resolved': str(candidate.relative_to(PROJECT_ROOT))
                })

missing_md = "# Missing Modules Report\n\n"
if missing_imports:
    missing_md += "| File | Line | Import | Resolved Path |\n| ---- | ---- | ------ | ------------- |\n"
    for i in missing_imports:
        missing_md += f"| `{i['file']}` | {i['line']} | `{i['import']}` | `{i['resolved']}` |\n"
else:
    missing_md += "All imports resolved to existing files.\n"
write_md(PROJECT_ROOT / 'missing_modules_report.md', missing_md)

# ---------------------------------------------------------------------------
# 3. Stub detection (both Python and TypeScript)
# ---------------------------------------------------------------------------
stub_patterns = [r'TODO', r'return\s*\{\s*\}', r'return\s*\[\s*\]', r'pass\s*#\s*stub']
stub_rx = re.compile('|'.join(stub_patterns))
stub_entries = []
for base in PYTHON_DIRS + TS_DIRS:
    for fp in base.rglob('*.*'):
        if fp.suffix not in {'.py', '.ts', '.tsx'}:
            continue
        try:
            lines = fp.read_text(encoding='utf-8').splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, start=1):
            if stub_rx.search(line):
                stub_entries.append({
                    'file': str(fp.relative_to(PROJECT_ROOT)),
                    'line': i,
                    'code': line.strip()
                })

stub_md = "# Stub Modules Report\n\n"
if stub_entries:
    stub_md += "| File | Line | Code Snippet |\n| ---- | ---- | ------------ |\n"
    for e in stub_entries:
        snippet = e['code'].replace('|', '\\|')
        stub_md += f"| `{e['file']}` | {e['line']} | `{snippet}` |\n"
else:
    stub_md += "No stub patterns detected.\n"
write_md(PROJECT_ROOT / 'stub_modules_report.md', stub_md)

print('Audit reports generated:')
print('- documentation_report.md')
print('- missing_modules_report.md')
print('- stub_modules_report.md')
