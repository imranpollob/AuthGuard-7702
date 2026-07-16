#!/usr/bin/env python3
"""Replace host-specific absolute manifest keys with repository-relative paths."""
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
RV2 = os.path.join(ROOT, "revision_v2")


def clean_key(key):
    key = str(key).replace("\\", "/")
    marker = "/AuthGuard-7702/"
    if marker in key:
        return key.split(marker, 1)[1]
    # Older manifests were generated from an extracted checkout whose directory name was
    # not AuthGuard-7702. Recover known repository anchors instead of collapsing to basename.
    for anchor in ["revision_v2/", "paper_build/"]:
        token = "/" + anchor
        if token in key:
            return anchor + key.split(token, 1)[1]
    absolute = os.path.abspath(key)
    try:
        if os.path.commonpath([ROOT, absolute]) == ROOT:
            return os.path.relpath(absolute, ROOT).replace("\\", "/")
    except ValueError:
        pass
    return os.path.basename(key)


def main():
    changed = []
    for directory, _subdirs, files in os.walk(os.path.join(RV2, "results")):
        if "manifest.json" not in files:
            continue
        path = os.path.join(directory, "manifest.json")
        with open(path) as f:
            payload = json.load(f)
        before = json.dumps(payload, sort_keys=True)
        for field in ["inputs", "outputs"]:
            if field in payload:
                payload[field] = {clean_key(k): v for k, v in payload[field].items()}
        payload["path_policy"] = "repository-relative; external inputs reduced to basename"
        if json.dumps(payload, sort_keys=True) != before:
            with open(path, "w") as f:
                json.dump(payload, f, indent=2)
                f.write("\n")
            changed.append(os.path.relpath(path, ROOT))
    print(f"[sanitize-manifests] updated {len(changed)} manifests")
    for path in changed:
        print(path)


if __name__ == "__main__":
    main()
