#!/usr/bin/env python3
"""Machine-readable anonymity audit for manuscript and anonymous artifact inventory."""
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
RV2 = os.path.join(ROOT, "revision_v2")
OUT = os.path.join(RV2, "audits", "anonymity_audit.json")
TEXT_EXTENSIONS = {".json", ".md", ".tex", ".txt", ".csv", ".sh", ".py"}
FORBIDDEN = ["/home/pollmix", "/Users/", "file://"]


def main():
    hits = []
    # Match the anonymous payload enumerated by build_artifact_manifest.py. The audit
    # source itself necessarily contains the forbidden-pattern literals and is skipped.
    roots = [os.path.join(RV2, name) for name in
             ["experiments", "protocols", "results", "audits", "reports", "planning",
              "manuscript"]]
    roots += [os.path.join(RV2, "artifact", "label_audit"),
              os.path.join(RV2, "artifact", "artifact_manifest.json")]
    roots += [os.path.join(RV2, fn) for fn in os.listdir(RV2)
              if fn.startswith("final_") and fn.endswith(".md")]
    self_path = os.path.abspath(__file__)
    reviewer_key = os.path.join(RV2, "artifact", "label_audit",
                                "REVIEWER_KEY_do_not_distribute.csv")
    for root in roots:
        paths = [root] if os.path.isfile(root) else [
            os.path.join(dp, fn) for dp, _dirs, files in os.walk(root) for fn in files]
        for path in paths:
            if (os.path.abspath(path) in {self_path, reviewer_key} or
                    os.path.splitext(path)[1] not in TEXT_EXTENSIONS or path.endswith(".log")):
                continue
            try:
                text = open(path, errors="replace").read()
            except OSError:
                continue
            for pattern in FORBIDDEN:
                if pattern in text:
                    hits.append(dict(path=os.path.relpath(path, ROOT), pattern=pattern))
    main_tex = open(os.path.join(RV2, "manuscript", "main.tex")).read()
    anonymous_author = "Anonymous Authors" in main_tex
    artifact_manifest = open(os.path.join(RV2, "artifact", "artifact_manifest.json")).read()
    reviewer_key_listed = "REVIEWER_KEY_do_not_distribute.csv" in artifact_manifest
    payload = dict(pass_=not hits and anonymous_author and not reviewer_key_listed,
                   anonymous_author=anonymous_author,
                   forbidden_hits=hits,
                   reviewer_key_present_locally=os.path.exists(os.path.join(
                       RV2, "artifact", "label_audit", "REVIEWER_KEY_do_not_distribute.csv")),
                   reviewer_key_listed_in_artifact=reviewer_key_listed,
                   reviewer_key_policy="retained locally; excluded from anonymous artifact ledger")
    payload["pass"] = payload.pop("pass_")
    with open(OUT, "w") as f:
        json.dump(payload, f, indent=2)
    print(json.dumps(payload, indent=2))
    if not payload["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
