"""Task 1: independently validate the recovered EIP-7702 authorization signers.

Two independent checks, neither of which reuses the pipeline's recovery path
(revision_v3/src/temporal/authorization.py -> rlp + eth_keys + eth_utils):

  CHECK A -- independent reimplementation.
      Hand-rolled RLP encoder, keccak from pycryptodome (not eth_hash/eth_utils), and ECDSA
      public-key recovery from coincurve directly (not eth_keys.datatypes.Signature). If the
      signing payload keccak(0x05 || rlp([chain_id, address, nonce])) were wrong, both
      implementations would have to be wrong in exactly the same way to agree.

  CHECK B -- on-chain ground truth.
      An accepted EIP-7702 authorization sets the AUTHORITY's account code to the delegation
      designator 0xef0100 || delegate_address. So for a sampled authorization at block B we
      query eth_getCode(recovered_authority, block=B) and require it to equal
      ef0100 || delegate. This does not re-derive anything -- it asks the chain whether the
      address we recovered is in fact the account that got delegated. A wrong recovery yields
      an unrelated address, which will essentially never carry that exact designator.

      Authorizations can legitimately be *invalid* (nonce already consumed, authority
      re-delegated later in the same block), so CHECK B is scored only over samples where the
      recovered authority has exactly one authorization in that block, and any mismatch is
      itemized rather than averaged away.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import coincurve  # noqa: E402
import pandas as pd  # noqa: E402
from Crypto.Hash import keccak as _pycrypto_keccak  # noqa: E402

from lib.config import load_config  # noqa: E402
from lib.repo_paths import add_revision_v3_src_to_path  # noqa: E402

add_revision_v3_src_to_path()
from temporal.rpc_client import ChainClient, RpcError  # noqa: E402

SECP256K1_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141


# ---------------------------------------------------------------- independent primitives
def keccak256(data: bytes) -> bytes:
    h = _pycrypto_keccak.new(digest_bits=256)
    h.update(data)
    return h.digest()


def rlp_encode_bytes(value: bytes) -> bytes:
    if len(value) == 1 and value[0] < 0x80:
        return value
    if len(value) <= 55:
        return bytes([0x80 + len(value)]) + value
    length_bytes = len(value).to_bytes((len(value).bit_length() + 7) // 8, "big")
    return bytes([0xB7 + len(length_bytes)]) + length_bytes + value


def rlp_encode_int(value: int) -> bytes:
    if value == 0:
        return rlp_encode_bytes(b"")
    return rlp_encode_bytes(value.to_bytes((value.bit_length() + 7) // 8, "big"))


def rlp_encode_list(items: list[bytes]) -> bytes:
    payload = b"".join(items)
    if len(payload) <= 55:
        return bytes([0xC0 + len(payload)]) + payload
    length_bytes = len(payload).to_bytes((len(payload).bit_length() + 7) // 8, "big")
    return bytes([0xF7 + len(length_bytes)]) + length_bytes + payload


def as_int(value) -> int:
    if isinstance(value, str):
        return int(value, 16) if value.lower().startswith("0x") else int(value)
    return int(value)


def independent_recover(chain_id, delegate: str, nonce, y_parity, r, s) -> str:
    """Fully independent EIP-7702 authority recovery. Returns lowercase 0x-address."""
    chain_int, nonce_int = as_int(chain_id), as_int(nonce)
    parity, r_int, s_int = as_int(y_parity), as_int(r), as_int(s)
    if parity not in (0, 1):
        raise ValueError(f"bad y_parity {parity}")
    if not 0 < r_int < SECP256K1_N:
        raise ValueError("r out of range")
    if not 0 < s_int <= SECP256K1_N // 2:
        raise ValueError("s violates EIP-2 low-s")
    delegate_bytes = bytes.fromhex(delegate.lower().removeprefix("0x"))
    if len(delegate_bytes) != 20:
        raise ValueError("delegate must be 20 bytes")

    payload = rlp_encode_list([
        rlp_encode_int(chain_int),
        rlp_encode_bytes(delegate_bytes),
        rlp_encode_int(nonce_int),
    ])
    message_hash = keccak256(b"\x05" + payload)

    signature = r_int.to_bytes(32, "big") + s_int.to_bytes(32, "big") + bytes([parity])
    public_key = coincurve.PublicKey.from_signature_and_message(signature, message_hash, hasher=None)
    uncompressed = public_key.format(compressed=False)  # 0x04 || X || Y
    return "0x" + keccak256(uncompressed[1:])[-20:].hex()


def main():
    cfg = load_config()
    run_id = cfg["run_id"]
    ap = argparse.ArgumentParser()
    ap.add_argument("--chain", default="ethereum")
    ap.add_argument("--sample-size", type=int, default=150)
    ap.add_argument("--onchain-checks", type=int, default=120)
    ap.add_argument("--seed", type=int, default=7702)
    args = ap.parse_args()

    enriched_path = os.path.join(
        cfg["_resolved_paths"]["collected_delegates"],
        f"{run_id}_{args.chain}_authorizations_enriched.csv",
    )
    df = pd.read_csv(enriched_path, dtype=str)
    df = df[df["recovered_authority"].notna()]
    sample = df.sample(n=min(args.sample_size, len(df)), random_state=args.seed).reset_index(drop=True)

    # ---------------- CHECK A ----------------
    a_match, a_mismatch, a_error = 0, [], []
    for _, row in sample.iterrows():
        try:
            independent = independent_recover(
                row["authorization_chain_id"], row["delegate_address"],
                row["authorization_nonce"], row["authorization_y_parity"],
                row["authorization_r"], row["authorization_s"],
            )
        except Exception as e:  # noqa: BLE001
            a_error.append({"tx_hash": row["tx_hash"], "error": f"{type(e).__name__}: {e}"})
            continue
        if independent == str(row["recovered_authority"]).lower():
            a_match += 1
        else:
            a_mismatch.append({
                "tx_hash": row["tx_hash"], "block": row["block_number"],
                "pipeline": row["recovered_authority"], "independent": independent,
            })

    # ---------------- CHECK B ----------------
    # only authorities appearing exactly once in their block (unambiguous end-of-block state)
    per_block_authority = df.groupby(["block_number", "recovered_authority"]).size()
    unique_pairs = set(per_block_authority[per_block_authority == 1].index)
    eligible = sample[sample.apply(
        lambda r: (r["block_number"], r["recovered_authority"]) in unique_pairs, axis=1)]
    onchain_sample = eligible.head(args.onchain_checks)

    client = ChainClient(args.chain)
    b_confirmed, b_other_designator, b_no_code, b_rpc_error = 0, [], 0, []
    for _, row in onchain_sample.iterrows():
        authority = str(row["recovered_authority"])
        block_tag = hex(int(row["block_number"]))
        try:
            code = client.get_code(authority, block_tag=block_tag)
        except RpcError as e:
            b_rpc_error.append({"authority": authority, "error": str(e)})
            continue
        expected = "0xef0100" + str(row["delegate_address"]).lower().removeprefix("0x")
        if (code or "").lower() == expected:
            b_confirmed += 1
        elif (code or "0x").lower().startswith("0xef0100"):
            b_other_designator.append({
                "authority": authority, "block": row["block_number"],
                "expected_delegate": row["delegate_address"],
                "observed_designator": code,
            })
        else:
            b_no_code += 1

    n_b = len(onchain_sample) - len(b_rpc_error)
    report = {
        "run_id": run_id, "chain": args.chain,
        "check_a_independent_reimplementation": {
            "n_sampled": int(len(sample)),
            "n_agree": a_match,
            "n_disagree": len(a_mismatch),
            "n_error": len(a_error),
            "agreement_rate": a_match / len(sample) if len(sample) else None,
            "disagreements": a_mismatch[:20],
            "errors": a_error[:20],
        },
        "check_b_onchain_designator": {
            "n_eligible_unique_authority_per_block": int(len(eligible)),
            "n_checked": int(n_b),
            "n_confirmed_exact_designator": b_confirmed,
            "n_authority_holds_different_delegate": len(b_other_designator),
            "n_authority_has_no_delegation_code": b_no_code,
            "confirmation_rate": b_confirmed / n_b if n_b else None,
            "rpc_errors": b_rpc_error[:10],
            "other_designator_examples": b_other_designator[:10],
            "note": ("An authority holding a DIFFERENT delegate, or no code, at that block is "
                     "expected for authorizations that were invalid (stale nonce) or superseded "
                     "later in the same block; it is not by itself evidence of wrong recovery. "
                     "A wrong recovery would instead produce addresses that essentially never "
                     "carry any 0xef0100 designator."),
        },
    }
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "reports")
    out_path = os.path.abspath(os.path.join(out_dir, f"signer_recovery_validation_{run_id}.json"))
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
