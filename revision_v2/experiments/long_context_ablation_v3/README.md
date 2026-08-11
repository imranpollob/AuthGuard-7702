# Long-context ablation v3

This isolated experiment supplies the missing controlled evidence behind AuthGuard-Seq's
hierarchical long-context contribution.

Run a small implementation smoke test:

```bash
python3 revision_v2/experiments/long_context_ablation_v3/run_long_context_ablation_v3.py \
  --smoke
python3 revision_v2/experiments/long_context_ablation_v3/verify_outputs.py --smoke
```

Run or resume the frozen full protocol:

```bash
python3 revision_v2/experiments/long_context_ablation_v3/run_long_context_ablation_v3.py \
  --resume
python3 revision_v2/experiments/long_context_ablation_v3/verify_outputs.py
```

Long runs should be launched through `launch_detached.sh`, which records the worker PID,
exit status, and completion marker without tying training to an interactive shell.

