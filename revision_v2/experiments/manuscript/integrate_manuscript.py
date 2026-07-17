#!/usr/bin/env python3
"""Create revision_v2/manuscript/main.tex from the frozen manuscript plus v2 evidence."""
import hashlib
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RV2 = os.path.join(ROOT, "revision_v2")
SOURCE = os.path.join(ROOT, "paper_build", "overleaf", "main.tex")
OUT = os.path.join(RV2, "manuscript", "main.tex")
RESULTS = os.path.join(RV2, "results")


def load(*parts):
    with open(os.path.join(RESULTS, *parts)) as f:
        return json.load(f)


def replace_once(text, old, new, label):
    if text.count(old) != 1:
        raise RuntimeError(f"{label}: expected one exact match, found {text.count(old)}")
    return text.replace(old, new, 1)


def replace_environment(text, label, replacement, kind="table"):
    marker = f"\\label{{{label}}}"
    pos = text.find(marker)
    if pos < 0:
        raise RuntimeError(f"missing environment label {label}")
    candidates = [text.rfind(f"\\begin{{{kind}}}[t]", 0, pos),
                  text.rfind(f"\\begin{{{kind}*}}[t]", 0, pos)]
    start = max(candidates)
    if start < 0:
        raise RuntimeError(f"missing start for {label}")
    starred = text.startswith(f"\\begin{{{kind}*}}", start)
    end_token = f"\\end{{{kind}*}}" if starred else f"\\end{{{kind}}}"
    end = text.find(end_token, pos)
    if end < 0:
        raise RuntimeError(f"missing end for {label}")
    end += len(end_token)
    return text[:start] + replacement + text[end:]


def table_wrapper(label, caption, filename, wide=False):
    env = "table*" if wide else "table"
    width = r"\textwidth" if wide else r"\columnwidth"
    return (f"\\begin{{{env}}}[t]\n  \\centering\n  \\caption{{{caption}}}\n"
            f"  \\label{{{label}}}\n  \\resizebox{{{width}}}{{!}}{{\\input{{tables/{filename}}}}}\n"
            f"\\end{{{env}}}")


def fmt(x):
    return f"{x:.3f}"


def main():
    gdet = load("gdet_v2", "gdet_v2_results.json")["primary"]
    gdet_boot = load("uncertainty", "gdet_bootstrap.json")
    gadv = load("gadv_v2", "gadv_v2_results.json")["aggregate"]["val_threshold"]
    gadv_boot = load("uncertainty", "gadv_v2_bootstrap.json")["results"]
    baselines = load("baselines", "baselines_results.json")
    ablations = load("ablations", "ablations_results.json")
    baseline_boot = load("baselines", "paired_family_bootstrap.json")
    first = load("first_stop", "first_stop_results.json")
    controls = load("secondary_controls", "secondary_controls.json")
    gateb = load("gateB", "gateB_verdict.json") if os.path.exists(
        os.path.join(RESULTS, "gateB", "gateB_verdict.json")) else {"verdict": "NOT_RUN"}
    gateb_results = load("gateB", "gateB_results.json") if os.path.exists(
        os.path.join(RESULTS, "gateB", "gateB_results.json")) else None

    fs = first["primary_stored_folds"]
    fs_boot = first["paired_family_clustered_bootstrap"]
    ag_linux = ablations["full_773"]["mean"]["AUPRC"]
    fs_full = fs["first_stop_full_773"]["mean"]["AUPRC"]
    fs_nolen = fs["first_stop_no_length"]["mean"]["AUPRC"]
    fs_nometa = fs["first_stop_no_length_metadata"]["mean"]["AUPRC"]
    nolen_ci = fs_boot["first_stop_no_length_minus_authguard_full_773"]["delta_CI95"]
    nometa_ci = fs_boot["first_stop_no_length_metadata_minus_authguard_full_773"]["delta_CI95"]
    if fs_nolen > ag_linux and fs_nometa > ag_linux and nolen_ci[0] > 0 and nometa_ci[0] > 0:
        fs_branch = "genuine"
        fs_claim = ("The advantage survives removal of explicit length and metadata-like "
                    "features, supporting terminal-region truncation as a representational "
                    "finding rather than an explicit-length shortcut.")
    elif fs_nolen <= ag_linux + 0.02 and fs_nometa <= ag_linux + 0.02:
        fs_branch = "shortcut"
        fs_claim = ("The apparent advantage collapses after removing length/metadata-like "
                    "features, identifying a corpus shortcut rather than a stronger representation.")
    else:
        fs_branch = "mixed"
        fs_claim = ("The advantage is reduced but not eliminated by length/metadata ablation; "
                    "we therefore report a mixed length-and-structure decomposition.")

    strongest = baseline_boot["strongest_baseline"]
    strongest_label = {"hash_xgb": "hashed 4-gram XGBoost", "tfidf_lr": "TF--IDF LR",
                       "tfidf_svm": "TF--IDF SVM", "abl_hist_only": "opcode-histogram XGBoost",
                       "abl_ngram_only": "hashed 4-gram XGBoost",
                       "abl_hist_struct": "opcode-histogram plus structural XGBoost",
                       "abl_hist_ngram": "opcode-histogram plus hashed-4-gram XGBoost"}.get(
                           strongest, strongest)
    ablation_labels = {
        "struct_sel_only": "structural/selector only", "hist_only": "opcode histogram only",
        "ngram_only": "hashed 4-gram only", "hist_struct": "histogram plus structural",
        "hist_ngram": "histogram plus hashed 4-grams", "full_773": "full 773 features",
        "no_selectors": "full without selector features", "no_length": "full without length",
        "no_metadata": "full without metadata-like features",
        "no_length_metadata": "full without length/metadata-like features"}
    best_ablation = max(ablations, key=lambda k: ablations[k]["mean"]["AUPRC"])
    best_ablation_ap = ablations[best_ablation]["mean"]["AUPRC"]
    if best_ablation == "full_773":
        ablation_claim = "The full feature set has the highest primary-seed ablation AUPRC."
    else:
        ablation_claim = (f"The highest primary-seed ablation is {ablation_labels[best_ablation]} "
                          f"at {best_ablation_ap:.3f} AUPRC, so the complete 773-feature set is "
                          "not empirically optimal.")
    delta = baseline_boot["authguard_minus_strongest"]
    delta_ci = delta["delta_CI95"]
    if delta_ci[0] > 0:
        baseline_claim = (f"Full AuthGuard exceeds it by {delta['delta_point']:+.3f} pooled "
                          f"AUPRC (95\\% CI [{delta_ci[0]:+.3f},{delta_ci[1]:+.3f}]).")
        baseline_conclusion = "The full tool exceeds the strongest same-host standard baseline"
    elif delta_ci[1] < 0:
        baseline_claim = (f"Full AuthGuard is lower by {delta['delta_point']:+.3f} pooled "
                          f"AUPRC (95\\% CI [{delta_ci[0]:+.3f},{delta_ci[1]:+.3f}]).")
        baseline_conclusion = "The full tool is below the strongest same-host standard baseline"
    else:
        baseline_claim = (f"Their paired pooled difference is {delta['delta_point']:+.3f} "
                          f"AUPRC (95\\% CI [{delta_ci[0]:+.3f},{delta_ci[1]:+.3f}]), so the "
                          "comparison is statistically unresolved.")
        baseline_conclusion = ("The full tool does not statistically separate from the "
                               "strongest same-host standard baseline")
    f200 = gadv_boot["F200"]
    compound = gadv_boot["M3F200"]
    gateb_abstract = ""
    gateb_bullet = ""
    if gateb.get("verdict") == "PASS" and gateb_results:
        clean_b = gateb_results["summary"]["cleanM0"]
        clean_b_ci = gateb_results["family_clustered_uncertainty"]["cleanM0"]
        gateb_abstract = (f" Selective escalation routes {100*clean_b['escalation_rate']:.1f}\\% "
                          f"of clean cases and concentrates errors by "
                          f"{clean_b['concentration_ratio']:.2f}x.")
        gateb_bullet = (f"\n  \\item a frozen-criterion selective-escalation rule that routes "
                        f"{100*clean_b['escalation_rate']:.1f}\\% of clean cases and "
                        f"concentrates errors by {clean_b['concentration_ratio']:.2f}x "
                        f"(95\\% CI [{clean_b_ci['candidate_ratio']['CI95'][0]:.2f},"
                        f"{clean_b_ci['candidate_ratio']['CI95'][1]:.2f}]).")

    with open(SOURCE) as f:
        text = f.read()
    text = replace_once(text, r"\usepackage{cite}",
                        r"\usepackage{cite}" + "\n" +
                        r"\graphicspath{{../../paper_build/overleaf/}}", "graphicspath")

    abstract = f"""\\begin{{abstract}}
EIP-7702 lets an externally owned account delegate execution to contract code, creating a
pre-authorization decision point at which runtime bytecode may be the only available signal.
We present AuthGuard-7702, a decompiler-free bytecode risk scorer, and a task-aligned,
dependence-aware evaluation on 727 artifact-derived positives and 1,553 rule-silent weak
negatives. Family-grouped AuthGuard AUPRC is $0.881\\pm0.028$, versus $0.975\\pm0.012$ under
a random diagnostic; the paired random-minus-family interval excludes zero. Against the
strongest same-host standard bytecode baseline ({strongest_label}), full AuthGuard's pooled
AUPRC difference is {delta['delta_point']:+.3f} (95\\% CI
[{delta_ci[0]:+.3f},{delta_ci[1]:+.3f}]). First-STOP truncation obtains
{fs_full:.3f} fold-mean AUPRC and {fs_nometa:.3f} after length/metadata ablation; {fs_claim}
Donor-isolated augmentation improves pooled F200 recall by {f200['Recall']['delta_point']:+.3f}
but increases FPR by {f200['FPR']['delta_point']:+.3f}, exposing an operational trade-off rather
than general robustness.{gateb_abstract} These results support lightweight bytecode screening as a complementary
stage within the evaluated conditions, not production readiness or replacement of declarative
analysis.
\\end{{abstract}}"""
    text = re.sub(r"\\begin\{abstract\}.*?\\end\{abstract\}", abstract, text,
                  count=1, flags=re.S)

    start = "While we employ standard gradient boosting for inference, our primary contribution"
    s = text.find(start); e = text.find(r"\end{itemize}", s)
    if s < 0 or e < 0:
        raise RuntimeError("introduction contribution block not found")
    e += len(r"\end{itemize}")
    contributions = f"""The estimator is standard gradient boosting; the contribution is the
task-specific screening tool, its dependence-aware protocol, and the empirical representation
and robustness findings. The main contributions are:
\\begin{{itemize}}
  \\item an outcome-blind task-alignment and frozen family-grouped protocol with OOF threshold
  transfer, FPR reporting, donor isolation, and family-clustered uncertainty;
  \\item a decompiler-free 773-feature scorer compared against the strongest same-host standard
  bytecode baseline: {baseline_claim}
  \\item a first-STOP representation investigation: {fs_claim}
  \\item a donor-isolated augmentation study including M3+F200, showing recall/ranking gains
  accompanied by materially higher FPR rather than uniform robustness.{gateb_bullet}
\\end{{itemize}}"""
    text = text[:s] + contributions + text[e:]

    old = ("While these declarative analyses are powerful, they are computationally intensive. "
           "AuthGuard bridges the gap by providing a sub-second, lightweight screening stage "
           "that can complement heavyweight analyzers without blocking real-time interactive "
           "workflows. We do not execute the full USENIX Gigahorse/Datalog pipeline. The "
           "sensitive-name rule approximation and external-call structural over-approximation "
           "evaluated here are lightweight local baselines and must not be interpreted as "
           "reproductions of that pipeline.")
    new = ("AuthGuard is a lightweight local screening stage intended to complement declarative "
           "analyzers, whose runtime we do not measure; the approaches consume different "
           "information and provide different guarantees. We could not execute the full USENIX "
           "Gigahorse/Datalog pipeline because the artifact omits required Gigahorse client "
           "libraries and this environment lacks Souffle and a container runtime. The local "
           "rule approximations below are not reproductions of that pipeline.")
    text = replace_once(text, old, new, "reference analyzer positioning")

    old = ("The G-ADV protocol evaluates held-out M3 and pure-M0 F200 separately; it does not "
           "recover or evaluate the compound M3-plus-F200 condition used in G-VOL.")
    new = ("G-ADV evaluates held-out M3, pure-M0 F200, and compound M3-plus-F200 as distinct "
           "conditions; none establishes robustness beyond the implemented transformations.")
    text = replace_once(text, old, new, "compound threat scope")

    protocol_start = "Four protocols answer distinct questions and are not directly interchangeable."
    protocol_end = ("Training and test transformations use separate deterministic random-number domains.")
    s = text.find(protocol_start); e = text.find(protocol_end, s)
    if s < 0 or e < 0:
        raise RuntimeError("protocol block not found")
    e += len(protocol_end)
    protocols = r"""Four protocols answer distinct questions. G-DET uses five preserved
family-grouped outer folds. Within each outer-training population, four family-grouped inner
folds produce OOF scores, the maximum-F1 threshold is selected from those scores, the model is
refit on all outer-training rows, and the test fold is evaluated once. The random split is a
diagnostic only. G-MUT trains clean M0 models and applies M0--M3 transformations to held-out
positives. G-VOL applies the compound transformation with increasing post-STOP flooding.
G-ADV uses outer fold $f$ for test, fold $(f+1)\bmod 5$ for clean validation in its primary
continuity arm, and the other three folds for fitting; a four-fold OOF-threshold arm is reported
as sensitivity. G-ADV training conditions are M0/M1/M2/F25/F50/F100; M3, F200, and M3+F200 are
held out. Training, validation, and test donors come from partition-isolated family pools and
every copied segment is recorded."""
    text = text[:s] + protocols + text[e:]

    old = ("G-VOL composes the metadata, address, and selector transformations with each flooding "
           "level. G-ADV instead generates each F condition directly from M0. These variants are "
           "described as structure-preserving under the repository's opcode-skeleton checker. For "
           "each tier, the checker compares the original and transformed opcode-token sequences "
           "over the original pre-metadata region. All 727 retained positives passed at M1, M2, "
           "and M3. This result verifies only the implemented syntactic property; it does not "
           "prove execution or behavioral equivalence.")
    new = ("G-VOL composes metadata, address, selector, and flooding transformations, whereas "
           "G-ADV also evaluates pure-M0 flooding. All 727 positives pass the syntactic checker at "
           "M1--M3. A bounded Anvil trace study adds execution evidence on ten delegates: M1 and "
           "F200 preserve all tested fingerprints, M2 preserves control-flow observations with "
           "targets allowed to change, and M3 differs at intentionally renamed selectors. These "
           "tests do not prove general semantic equivalence.")
    text = replace_once(text, old, new, "transformation validity")

    text = replace_once(text,
        "For G-ADV training, benign and malicious sources are augmented symmetrically.",
        "For G-ADV training, benign and malicious sources are augmented symmetrically using "
        "partition-isolated benign-general donor families.", "donor isolation")
    text = replace_once(text,
        "The benign false-positive rate provides the empirical check for residual shortcut behavior.",
        "The 103,250-segment provenance ledger and two-sided assertions establish donor isolation; "
        "benign FPR measures the remaining operational trade-off.", "donor ledger")

    text = replace_once(text,
        "The evaluation addresses five research questions. Unless stated otherwise, values are "
        "task-aligned fold means. G-DET, G-MUT, G-VOL, and G-ADV retain distinct splits, "
        "threshold-selection procedures, and transformation conditions.",
        "The evaluation addresses detection, dependence, transformations, augmentation, "
        "representation shortcuts, controls, and local cost. Unless stated otherwise, values are "
        "task-aligned fold means; pooled family-bootstrap estimates are labeled separately.",
        "evaluation overview")

    text = replace_environment(text, "tab:gdet-performance",
        table_wrapper("tab:gdet-performance",
                      "Corrected G-DET v2. Thresholded metrics use inner family-OOF thresholds.",
                      "gdet_v2.tex", wide=True))
    s = text.find("Table~\\ref{tab:gdet-performance} reports G-DET")
    e_marker = "These baselines are not implementations of the full USENIX Gigahorse/Datalog pipeline, which was not executed."
    e = text.find(e_marker, s)
    if s < 0 or e < 0:
        raise RuntimeError("G-DET narrative not found")
    e += len(e_marker)
    gdet_text = f"""Table~\\ref{{tab:gdet-performance}} reports corrected G-DET v2. AuthGuard
achieves {gdet['leave_family_out']['authguard']['mean']['AUPRC']:.3f} AUPRC, F1
{gdet['leave_family_out']['authguard']['mean']['F1']:.3f}, recall
{gdet['leave_family_out']['authguard']['mean']['Recall']:.3f}, and FPR
{gdet['leave_family_out']['authguard']['mean']['FPR']:.3f}. Its pooled AUPRC is
{gdet_boot['authguard_AUPRC']['point']:.3f}
[{gdet_boot['authguard_AUPRC']['CI95'][0]:.3f},{gdet_boot['authguard_AUPRC']['CI95'][1]:.3f}].
The corrected thresholds increase recall and reduce precision relative to v1; v1 was
conservative, not inflated. The local rules expose complementary failure modes and are not the
full reference analyzer."""
    text = text[:s] + gdet_text + text[e:]

    insert_at = text.find(r"\subsection{RQ2: Effect of Random Splitting}")
    if insert_at < 0:
        raise RuntimeError("RQ2 marker missing")
    representation = f"""
\\subsection{{Strong baselines, ablations, and first-STOP representation}}

\\begin{{table}}[t]
  \\centering
  \\caption{{Same-host standard baselines and AuthGuard feature ablations. AUPRC reports
  seed 7702 with the five-seed range for stochastic learners.}}
  \\label{{tab:baseline-ablation}}
  \\resizebox{{\\columnwidth}}{{!}}{{\\input{{tables/baselines_ablations_v2.tex}}}}
\\end{{table}}

The strongest standard Phase-3 baseline is {strongest_label}. On same-host pooled predictions,
{baseline_claim} {ablation_claim} These comparisons are not mixed with the ARM64 headline fits.

\\begin{{table}}[t]
  \\centering
  \\caption{{First-STOP representation and explicit shortcut ablations; AUPRC reports seed
  7702 with the five-seed range, and paired deltas use same-host seed-7702 full AuthGuard.}}
  \\label{{tab:first-stop}}
  \\resizebox{{\\columnwidth}}{{!}}{{\\input{{tables/first_stop_v2.tex}}}}
\\end{{table}}

First-STOP truncation scores {fs_full:.3f} fold-mean AUPRC versus {ag_linux:.3f} for the
same-host full view; removing explicit length yields {fs_nolen:.3f}, and removing length plus
metadata-like features yields {fs_nometa:.3f}. {fs_claim} Near-empty and whole-body prefixes,
finite/zero feature rows, family-threshold sensitivity, and post-hoc exclusion diagnostics are
reported in the artifact. The failed dual-view Gate A is not proposed as a paper method.

"""
    text = text[:insert_at] + representation + text[insert_at:]

    random_end = ("Accordingly, the family-grouped result is used for the primary detection claim.")
    text = replace_once(text, random_end, random_end + r"""

\begin{table}[t]
  \centering
  \caption{Sensitivity to frozen family-similarity thresholds.}
  \label{tab:family-sensitivity}
  \resizebox{\columnwidth}{!}{\input{tables/family_sensitivity_v2.tex}}
\end{table}

AuthGuard remains above opcode-histogram XGBoost at thresholds 0.75, 0.85, and 0.90. Its
observation/inverse-family/one-vote-per-bytecode pooled AUPRCs are 0.867/0.838/0.844, so the
ranking conclusion is not driven only by large families or exact duplicates.""",
        "family sensitivity insertion")

    text = replace_environment(text, "tab:gmut-robustness",
        table_wrapper("tab:gmut-robustness", "Donor-isolated G-MUT v2 retained recall.",
                      "gmut_v2.tex"))
    s = text.find("Under G-MUT, the sensitive-name approximation")
    e = text.find("All 727 positives pass the opcode-token checker at M1--M3, which supports only the stated syntactic invariant.", s)
    if s < 0 or e < 0:
        raise RuntimeError("G-MUT narrative not found")
    e += len("All 727 positives pass the opcode-token checker at M1--M3, which supports only the stated syntactic invariant.")
    text = text[:s] + ("Under corrected donor-isolated G-MUT, AuthGuard recall changes from "
        "0.808 at M0 to 0.770 at M3; all 2,280 transformed cases per tier pass the syntactic "
        "checker. The bounded execution study provides the narrower trace evidence stated above.") + text[e:]
    text = replace_environment(text, "fig:mutation-flooding", "", kind="figure")
    old = ("Figure~\\ref{fig:mutation-flooding}(b) reports the separate G-VOL stress test. At "
           "the compound metadata/address/selector starting condition, AuthGuard and opcode-"
           "histogram XGBoost retain 0.608 and 0.603 recall. At +200\\% post-\\texttt{STOP} "
           "flooding, recall falls to 0.130 and 0.279, respectively. The sensitive-name "
           "approximation remains at zero and the external-call over-approximation at one. The "
           "compound result exposes a substantial residual weakness and is not the pure-M0 F200 "
           "condition used in G-ADV.")
    new = r"""The separate donor-isolated G-VOL stress test is reported in
Table~\ref{tab:gvol-v2}. AuthGuard recall falls from 0.816 at +0\% to 0.379 at +200\%; opcode
XGBoost falls from 0.809 to 0.423. The retained v1-donor arm can move in the opposite direction,
confirming that a single donor signature confounded the old experiment.

\begin{table}[t]
  \centering
  \caption{Donor-isolated G-VOL v2 retained recall.}
  \label{tab:gvol-v2}
  \resizebox{\columnwidth}{!}{\input{tables/gvol_v2.tex}}
\end{table}"""
    text = replace_once(text, old, new, "G-VOL narrative")

    text = replace_environment(text, "tab:gadv-results",
        table_wrapper("tab:gadv-results",
                      "Donor-isolated G-ADV v2 recall; primary clean-validation threshold arm.",
                      "gadv_v2.tex", wide=True))
    text = replace_environment(text, "fig:gadv-heldout", "", kind="figure")
    s = text.find("Table~\\ref{tab:gadv-results} summarizes G-ADV.")
    e_marker = ("These findings establish improvement under the tested held-out flooding severity, "
                "not robustness to arbitrary transformations or recovery of compound G-VOL F200.")
    e = text.find(e_marker, s)
    if s < 0 or e < 0:
        raise RuntimeError("G-ADV narrative not found")
    e += len(e_marker)
    gadv_text = f"""Table~\\ref{{tab:gadv-results}} reports the complete donor-isolated G-ADV
rerun. Pooled F200 recall changes from {f200['Recall']['M0']:.3f} to
{f200['Recall']['aug']:.3f}, a delta of {f200['Recall']['delta_point']:+.3f}
[{f200['Recall']['delta_CI95'][0]:+.3f},{f200['Recall']['delta_CI95'][1]:+.3f}], while FPR
increases by {f200['FPR']['delta_point']:+.3f}
[{f200['FPR']['delta_CI95'][0]:+.3f},{f200['FPR']['delta_CI95'][1]:+.3f}]. Under M3+F200,
recall improves by {compound['Recall']['delta_point']:+.3f}
[{compound['Recall']['delta_CI95'][0]:+.3f},{compound['Recall']['delta_CI95'][1]:+.3f}], but FPR
also increases by {compound['FPR']['delta_point']:+.3f}. Thus augmentation improves ranking and
recall at the cost of more false alerts; the old donor-confounded false-positive-reduction claim
is rejected."""
    text = text[:s] + gadv_text + text[e:]

    old = ("Crucially, this sub-10ms latency proves that AuthGuard-7702 can be seamlessly "
           "integrated into real-time wallet authorization flows without degrading the user experience.")
    new = ("These measurements indicate that local scoring is unlikely to dominate an interactive "
           "authorization flow on comparable hardware; wallet-level latency, integration, and user "
           "experience remain unevaluated.")
    text = replace_once(text, old, new, "latency claim")

    rq5_end = new
    controls_text = r"""

\begin{table}[t]
  \centering
  \caption{Secondary benign-general controls at corrected frozen thresholds.}
  \label{tab:secondary-controls}
  \resizebox{\columnwidth}{!}{\input{tables/secondary_controls_v2.tex}}
\end{table}

At the aggressive maximum-F1 threshold, AuthGuard flags 95/797 benign-general controls
(FPR 0.119). Opcode RF and opcode XGBoost yield 0.034 and 0.221. All five benign-AA cases are
unflagged by AuthGuard and are case observations only. Raw AuthGuard scores are ranking scores:
family-disjoint calibration changes ECE from 0.134 to 0.098 with Platt scaling."""
    text = replace_once(text, rq5_end, rq5_end + controls_text, "secondary controls insertion")

    old = ("The mutation experiments show that performance depends on the transformation regime. "
           "AuthGuard retains more signal than the sensitive-name approximation after selector "
           "rewriting, but its M3 recall remains 0.530. The compound G-VOL F200 result is more "
           "severe: recall falls to 0.130. Because G-ADV evaluates pure-M0 F200 rather than compound "
           "M3-plus-F200, the augmentation result does not resolve this failure mode.\n\n"
           "Within the G-ADV protocol, source-balanced augmentation materially improves F200 "
           "ranking, recall, and false-positive behavior. The family-clustered intervals support "
           "the direction of the F200 changes. However, the remaining FPR of 0.174 is operationally "
           "significant, and opcode-histogram XGBoost-aug achieves higher recall at the cost of "
           "substantially more false positives. The appropriate deployment threshold would therefore "
           "depend on the costs of missed threats and user-facing warnings. Clean and M3 recall "
           "changes are not statistically resolved, which argues against describing augmentation "
           "as uniformly beneficial across all operating conditions.")
    new = ("Corrected mutation and flooding results remain regime-dependent. Donor isolation "
           "removes the most serious leakage concern but does not make flooding benign: clean-model "
           "G-VOL recall falls sharply, and G-ADV's recall recovery buys significantly more false "
           "alerts in both F200 and M3+F200. Threshold selection therefore encodes an explicit alert-"
           "burden trade-off. Neither augmentation nor first-STOP truncation supports robustness to "
           "unseen transformations.")
    text = replace_once(text, old, new, "evasion discussion")

    old = ("The mutation benchmark is limited by its checker. Passing the opcode-skeleton test "
           "verifies a syntactic invariant over the checked region, not behavioral equivalence, "
           "dynamic unreachability, or preservation under arbitrary compiler and control-flow "
           "transformations. Future evaluation should incorporate execution-aware validation, "
           "reachability-sensitive representations, and compound transformations that combine "
           "selector changes with severe flooding.")
    new = ("The mutation benchmark remains checker-constrained. Ten-contract execution traces "
           "support preservation only for the tested calls and stated M1/M2/F200 observations; M3 "
           "intentionally reroutes renamed selectors. This is not formal or general behavioral "
           "equivalence. Donor-isolated compound tests broaden the stress conditions but do not cover "
           "arbitrary recompilation or control-flow obfuscation.")
    text = replace_once(text, old, new, "validity transformation")

    conclusion_start = "This paper presented AuthGuard-7702, a decompiler-free architecture"
    s = text.find(conclusion_start)
    e = text.find("\n\n\\bibliographystyle", s)
    if s < 0 or e < 0:
        raise RuntimeError("conclusion not found")
    conclusion = f"""This paper presented a task-aligned, dependence-aware evaluation and a
lightweight bytecode scorer for pre-authorization EIP-7702 screening. Family grouping exposes a
material random-split optimism gap, corrected OOF thresholds change the operating point, and
donor isolation converts the old augmentation story into an honest recall--FPR trade-off. The
first-STOP investigation yields the following bounded representation conclusion: {fs_claim}
{baseline_conclusion} within this artifact-defined task. Labels remain source-derived,
independent validation is insufficient, transformations
are checker-constrained, the full reference analyzer was not run, and wallet integration is
unevaluated. AuthGuard is therefore a complementary screening baseline and released evaluation
protocol, not a production-ready detector."""
    text = text[:s] + conclusion + text[e:]
    text = replace_once(text, r"\bibliography{references}",
                        r"\bibliography{../../paper_build/overleaf/references}", "bibliography")

    # Gate B is excluded on failure; on PASS, report its frozen-criteria evidence.
    if gateb.get("verdict") == "PASS" and gateb_results:
        marker = r"\subsection{RQ5: Local Processing Cost}"
        pos = text.find(marker)
        clean_b = gateb_results["summary"]["cleanM0"]
        unc_b = gateb_results["family_clustered_uncertainty"]["cleanM0"]
        passing = gateb["criteria"]["3_robust_value"]["passing_conditions"]
        robust = passing[0]
        robust_b = gateb_results["summary"][robust]
        ratio_ci = unc_b["candidate_ratio"]["CI95"]
        delta_ci_b = unc_b["candidate_minus_low_conf"]["CI95"]
        gate_text = f"""\\subsection{{Selective escalation}}
The frozen Gate B criteria pass. The rule escalates {100*clean_b['escalation_rate']:.1f}\\%
of clean cases, with an escalated/non-escalated error-density ratio of
{clean_b['concentration_ratio']:.2f} (95\\% CI [{ratio_ci[0]:.2f},{ratio_ci[1]:.2f}]).
Non-escalated recall/FPR are {clean_b['nonescalated_recall']:.3f}/
{clean_b['nonescalated_FPR']:.3f}. Under {robust}, escalation captures
{100*robust_b['fn_captured_fraction']:.1f}\\% of false negatives. Its concentration advantage
over matched low-confidence abstention has 95\\% CI [{delta_ci_b[0]:.2f},{delta_ci_b[1]:.2f}],
and EIP-specific signals change {gateb['criteria']['5_eip_specific_contribution']['escalation_decision_changes']}
decisions. These results are bounded to the tested populations and transformations.\n\n"""
        text = text[:pos] + gate_text + text[pos:]

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write(text)
    used = [
        "revision_v2/results/gdet_v2/gdet_v2_results.json",
        "revision_v2/results/gadv_v2/gadv_v2_results.json",
        "revision_v2/results/uncertainty/gadv_v2_bootstrap.json",
        "revision_v2/results/baselines/baselines_results.json",
        "revision_v2/results/ablations/ablations_results.json",
        "revision_v2/results/baselines/paired_family_bootstrap.json",
        "revision_v2/results/first_stop/first_stop_results.json",
        "revision_v2/results/gateB/gateB_verdict.json",
        "revision_v2/results/gateB/gateB_results.json",
    ]
    provenance = dict(
        source="paper_build/overleaf/main.tex",
        source_sha256=hashlib.sha256(open(SOURCE, "rb").read()).hexdigest(),
        applied_claim_corrections=["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8-retired"],
        first_stop_branch=fs_branch, gateB_verdict=gateb.get("verdict"),
        result_sources={p: hashlib.sha256(open(os.path.join(ROOT, p), "rb").read()).hexdigest()
                        for p in used if os.path.exists(os.path.join(ROOT, p))})
    with open(os.path.join(RV2, "manuscript", "integration_provenance.json"), "w") as f:
        json.dump(provenance, f, indent=2)
    print(f"[manuscript] wrote {OUT}; first_stop={fs_branch}; gateB={gateb.get('verdict')}")


if __name__ == "__main__":
    main()
