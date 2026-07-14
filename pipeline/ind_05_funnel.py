#!/usr/bin/env python3
"""
ind_05_funnel.py -- assemble the T2-T4 funnel, per-target classification with documented
maliciousness judgments, and the deliverable CSVs + funnel figure.

Maliciousness judgments are MANUAL (T3), documented per target with reasons, and are
independent of the USENIX static rule (structure + on-chain convergence/drain state +
manual interface reading). Confidence is conservative: legitimate-wallet interfaces
(ERC-1271 isValidSignature, ERC-721 receiver, proxy initialize) route to NOT-malicious/uncertain.
"""
import os, sys, json, csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REP = os.path.join(ROOT, "reports")

# ---- documented per-target manual maliciousness triage (T3), reasons recorded ----
# confidence in {malicious_high, malicious_medium, uncertain, likely_benign}
JUDGE = {
 "0x0727ca41efc85f75cef26ee48f825893b4836786": ("malicious_high",
    "39 independent blacklisted accounts converge on this 1.25KB forwarder; all sampled "
    "delegating accounts active (nonce>0) and swept to ~0 balance: classic shared sweeper."),
 "0xa3560611a7acd82481193aa210b56cae847ac491": ("malicious_medium",
    "MinHash sim 0.961 to USENIX-793 malicious (near-duplicate of a known drainer family); "
    "delegating account active and swept."),
 "0xb6785b782571980b3ddb5d40659f4861ff15aa02": ("malicious_high",
    "Byte-identical (sim 1.000) to a USENIX-793 malicious contract (address also in 793)."),
 "0x5459 40f521452b4138b360ad55e28667ea07a8bf".replace(" ", ""): ("malicious_medium",
    "Exposes ERC-20 transfer(a9059cbb)+balanceOf(70a08231) with 3 CALLs and a dynamic sink; "
    "delegating account active and swept: plausible token sweeper. Thin (1 victim)."),
 "0x88cf071b4bf5facab6712070a671f71282188d46": ("uncertain",
    "Unusual selectors (169f67ed/6c354f05/b269681d), 2 SSTORE, single CALL, sink=0xffff..ff; "
    "asset-moving path not clearly established; 2 victims. Insufficient to confirm."),
 "0x99c0b9dd3ead519927e29af2c2a39ae43dfb9dce": ("uncertain",
    "Has initialize(address) (c4d66de8) proxy/wallet initializer alongside transfer/balanceOf; "
    "consistent with a legit upgradeable smart-account. Cannot confirm malicious."),
 "0xa845c74344fc9405b1fcf712f04668979573c1bf": ("likely_benign",
    "Implements ERC-1271 isValidSignature(1626ba7e), ERC-721 onERC721Received(150b7a02), "
    "ERC-165 supportsInterface(01ffc9a7): hallmarks of a LEGITIMATE smart-account wallet, "
    "not a drainer. A blacklisted account delegating here does not make the delegate malicious."),
 "0xeb96daa7a587ea46ead1a2c2ed596cddd279ce54": ("uncertain",
    "8.7KB contract exposing Uniswap-router selectors (791ac947/d06ca61f) + approve/transferFrom; "
    "resembles a trading/wallet contract more than a minimal drainer. Cannot confirm malicious."),
 "0x0e04736a85433445ef602d07946671685ec94647": ("uncertain",
    "Minimal USDT(dac17f95) forwarder, 0 selectors, 7 CALLs, 2 victims swept -> structurally a "
    "USDT sweeper, BUT this address is already present in the USENIX dataset as benign_cleared "
    "(a TRAINING NEGATIVE): it is NOT absent from training, and its label is contested. Excluded "
    "from the novel-malicious set; flagged as a possible rule false-clear for separate study."),
}


def main():
    tgts = list(csv.DictReader(open(os.path.join(REP, "independent_targets.csv"))))
    gc = list(csv.DictReader(open(os.path.join(REP, "getcode_mainnet.csv"))))
    inv = json.load(open(os.path.join(REP, "inventory.json")))
    gcs = json.load(open(os.path.join(REP, "getcode_summary.json")))

    for t in tgts:
        conf, reason = JUDGE.get(t["target"], ("uncertain", "no judgment"))
        t["maliciousness_confidence"] = conf
        t["maliciousness_reason"] = reason

    def is_mal(t):
        return t["maliciousness_confidence"] in ("malicious_high", "malicious_medium")

    # ---- funnel ----
    n_black = inv["union_unique"]
    n_deleg_accts = gcs["is_7702_designator"]
    n_targets = len(tgts)
    n_usage_verified = n_targets  # all 9 have on-chain delegation evidence (I3)
    confirmed_mal = [t for t in tgts if is_mal(t)]
    not_in_793 = [t for t in confirmed_mal if t["in_usenix_793"] in ("False", "false", False)]
    not_exact = [t for t in not_in_793 if t["exact_overlap"] in ("False", "false", False)]
    not_family = [t for t in not_exact if t["novelty_subset"] not in ("known_family", "exact_known")]
    truly_novel = [t for t in not_family if t["novelty_subset"] == "truly_novel"]

    funnel = {
        "blacklist_unique_addresses": n_black,
        "with_verified_7702_delegate_usage(accounts delegating)": n_deleg_accts,
        "unique_delegate_targets(candidate delegates, I3-verified)": n_targets,
        "independently_confirmed_malicious(I4 medium+)": len(confirmed_mal),
        "confirmed_malicious_not_in_USENIX_793": len(not_in_793),
        "confirmed_malicious_not_exact_bytecode_overlap": len(not_exact),
        "confirmed_malicious_not_family_overlap": len(not_family),
        "confirmed_malicious_TRULY_NOVEL": len(truly_novel),
    }
    # subset census over ALL 9 targets (independent of confidence)
    from collections import Counter
    subset_census = dict(Counter(t["novelty_subset"] for t in tgts))
    conf_census = dict(Counter(t["maliciousness_confidence"] for t in tgts))

    # ---- deliverable CSVs ----
    cols = ["target", "n_delegating_blacklisted", "code_bytes", "bytecode_sha256",
            "in_usenix_793", "in_usenix_dataset", "exact_overlap", "max_minhash_sim_to_793",
            "nearest_793", "novelty_subset", "maliciousness_confidence", "maliciousness_reason",
            "usage_evidence_example"]

    def write(path, rows):
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader()
            for r in rows:
                w.writerow(r)

    write(os.path.join(ROOT, "independent_malicious.csv"), confirmed_mal)
    write(os.path.join(ROOT, "uncertain_candidates.csv"),
          [t for t in tgts if t["maliciousness_confidence"] in ("uncertain", "likely_benign")])
    # unverified = blacklist addresses with contract code but NO delegate-usage evidence
    contract_no_usage = [{"target": r["address"], "code_bytes": r["code_bytes"],
                          "note": "contract code on mainnet but NO EIP-7702 delegate-usage evidence"}
                         for r in gc if r["class"] == "CONTRACT_CODE"]
    with open(os.path.join(ROOT, "unverified_candidates.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["target", "code_bytes", "note"]); w.writeheader()
        for r in contract_no_usage:
            w.writerow(r)

    out = dict(funnel=funnel, subset_census_over_9_targets=subset_census,
               maliciousness_census_over_9_targets=conf_census,
               n_unverified_contract_addresses=len(contract_no_usage),
               truly_novel_confirmed_targets=[t["target"] for t in truly_novel])
    with open(os.path.join(REP, "funnel.json"), "w") as f:
        json.dump(out, f, indent=2)

    # ---- funnel figure ----
    labels = ["blacklist\naddresses", "7702-delegating\naccounts", "unique delegate\ntargets (I3)",
              "confirmed\nmalicious (I4)", "not in\nUSENIX-793", "not exact\noverlap",
              "not family\noverlap", "TRULY\nNOVEL"]
    vals = list(funnel.values())
    fig, ax = plt.subplots(figsize=(8.4, 4.6))
    bars = ax.bar(range(len(vals)), vals, color="#2a78d6")
    ax.set_yscale("symlog")
    for b, v in zip(bars, vals):
        ax.text(b.get_x()+b.get_width()/2, v*1.1+0.3, str(v), ha="center", fontsize=9)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("count (symlog)")
    ax.set_title("Independent-set funnel: scamsonethereum blacklist → truly-novel confirmed "
                 "malicious EIP-7702 delegates")
    fig.tight_layout()
    os.makedirs(os.path.join(ROOT, "figures"), exist_ok=True)
    fig.savefig(os.path.join(ROOT, "figures", "fig_independent_funnel.png"), dpi=140)
    plt.close(fig)

    print("=== FUNNEL ===")
    for k, v in funnel.items():
        print(f"  {v:>7}  {k}")
    print("subset census (all 9 targets):", subset_census)
    print("maliciousness census (all 9):", conf_census)
    print("unverified contract addresses:", len(contract_no_usage))
    print("truly-novel confirmed:", [t['target'] for t in truly_novel])


if __name__ == "__main__":
    main()
