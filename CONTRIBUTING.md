# Contributing to StraightLens

Thanks for helping improve StraightLens. The project is a local-first image tool for conservative radial lens-distortion correction.

## Development setup

Run `bash setup.sh` once, then start the application with `bash scripts/run_local.sh`.

Run the backend tests with:

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q
```

Build the frontend with:

```bash
pnpm --dir frontend run build
```

Browser tests require the local application and Chrome:

```bash
pnpm --dir frontend test
```

## Changes

Keep changes focused and preserve the existing behavior unless the change explicitly updates the product contract. Add or update tests for algorithm, API, and UI behavior. Explain user-visible changes and validation in the pull request.

Please do not commit credentials, local runtime data, virtual environments, generated output, or user-supplied images.
