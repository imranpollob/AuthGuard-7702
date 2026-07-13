import jsonlines
import json
import pandas as pd

# Final Victim Matching and Ethical Considerations.
# After identifying attacker contracts, we further reuse our cross_match.py 
# script to match their potential victims based on transaction interactions. The final
#  matched results are stored in result.xlsx. For ethical considerations, we 
# have intentionally hidden the addresses of victim contracts to prevent potential misuse. 
# Researchers can manually verify the results by comparing result.xlsx and mid_matched_results.xlsx.

# Step 1: Read flashloan.jsonl and build a mapping: address -> set of function selectors
flashloan_funcs = {}

with jsonlines.open("./../composite_detect/decompile/AM_Detect_FlashloanCall.jsonl", "r") as reader:
    for item in reader:
        addr = item["address"].lower()
        sigs = set()
        for r in item.get("result", []):
            func_sig = r[4]
            sigs.add(func_sig)
        if sigs:
            flashloan_funcs[addr] = sigs

print(f"[INFO] Loaded {len(flashloan_funcs)} addresses with flashloan-related function selectors.")

# Step 2: Load related contracts table
related_df = pd.read_excel("related_contracts.xlsx")
related_df['target_address'] = related_df['target_address'].str.lower()
related_df['related_contracts'] = related_df['related_contracts'].apply(eval)  # convert string to list

# Step 3: Match function selectors in related contracts
matched_results = []

for addr, target_sigs in flashloan_funcs.items():
    row = related_df[related_df['target_address'] == addr]
    if row.empty:
        continue
    related_contracts = row.iloc[0]['related_contracts']
    related_contracts_set = set(related_contracts)

    with jsonlines.open("./../composite_detect/decompile/AM_FunctionSelector.jsonl", "r") as reader:
        for item in reader:
            contract_addr = item["address"].lower()
            if contract_addr not in related_contracts_set:
                continue

            result = item.get("result", [])
            selectors = {r[1] for r in result if len(r) >= 2}
            matched_sigs = selectors & target_sigs

            if matched_sigs:
                matched_results.append({
                    "target_address": addr,
                    "related_contract": contract_addr,
                    "matched_selectors": list(matched_sigs),
                    "row": item
                })

print(f"[INFO] Matching completed. Total matched entries: {len(matched_results)}")

# Step 4: Export results
matched_df = pd.DataFrame(matched_results)
matched_df.to_excel("matched_results.xlsx", index=False)
print("[INFO] Results saved to matched_results.xlsx")

