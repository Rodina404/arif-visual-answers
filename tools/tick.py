"""Tick every checkbox in docs/BUILD_SPEC.md section '### Phase N'. Usage: python tools/tick.py N"""
import sys

n = sys.argv[1]
s = open("docs/BUILD_SPEC.md", encoding="utf-8").read()
start = s.index(f"### Phase {n} ")
end = s.find("\n### ", start + 5)
end = len(s) if end < 0 else end
s = s[:start] + s[start:end].replace("- [ ]", "- [x]") + s[end:]
open("docs/BUILD_SPEC.md", "w", encoding="utf-8", newline="").write(s)
