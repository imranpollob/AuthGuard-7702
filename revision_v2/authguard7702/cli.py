"""Command-line interface for AuthGuard-7702."""
from __future__ import annotations

import argparse
import json
import os
import sys

from .scorer import AuthGuardScorer


def _emit(result: dict, pretty: bool):
    print(json.dumps(result, indent=2 if pretty else None, sort_keys=pretty))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="authguard7702")
    parser.add_argument("--model", required=True, help="AuthGuard-Fusion .pt artifact")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--pretty", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)

    bytecode = commands.add_parser("scan-bytecode")
    bytecode.add_argument("bytecode")

    address = commands.add_parser("scan-address")
    address.add_argument("address")
    address.add_argument("--rpc-url", required=True)
    address.add_argument("--block", default="latest")

    authorization = commands.add_parser("scan-authorization")
    authorization.add_argument("json_file")
    authorization.add_argument("--rpc-url", required=True)
    authorization.add_argument("--block", default="latest")

    args = parser.parse_args(argv)
    scorer = AuthGuardScorer(args.model, args.device)
    if args.command == "scan-bytecode":
        result = scorer.score_bytecode(args.bytecode)
        result["input_mode"] = "runtime_bytecode"
    elif args.command == "scan-address":
        result = scorer.score_address(args.address, args.rpc_url, args.block)
    else:
        with open(args.json_file) as handle:
            payload = json.load(handle)
        result = scorer.score_authorization(payload, args.rpc_url, args.block)
    _emit(result, args.pretty)
    return 0


if __name__ == "__main__":
    sys.exit(main())

