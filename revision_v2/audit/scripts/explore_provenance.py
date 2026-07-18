#!/usr/bin/env python3
"""Exploratory provenance checks for the AuthGuardBench-7702 audit (read-only)."""
import hashlib
import json
import os
import sys
import zipfile

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
USENIX = os.path.join(ROOT, "USENIX EIP-7702 artifact")
PH = os.path.join(ROOT, "PhishingHook Zenodo artifact")


def norm(raw):
    h = str(raw).lower().strip()
    if h.startswith("0x"):
        h = h[2:]
    return h[:-1] if len(h) % 2 else h


def sha(h):
    return hashlib.sha256(h.encode()).hexdigest()


def main():
    cap = pd.read_csv(os.path.join(ROOT, "capability_dataset.csv"))
    cap["bc"] = cap["bytecode"].map(norm)
    cap["h"] = cap["bc"].map(sha)
    cap["hexlen"] = cap["bytecode"].astype(str).str.len()
    out = {}
    out["cap_class_counts"] = cap["class"].value_counts().to_dict()

    # 1. benign_cleared derivation from USENIX candidate pool
    cwb = pd.read_excel(os.path.join(USENIX, "eoa_detect", "get_code",
                                     "contracts_with_bytecode.xlsx"))
    out["usenix_cwb_columns"] = cwb.columns.tolist()
    cwb.columns = [c.strip().lower() for c in cwb.columns]
    addr_col = [c for c in cwb.columns if "address" in c][0]
    cwb["key"] = cwb["chain"].astype(str).str.lower() + ":" + cwb[addr_col].astype(str).str.lower()
    cwb["bc"] = cwb["bytecode"].map(norm)
    cwb["empty"] = cwb["bc"].isin(["", "0x", "nan"]) | (cwb["bc"].str.len() < 4)
    out["usenix_cwb_rows"] = len(cwb)
    out["usenix_cwb_unique_keys"] = int(cwb["key"].nunique())
    out["usenix_cwb_empty_bytecode"] = int(cwb["empty"].sum())

    det = []
    decoder = json.JSONDecoder()
    with open(os.path.join(USENIX, "eoa_detect", "detect_result.jsonl")) as fh:
        for line in fh:
            line = line.strip()
            pos = 0
            while pos < len(line):
                obj, end = decoder.raw_decode(line, pos)
                det.append(obj)
                pos = end
                while pos < len(line) and line[pos] in " \t,":
                    pos += 1
    det_keys = set()
    for row in det:
        chain = row["path"].split("/")[1]
        det_keys.add(chain.lower() + ":" + row["address"].lower())
    out["usenix_detected_keys"] = len(det_keys)

    cap["key"] = cap["chain"].astype(str).str.lower() + ":" + cap["address"].astype(str).str.lower()
    mal = cap[cap["class"] == "malicious"]
    cle = cap[cap["class"] == "benign_cleared"]
    out["malicious_in_detected"] = int(mal["key"].isin(det_keys).sum())
    out["cleared_in_detected"] = int(cle["key"].isin(det_keys).sum())
    out["malicious_in_cwb"] = int(mal["key"].isin(set(cwb["key"])).sum())
    out["cleared_in_cwb"] = int(cle["key"].isin(set(cwb["key"])).sum())
    # why 1657 not 1892?
    cand_clear = cwb[~cwb["key"].isin(det_keys)]
    out["cwb_not_detected"] = len(cand_clear)
    out["cwb_not_detected_nonempty"] = int((~cand_clear["empty"]).sum())
    out["cwb_not_detected_unique_nonempty"] = int(
        cand_clear.loc[~cand_clear["empty"], "key"].nunique())
    missing = cand_clear.loc[~cand_clear["empty"] & ~cand_clear["key"].isin(set(cle["key"]))]
    out["cwb_cleared_missing_from_cap"] = len(missing)
    # do missing rows look like designators / duplicates?
    dup_keys = cand_clear["key"].duplicated().sum()
    out["cand_clear_dup_keys"] = int(dup_keys)
    if len(missing):
        out["missing_examples"] = missing["key"].head(10).tolist()
        out["missing_len_stats"] = missing["bc"].str.len().describe().to_dict()

    # 2. Excel truncation: hexlen at cap 32767
    for cls, sub in cap.groupby("class"):
        out[f"len_cap_{cls}"] = {
            "max_hexlen": int(sub["hexlen"].max()),
            "n_at_32767": int((sub["hexlen"] == 32767).sum()),
            "n_ge_32700": int((sub["hexlen"] >= 32700).sum()),
            "n_odd_hexlen": int((sub["bytecode"].astype(str).str.replace("0x", "", regex=False)
                                  .str.len() % 2 == 1).sum()),
            "n_designator": int(sub["bc"].str.match(r"^ef0100[0-9a-f]{40}$").sum()),
        }
    out["cwb_n_at_32767"] = int((cwb["bytecode"].astype(str).str.len() == 32767).sum())

    # 3. hex files in output.zip: full bytecode available for truncated rows?
    zpath = os.path.join(USENIX, "eoa_detect", "get_code", "output.zip")
    zf = zipfile.ZipFile(zpath)
    names = zf.namelist()
    out["outputzip_files"] = len(names)
    out["outputzip_sample"] = names[:3]
    # check a truncated row
    trunc = cap[cap["hexlen"] >= 32700].head(3)
    checks = []
    name_index = {}
    for n in names:
        parts = n.replace("\\", "/").split("/")
        if len(parts) >= 2 and parts[-1].endswith(".hex"):
            name_index[(parts[-2].lower(), parts[-1][:-4].lower())] = n
    out["outputzip_indexed"] = len(name_index)
    for _, row in trunc.iterrows():
        k = (str(row["chain"]).lower(), str(row["address"]).lower())
        if k in name_index:
            raw = zf.read(name_index[k]).decode().strip()
            checks.append({
                "key": row["key"], "cap_hexlen": int(row["hexlen"]),
                "hex_file_len": len(raw),
                "prefix_match": norm(raw)[:1000] == row["bc"][:1000],
            })
        else:
            checks.append({"key": row["key"], "hex_file": "MISSING"})
    out["truncation_repair_checks"] = checks

    # 4. benign_general provenance: PhishingHook unique benign bytecodes
    ph_path = os.path.join(PH, "artifact", "dataset", "bytecodes", "unique_bytecodes",
                           "unique_benign_bytecodes.txt")
    ph_hashes = set()
    with open(ph_path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                ph_hashes.add(sha(norm(line)))
    gen = cap[cap["class"] == "benign_general"]
    out["phishinghook_unique_benign"] = len(ph_hashes)
    out["benign_general_hash_in_phishinghook"] = int(gen["h"].isin(ph_hashes).sum())
    out["benign_general_chains"] = gen["chain"].value_counts().to_dict()
    out["cleared_chains"] = cle["chain"].value_counts().to_dict()
    out["malicious_chains"] = mal["chain"].value_counts().to_dict()

    # 5. benign_AA provenance
    aa = cap[cap["class"] == "benign_AA"]
    b7702 = pd.read_csv(os.path.join(ROOT, "benign_7702_bytecode.csv"))
    b7702["h"] = b7702["bytecode"].map(lambda x: sha(norm(x)))
    out["benign_AA_rows"] = len(aa)
    out["benign_AA_hash_in_fetched"] = int(aa["h"].isin(set(b7702["h"])).sum())
    out["benign_AA_addrs"] = aa[["chain", "address"]].to_dict("records")

    # 6. scamsonethereum blacklist overlap (independent evidence)
    bl = set()
    for f in ["master_blacklist_set.txt", "all_across_hard.txt"]:
        with open(os.path.join(ROOT, "scamsonethereum-main", f)) as fh:
            for line in fh:
                a = line.strip().lower()
                if a.startswith("0x") and len(a) == 42:
                    bl.add(a)
    out["blacklist_size"] = len(bl)
    cap["addr_l"] = cap["address"].astype(str).str.lower()
    for cls, sub in cap.groupby("class"):
        out[f"blacklist_overlap_{cls}"] = int(sub["addr_l"].isin(bl).sum())

    # 7. matched column vs class
    sam = pd.read_excel(os.path.join(USENIX, "analysis_information",
                                     "sa_contract_malicious.xlsx"))
    sam["key"] = sam["chain"].astype(str).str.lower() + ":" + \
        sam["delegated_address"].astype(str).str.lower()
    matched = set(sam.loc[sam["matched"] == "matched", "key"])
    out["matched_total"] = len(matched)
    out["malicious_matched"] = int(mal["key"].isin(matched).sum())
    out["cleared_matched"] = int(cle["key"].isin(matched).sum())

    # 8. PhishingHook phishing overlap with dataset (contamination / extra evidence)
    php = os.path.join(PH, "artifact", "dataset", "bytecodes", "unique_bytecodes",
                       "unique_phishing_bytecodes.txt")
    ph_mal_hashes = set()
    with open(php) as fh:
        for line in fh:
            line = line.strip()
            if line:
                ph_mal_hashes.add(sha(norm(line)))
    for cls, sub in cap.groupby("class"):
        out[f"phishinghook_phishing_hash_overlap_{cls}"] = int(sub["h"].isin(ph_mal_hashes).sum())
    # address-level phishing overlap
    ph_addr = set()
    with open(os.path.join(PH, "artifact", "dataset", "contracts", "unique_contracts",
                           "unique_phishing.txt")) as fh:
        for line in fh:
            a = line.strip().lower()
            if a.startswith("0x"):
                ph_addr.add(a)
    for cls, sub in cap.groupby("class"):
        out[f"phishinghook_phishing_addr_overlap_{cls}"] = int(sub["addr_l"].isin(ph_addr).sum())

    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    sys.exit(main())
