"""Prototype: find tool references in prompt text that do not match the tool registry.

Usage: python detect.py REGISTRY_FILE TEXT_FILE...
REGISTRY_FILE: one tool name per line.
Rules (deliberately simple, deterministic):
  R1 phrase:   "the X tool", "`X` tool", "use X tool", "call X", "functions.X"  -> X must be a tool
  R2 near-miss: any `backticked` identifier that is not a tool but normalizes to,
               or is very similar to, a tool name (case, -/_, snake/camel, prefixes)
"""
import re, sys, difflib, json

reg = [l.strip() for l in open(sys.argv[1]) if l.strip()]
R = set(reg)

def norm(s):
    s = re.sub(r'(?<=[a-z0-9])([A-Z])', r'_\1', s)  # camel -> snake
    s = s.lower().replace('-', '_').replace('.', '_')
    s = re.sub(r'^(functions_|tools_|mcp__\w+?__)', '', s)
    return s

NR = {norm(t): t for t in reg}
IDENT = r'[A-Za-z_][A-Za-z0-9_.\-]{1,60}'
STOP = {'the','a','an','this','that','same','appropriate','right','correct','relevant','following','above','new','any','each','your','my','its','which','what','one','other','another','corresponding','specific','dedicated','available','built','search','file','shell','terminal','edit','read','write','web','todo','task','mcp','agent','subagent','memory','plan'}
phrase_res = [
    re.compile(r'\b(?:the|use|using|via|call|calling|invoke)\s+[`\'"]?(' + IDENT + r')[`\'"]?\s+tool\b', re.I),
    re.compile(r'`(' + IDENT + r')`\s+tool\b'),
    re.compile(r'\bfunctions\.(' + IDENT + r')'),
    re.compile(r'\btool_call:\s*(' + IDENT + r')'),
]
tick = re.compile(r'\\?`(' + IDENT + r')\\?`')

out = []
for path in sys.argv[2:]:
    try:
        text = open(path, encoding='utf-8', errors='ignore').read()
    except Exception:
        continue
    for lineno, line in enumerate(text.splitlines(), 1):
        seen = set()
        for rx in phrase_res:
            for m in rx.finditer(line):
                x = m.group(1).strip('.-')
                if x in R or x.lower() in STOP or x in seen:
                    continue
                seen.add(x)
                n = norm(x)
                sug = NR.get(n) or (difflib.get_close_matches(x, reg, 1, 0.7) or [None])[0]
                out.append(dict(rule='R1', file=path, line=lineno, ref=x, suggest=sug, ctx=line.strip()[:160]))
        for m in tick.finditer(line):
            x = m.group(1).strip('.-')
            if x in R or x in seen:
                continue
            n = norm(x)
            sug = NR.get(n)
            if not sug:
                c = difflib.get_close_matches(x, reg, 1, 0.82)
                sug = c[0] if c else None
            if sug:
                seen.add(x)
                out.append(dict(rule='R2', file=path, line=lineno, ref=x, suggest=sug, ctx=line.strip()[:160]))
        # R3: bare identifiers that look like tool names (snake_case or CamelCase)
        # and are near-misses of a registered tool (prefix/suffix/containment/similar)
        for m in re.finditer(r'(?<![\w./`-])([a-z]+(?:_[a-z0-9]+)+|[A-Z][a-z]+(?:[A-Z][a-z]+)+)(?![\w/`-])', line):
            x = m.group(1)
            if x in R or x in seen:
                continue
            n = norm(x)
            sug = NR.get(n)
            if not sug and '_' in x:
                for t in reg:
                    nt = norm(t)
                    if len(nt) >= 5 and (n.startswith(nt + '_') or n.endswith('_' + nt)) and n != nt:
                        sug = t
                        break
            if not sug and '_' in x:
                c = difflib.get_close_matches(n, list(NR), 1, 0.85)
                sug = NR[c[0]] if c else None
            if sug:
                seen.add(x)
                out.append(dict(rule='R3', file=path, line=lineno, ref=x, suggest=sug, ctx=line.strip()[:160]))
for o in out:
    print(json.dumps(o, ensure_ascii=False))
