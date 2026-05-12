#!/usr/bin/env bash
set -o errexit
set -o nounset

# Works whether Render's cwd is repo root or backend/ (paths are relative to this file).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

pip install pipenv

cd "$SCRIPT_DIR"
pipenv install --deploy --ignore-pipfile

cd "$REPO_ROOT/frontend"
if [ -f package-lock.json ]; then
  npm ci
else
  npm install
fi
npm run build

cd "$SCRIPT_DIR"
pipenv run python manage.py collectstatic --no-input
pipenv run python manage.py migrate
