set shell := ["/bin/zsh", "-lc"]

setup:
    @echo "Python dependencies are provided by the declarative workstation; no repo-local venv is required."
    @echo "PYTHONPATH=src python -m label_lab.main --help"
    PYTHONPATH=src python -m label_lab.main --help >/dev/null

test:
    python -m pytest -q

lint:
    python -m ruff check .

typecheck:
    python -m mypy src
