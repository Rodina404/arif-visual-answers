"""Tick every checkbox in README section '### Phase N'. Usage: python tools/tick.py N"""
import sys

n = sys.argv[1]
s = open("README.md", encoding="utf-8").read()
start = s.index(f"### Phase {n} ")
end = s.find("\n### ", start + 5)
end = len(s) if end < 0 else end
s = s[:start] + s[start:end].replace("- [ ]", "- [x]") + s[end:]
open("README.md", "w", encoding="utf-8", newline="").write(s)
