#!/usr/bin/env python3
"""Static manuscript checks for unsupported wording, balanced braces, and local inputs."""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
MANUSCRIPT = os.path.join(ROOT, "revision_v2", "manuscript")
MAIN = os.path.join(MANUSCRIPT, "main.tex")
OUT = os.path.join(MANUSCRIPT, "static_audit.json")

FORBIDDEN = [
    "production-ready",
    "proves that AuthGuard-7702 can be seamlessly",
    "without degrading the user experience",
    "declarative analyses are powerful, they are computationally intensive",
    "establishes a robust, highly efficient",
    "compound flooding condition remain unresolved",
    "significantly recovers detection performance while reducing false positives",
]


def main():
    text = open(MAIN).read()
    forbidden_hits = [phrase for phrase in FORBIDDEN if phrase.lower() in text.lower()]
    # Strip comments and escaped braces for a bounded structural check.
    code = "\n".join(re.split(r"(?<!\\)%", line, maxsplit=1)[0]
                     for line in text.splitlines())
    code = code.replace(r"\{", "").replace(r"\}", "")
    balance = 0; min_balance = 0
    for char in code:
        if char == "{":
            balance += 1
        elif char == "}":
            balance -= 1; min_balance = min(min_balance, balance)
    missing_inputs = []
    for item in re.findall(r"\\input\{([^}]+)\}", text):
        path = os.path.join(MANUSCRIPT, item if item.endswith(".tex") else item + ".tex")
        if not os.path.exists(path):
            missing_inputs.append(item)
    graphic_roots = [MANUSCRIPT]
    for group in re.findall(r"\\graphicspath\{((?:\{[^}]+\})+)\}", text):
        graphic_roots.extend(os.path.normpath(os.path.join(MANUSCRIPT, p))
                             for p in re.findall(r"\{([^}]+)\}", group))
    missing_graphics = []
    for item in re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}", text):
        candidates = [os.path.join(root, item + ext) for root in graphic_roots
                      for ext in ["", ".pdf", ".png", ".jpg", ".jpeg"]]
        if not any(os.path.exists(path) for path in candidates):
            missing_graphics.append(item)
    missing_bibliographies = []
    for item in re.findall(r"\\bibliography\{([^}]+)\}", text):
        path = os.path.normpath(os.path.join(MANUSCRIPT, item + ".bib"))
        if not os.path.exists(path):
            missing_bibliographies.append(item)
    anonymous_author = bool(re.search(
        r"\\author\{\\IEEEauthorblockN\{Anonymous Authors\}\}", text))
    payload = dict(
        pass_=not forbidden_hits and balance == 0 and min_balance >= 0 and
              not missing_inputs and not missing_graphics and not missing_bibliographies and
              anonymous_author,
        forbidden_hits=forbidden_hits, brace_balance=balance,
        minimum_brace_balance=min_balance, missing_inputs=missing_inputs,
        missing_graphics=missing_graphics,
        missing_bibliographies=missing_bibliographies,
        anonymous_author=anonymous_author,
        note="Static source audit only; no TeX engine is installed on the current host.")
    payload["pass"] = payload.pop("pass_")
    with open(OUT, "w") as f:
        json.dump(payload, f, indent=2)
    print(json.dumps(payload, indent=2))
    if not payload["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
