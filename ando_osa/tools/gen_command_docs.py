"""Generate docs/COMMANDS.md from the command table."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from ando_osa.commands import COMMANDS

out = ["# AQ6315 command reference (generated from src/ando_osa/commands.py)", "",
       "Page = manual chapter 9 page. `set_` methods validate ranges before sending.", ""]
groups = {}
for c in COMMANDS.values():
    groups.setdefault(c.group, []).append(c)
for g, cs in groups.items():
    out += [f"## {g}", "", "| Python | Sends | Query | Range / options | Page | Description |", "|---|---|---|---|---|---|"]
    for c in cs:
        if c.kind == "action":
            py = f"`{c.name}()`"
        elif c.kind == "query":
            py = f"`get_{c.name}()`"
        else:
            py = f"`set_{c.name}(x)`" + (f" / `get_{c.name}()`" if c.query else "")
        rng = (f"{c.lo} .. {c.hi} {c.unit}" + (f" (or {c.special})" if c.special else "")) if c.kind == "number" \
            else (", ".join(map(str, c.enum)) if c.enum else "")
        out.append(f"| {py} | `{c.code}{'<x>' if c.kind in ('number','choice') else ''}` | `{c.query or ''}` | {rng} | {c.page} | {c.doc.replace('|','/')} |")
    out.append("")
open(os.path.join(os.path.dirname(__file__), "..", "docs", "COMMANDS.md"), "w").write("\n".join(out))
print("wrote docs/COMMANDS.md")
