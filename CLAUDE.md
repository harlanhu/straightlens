# StraightLens project instructions

## Stack

- Backend: Python 3.11+, FastAPI, Pillow, NumPy, OpenCV, SciPy
- Native engine: vendored IPOL C++ program under `third_party/ipol`
- Frontend: React 19, TypeScript, Vite, pnpm
- Tests: pytest and Playwright

## Commands

- Setup: `bash setup.sh`
- Run locally: `bash scripts/run_local.sh`
- Backend tests: `PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q`
- Frontend build: `pnpm --dir frontend run build`
- Browser tests: `pnpm --dir frontend test`

## Structure

- `backend/app/main.py`: FastAPI routes and static frontend hosting
- `backend/app/jobs.py`: persistent task queue and worker lifecycle
- `backend/app/engine/`: estimation, policy, remapping, and reverse mapping
- `frontend/src/`: React workbench
- `backend/tests/`: algorithm and API tests
- `frontend/tests/`: browser-level tests
- `third_party/ipol/`: upstream algorithm and license notes

Keep uploaded images, runtime data, virtual environments, build output, and credentials out of commits. Preserve the conservative correction policy and update tests when changing the API or geometry behavior.
