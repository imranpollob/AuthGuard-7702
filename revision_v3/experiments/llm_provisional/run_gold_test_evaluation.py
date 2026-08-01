"""Part 9: evaluates the provisional selected model (frozen in Part 8, using ONLY Gold-Dev)
plus Phase 2's authguard_sequence_dense, authguard_reference_v3, flat_cnn_matched_16384,
flat_cnn_16384, and the source static rule against PROVISIONAL Gold-Test labels. Gold-Test
provisional labels are used here for the FIRST time in this pipeline -- no earlier part
(Part 7 retraining, Part 8 selection) touched them. The model is not modified after this
point.

LABEL_SOURCE=LLM_PROVISIONAL
STATUS=PROVISIONAL_NOT_FOR_FINAL_CLAIMS

Usage:
    python3 revision_v3/experiments/llm_provisional/run_gold_test_evaluation.py
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np
import torch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "src"))
sys.path.insert(0, os.path.join(REPO_ROOT, "revision_v3", "experiments", "llm_provisional"))

from evaluation import model_runtime  # noqa: E402
from evaluation.metrics import auprc, auroc, brier, metrics_at_threshold  # noqa: E402
from evaluation.metrics_extra import balanced_accuracy_from_cm, confusion_matrix, expected_calibration_error, specificity_from_cm, binary_rule_report  # noqa: E402
from features.encode import encode_bytecode  # noqa: E402
from models.hybrid import HybridConfig, HybridModel  # noqa: E402

HUMAN_EVAL_DIR = os.path.join(REPO_ROOT, "revision_v3", "human_eval")
RESULTS_DIR = os.path.join(REPO_ROOT, "revision_v3", "results", "llm_provisional", "gold_test")
os.makedirs(RESULTS_DIR, exist_ok=True)

CONTINUOUS_MODELS = ["authguard_sequence_dense", "authguard_reference_v3",
                      "flat_cnn_matched_16384", "flat_cnn_16384"]
N_BOOTSTRAP = 5000
BOOT_SEED = 77032026


def load_gold_test():
    with open(os.path.join(HUMAN_EVAL_DIR, "gold_test_manifest.csv"), newline="") as f:
        manifest = {r["item_id"]: r for r in csv.DictReader(f)}
    with open(os.path.join(REPO_ROOT, "revision_v3", "results", "llm_provisional", "gold_test_labels.json")) as f:
        labels = {r["item_id"]: r for r in json.load(f)["records"]}
    return manifest, labels


def score_provisional_model(bytecodes: list[str], device) -> np.ndarray:
    ckpt_dir = os.path.join(REPO_ROOT, "revision_v3", "results", "llm_provisional", "provisional_final_model_checkpoints")
    seed_scores = []
    for seed in (7702, 7703, 7704):
        ckpt_path = os.path.join(ckpt_dir, f"provisional_final_model_seed{seed}.pt")
        ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
        model = HybridModel(HybridConfig(vocab_size=227, chunk_size=256, max_chunks=64, use_dense=True))
        model.load_state_dict(ckpt["model_state_dict"])
        model.to(device).eval()
        scores = []
        for bc in bytecodes:
            enc = encode_bytecode(bc, chunk_size=256, max_chunks=64)
            chunks = torch.as_tensor(enc.chunks[None, :, :].astype(np.int64)).to(device)
            mask = torch.as_tensor(enc.chunk_mask[None, :]).to(device)
            dense = torch.as_tensor(enc.dense[None, :]).to(device)
            with torch.no_grad():
                logit = model(chunks.long(), mask.bool(), dense=dense)
            prob = torch.sigmoid(logit / max(ckpt["temperature"], 1e-3))
            scores.append(float(prob.cpu().numpy()[0]))
        seed_scores.append(np.array(scores))
    return np.mean(seed_scores, axis=0), seed_scores


def bootstrap_ci_metric(y_true: np.ndarray, scores: np.ndarray, family_ids: np.ndarray,
                          metric_fn, n_replicates=N_BOOTSTRAP, seed=BOOT_SEED) -> dict:
    """Family-clustered single-model bootstrap CI (resample unique families with replacement,
    take all items belonging to each resampled family)."""
    rng = np.random.default_rng(seed)
    unique_families = np.unique(family_ids)
    family_to_indices = {fam: np.where(family_ids == fam)[0] for fam in unique_families}
    point = metric_fn(y_true, scores)
    boot_vals = []
    for _ in range(n_replicates):
        sampled_families = rng.choice(unique_families, size=len(unique_families), replace=True)
        idx = np.concatenate([family_to_indices[fam] for fam in sampled_families])
        if len(np.unique(y_true[idx])) < 2:
            continue
        boot_vals.append(metric_fn(y_true[idx], scores[idx]))
    boot_vals = np.array(boot_vals)
    return {"point": float(point), "ci_low": float(np.percentile(boot_vals, 2.5)),
            "ci_high": float(np.percentile(boot_vals, 97.5)), "n_valid_replicates": len(boot_vals)}


def mean_threshold(model_name: str, device) -> float:
    spec = model_runtime.MODEL_REGISTRY[model_name]
    thresholds = []
    for seed in (7702, 7703, 7704):
        for fold in range(5):
            ckpt_path = os.path.join(spec["checkpoint_dir"], f"{model_name}_seed{seed}_fold{fold}.pt")
            if os.path.exists(ckpt_path):
                ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
                thresholds.append(ckpt["threshold_5pct"])
    return float(np.mean(thresholds)) if thresholds else 0.5


def evaluate_scores(y_true, scores, family_ids, threshold) -> dict:
    cm = confusion_matrix(y_true, scores, threshold)
    at_thr = metrics_at_threshold(y_true, scores, threshold)
    auprc_ci = bootstrap_ci_metric(y_true, scores, family_ids, auprc)
    auroc_ci = bootstrap_ci_metric(y_true, scores, family_ids, auroc) if len(np.unique(y_true)) > 1 else None
    return {
        "n_evaluated": int(len(y_true)), "n_safe": int((y_true == 0).sum()), "n_unsafe": int((y_true == 1).sum()),
        "auprc": auprc(y_true, scores), "auprc_ci_95": [auprc_ci["ci_low"], auprc_ci["ci_high"]],
        "auroc": auroc(y_true, scores), "auroc_ci_95": [auroc_ci["ci_low"], auroc_ci["ci_high"]] if auroc_ci else None,
        "operating_threshold": threshold,
        "precision": at_thr["precision"], "recall": at_thr["recall"],
        "specificity": specificity_from_cm(cm), "fpr": at_thr["observed_fpr"], "f1": at_thr["f1"],
        "balanced_accuracy": balanced_accuracy_from_cm(cm), "brier": brier(y_true, scores),
        "calibration_error": expected_calibration_error(y_true, scores), "confusion_matrix": cm,
    }


def main() -> int:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    manifest, labels = load_gold_test()
    all_ids = list(labels.keys())
    label_of = {iid: labels[iid]["llm_provisional_label"] for iid in all_ids}
    n_uncertain = sum(1 for v in label_of.values() if v == "UNCERTAIN")

    binary_ids = [iid for iid in all_ids if label_of[iid] in ("SAFE", "UNSAFE")]
    y_true = np.array([1 if label_of[iid] == "UNSAFE" else 0 for iid in binary_ids])
    bytecodes = [manifest[iid]["runtime_bytecode"] for iid in binary_ids]
    family_ids = np.array([manifest[iid]["family_id"] for iid in binary_ids])

    report = {
        "LABEL_SOURCE": "LLM_PROVISIONAL", "STATUS": "PROVISIONAL_NOT_FOR_FINAL_CLAIMS",
        "n_total_gold_test_items": len(all_ids), "n_uncertain_excluded": n_uncertain,
        "uncertainty_exclusion_rate_pct": round(100 * n_uncertain / len(all_ids), 1),
        "n_evaluated_binary": len(binary_ids), "models": {},
    }

    print("[gold_test] scoring provisional_final_model...")
    prov_scores, prov_seed_scores = score_provisional_model(bytecodes, device)
    prov_thr = float(np.mean([torch.load(
        os.path.join(REPO_ROOT, "revision_v3", "results", "llm_provisional",
                     "provisional_final_model_checkpoints", f"provisional_final_model_seed{s}.pt"),
        map_location=device, weights_only=False)["threshold_5pct"] for s in (7702, 7703, 7704)]))
    report["models"]["provisional_final_model"] = evaluate_scores(y_true, prov_scores, family_ids, prov_thr)

    for model_name in CONTINUOUS_MODELS:
        print(f"[gold_test] scoring {model_name}...")
        scores_by_seed = model_runtime.score_dataset_with_ensemble(model_name, bytecodes, device=device)
        point_scores = np.mean(list(scores_by_seed.values()), axis=0)
        thr = mean_threshold(model_name, device)
        report["models"][model_name] = evaluate_scores(y_true, point_scores, family_ids, thr)

    rule_preds = np.array([int(manifest[iid].get("source_label", 0)) for iid in binary_ids])
    report["source_static_rule"] = binary_rule_report(y_true, rule_preds)

    ranking = sorted(
        [(name, m["auprc"]) for name, m in report["models"].items()],
        key=lambda x: -x[1]
    )
    report["model_ranking_by_auprc"] = ranking

    out_path = os.path.join(RESULTS_DIR, "gold_test_report.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\nWrote {out_path}")
    for name, aup in ranking:
        m = report["models"][name]
        print(f"  {name}: AUPRC={m['auprc']:.3f} [{m['auprc_ci_95'][0]:.3f},{m['auprc_ci_95'][1]:.3f}] "
              f"recall={m['recall']:.3f} FPR={m['fpr']:.3f}")
    print(f"  source_static_rule: precision={report['source_static_rule']['precision']:.3f} "
          f"recall={report['source_static_rule']['recall']:.3f}")
    print(f"  UNCERTAIN exclusion: {report['uncertainty_exclusion_rate_pct']}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
