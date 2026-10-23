#!/usr/bin/env bash
# One command from a fresh clone to a running app: environment, data, database, trained model.
#
#   ./setup.sh               ~10-15 min, downloads ~270 MB once (skipped if data/raw/ already has it)
#   ./setup.sh --with-eval   also regenerates reports/ (evaluation + robustness), ~10 min more
#
# Then: source venv/bin/activate && python manage.py runserver   ->  http://127.0.0.1:8000
set -euo pipefail
cd "$(dirname "$0")"

WITH_EVAL=false
[[ "${1:-}" == "--with-eval" ]] && WITH_EVAL=true

step() { printf '\n==> %s\n' "$1"; }

step "1/6 Python 3.12 environment in ./venv"
if command -v uv >/dev/null 2>&1; then
    [[ -d venv ]] || uv venv --python 3.12 venv
    uv pip install --python venv/bin/python -r requirements-notebooks.txt
elif command -v python3.12 >/dev/null 2>&1; then
    [[ -d venv ]] || python3.12 -m venv venv
    venv/bin/pip install -r requirements-notebooks.txt
else
    echo "Need uv (recommended: curl -LsSf https://astral.sh/uv/install.sh | sh) or python3.12." >&2
    exit 1
fi
PY=venv/bin/python

step "2/6 Database tables"
$PY manage.py migrate

step "3/6 Data: download MovieLens 25M + IMDb (md5-checked), build data/processed/"
$PY manage.py prepare_data

step "4/6 Load the movie catalog into the database"
$PY manage.py load_catalog

if $WITH_EVAL; then
    step "Extra: offline evaluation and robustness checks -> reports/"
    $PY manage.py evaluate_recommenders
    $PY manage.py robustness_check
fi

step "5/6 Train the served model -> data/models/"
$PY manage.py train_recommender

step "6/6 Tests"
$PY -m pytest -q

cat <<'EOF'

Setup complete. Start the app with:

    source venv/bin/activate
    python manage.py runserver          # open http://127.0.0.1:8000 and register a user

Optional:
    python manage.py createsuperuser    # a staff account can open /analytics/
    open notebooks/01_eda_and_results.ipynb in VS Code or Jupyter for the analysis
EOF
