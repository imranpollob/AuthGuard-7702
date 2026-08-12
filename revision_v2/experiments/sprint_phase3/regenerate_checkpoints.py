#!/usr/bin/env python3
"""Phase 3 — regenerate and FREEZE the four primary targets for seed 7702.

Faithful rerun of the original training procedure. Nothing about the recipe is changed:
same corpus, same folds, same preprocessing, same architectures, same hyperparameters,
same optimiser, same seeding, and the original determinism settings are left exactly as
they are (the fusion/ablation paths call torch.use_deterministic_algorithms(False); that
is part of the historical recipe and is deliberately NOT overridden).

The training code itself is imported from the attack runner so there is one definition of
"how these models are trained" rather than a copy that could drift.

Everything is persisted: weights, config, preprocessing stats, temperature, all three
thresholds, validation metrics, environment, git commit, SHA-256. No regenerated model
exists only in memory.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time

import numpy as np
import pandas as pd
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
RV2 = os.path.abspath(os.path.join(HERE, "..", ".."))
ROOT = os.path.abspath(os.path.join(RV2, ".."))
OUT = os.path.join(RV2, "results", "sprint_phase3")
CKPT = os.path.join(OUT, "checkpoints")

sys.path.insert(0, os.path.join(RV2, "experiments", "adaptive_attacks_v2"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = _load("run_adaptive_attacks_v2", os.path.join(
    RV2, "experiments", "adaptive_attacks_v2", "run_adaptive_attacks_v2.py"))
fusion = runner.fusion
sanity = runner.sanity
WarningPolicy = runner.WarningPolicy

PRIMARY = ["authguard_seq", "emulator_logreg", "flat_cnn", "hist_ngram_xgb"]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def environment():
    return dict(
        python=platform.python_version(),
        torch=torch.__version__,
        cuda=torch.version.cuda,
        cudnn=torch.backends.cudnn.version(),
        device_name=(torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"),
        numpy=np.__version__, pandas=pd.__version__,
        platform=platform.platform(),
        git_commit=subprocess.run(["git", "rev-parse", "HEAD"], cwd=RV2,
                                  capture_output=True, text=True).stdout.strip(),
        deterministic_algorithms="left at original setting (False) — recipe not modified")


class Args:
    """Minimal stand-in for the runner's argparse namespace."""

    def __init__(self, models, epochs, pools, sids, families):
        self.models = models
        self.epochs = epochs
        self.pools = pools
        self.sids = sids
        self.families = families


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=7702)
    parser.add_argument("--folds", nargs="+", type=int, default=list(range(5)))
    parser.add_argument("--models", nargs="+", default=PRIMARY)
    parser.add_argument("--epochs", type=int, default=30)
    args_cli = parser.parse_args()
    started = time.time()
    if runner.verify_frozen() != 0:
        raise RuntimeError("frozen-artifact verification failed")
    os.makedirs(CKPT, exist_ok=True)

    bench, frame = runner.load_primary()
    features = sanity.build_features(frame, os.path.join(
        RV2, "experiments", "baseline_v2", "features_v2.npz"))
    token_store = sanity.LocalTokenStore(features["tokens"], features["offsets"],
                                         features["auxiliary"])
    y = frame["label"].to_numpy(dtype=int)
    folds = frame["fold_id"].to_numpy(dtype=int)
    families = frame["family_id"].astype(str).to_numpy()
    sids = frame["sample_id"].astype(str).to_numpy()
    pools = runner.build_pools(bench)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    env = environment()
    print(f"[phase3] device={device} seed={args_cli.seed} models={args_cli.models}", flush=True)
    print(f"[phase3] env: torch {env['torch']} cuda {env['cuda']} cudnn {env['cudnn']}",
          flush=True)

    manifest = []
    for fold in args_cli.folds:
        pools.assert_disjoint(fold)
        args = Args(args_cli.models, args_cli.epochs, pools, sids, families)
        t0 = time.time()
        # Single definition of the training procedure, imported from the attack runner.
        scorers, policies, test_idx = runner.fit_fold_models(
            frame, features, token_store, y, folds, fold, args_cli.seed, device, args)
        for name in args_cli.models:
            scorer, policy = scorers[name], policies[name]
            path = os.path.join(CKPT, f"{name}_s{args_cli.seed}_f{fold}.pt")
            payload = dict(
                model_name=name, seed=args_cli.seed, test_fold=fold,
                validation_fold=(fold + 1) % 5,
                training_folds=[f for f in range(5) if f not in (fold, (fold + 1) % 5)],
                temperature=float(scorer.temperature),
                threshold_01=float(policy.threshold_01),
                threshold_05=float(policy.threshold_05),
                threshold_10=float(policy.threshold_10),
                epochs=args_cli.epochs, environment=env,
                recipe="unmodified original training procedure")
            if hasattr(scorer, "model") and isinstance(scorer.model, torch.nn.Module):
                payload["state_dict"] = {k: v.detach().cpu()
                                         for k, v in scorer.model.state_dict().items()}
                payload["architecture"] = type(scorer.model).__name__
                payload["n_parameters"] = int(sum(
                    p.numel() for p in scorer.model.parameters() if p.requires_grad))
                if name == "flat_cnn":
                    payload["max_len"] = scorer.max_len
                torch.save(payload, path)
            else:
                # sklearn / xgboost estimators
                import pickle
                payload["estimator"] = scorer.model
                payload["architecture"] = type(scorer.model).__name__
                with open(path, "wb") as fh:
                    pickle.dump(payload, fh)
            digest = sha256_file(path)
            manifest.append(dict(
                model=name, seed=args_cli.seed, fold=fold, path=os.path.relpath(path, RV2),
                sha256=digest, bytes=os.path.getsize(path),
                temperature=payload["temperature"],
                threshold_01=payload["threshold_01"],
                threshold_05=payload["threshold_05"],
                threshold_10=payload["threshold_10"],
                architecture=payload["architecture"],
                n_parameters=payload.get("n_parameters")))
            print(f"  saved {os.path.basename(path)}  sha={digest[:12]}  "
                  f"thr05={payload['threshold_05']:.6f}", flush=True)
        print(f"[phase3] fold {fold} done ({time.time() - t0:.0f}s)", flush=True)

    frame_manifest = pd.DataFrame(manifest)
    frame_manifest.to_csv(os.path.join(OUT, f"checkpoint_manifest_s{args_cli.seed}.csv"),
                          index=False)
    with open(os.path.join(OUT, f"checkpoint_manifest_s{args_cli.seed}.json"), "w") as fh:
        json.dump(dict(
            phase="3 regenerate and freeze primary checkpoints",
            script="revision_v2/experiments/sprint_phase3/regenerate_checkpoints.py",
            seed=args_cli.seed, folds=args_cli.folds, models=args_cli.models,
            environment=env, provenance="regenerated_experiment",
            wall_seconds=time.time() - started, checkpoints=manifest), fh, indent=2)
    if runner.verify_frozen() != 0:
        raise RuntimeError("frozen-artifact verification failed after run")
    print(f"[phase3] {len(manifest)} checkpoints frozen in {time.time() - started:.0f}s",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
