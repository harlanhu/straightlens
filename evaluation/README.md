# Evaluation data

The checked-in evaluation images are deterministic synthetic samples plus the
upstream IPOL building example. They are used to exercise the correction,
unchanged, weak-distortion, and reverse-mapping paths.

Generate the synthetic set and run the policy evaluation with:

```bash
.venv-local/bin/python scripts/evaluate.py --phase policy
```

The evaluation is a small engineering sample. It is useful for regression
checks, but it is not a calibrated accuracy benchmark.

The browser smoke scripts require the local application to be running:

```bash
cd frontend
node scripts/verify-examples.mjs
node scripts/verify-reverse.mjs
```
