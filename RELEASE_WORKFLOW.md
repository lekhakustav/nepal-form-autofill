# Release Workflow

## Branch Model

- `main`: stable branch
- `feature/*`: day-to-day work branches
- `release/*`: optional stabilization branches before a public push

## Recommended Flow

1. Start from `main`.
2. Create a branch for one change only.
3. Keep frontend, backend, and portal automation checks green locally.
4. Merge back into `main` when the change is ready.
5. Tag the commit if you want a public release marker.

## What To Verify Before Merge

- `npm run build`
- backend starts cleanly
- `/api/health` responds
- portal autofill still opens a local browser and never presses final submit

## Notes

- Keep secrets in `.env`, not in the repository.
- Do not commit logs, browser profiles, OCR language files, or build outputs.
