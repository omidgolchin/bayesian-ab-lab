PY := .venv/bin/python

.PHONY: setup data test analyze figures serve clean

setup:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

data:
	$(PY) scripts/download_data.py

test:
	$(PY) -m pytest -q

analyze:
	$(PY) -m src.bayesab.analyze

serve:
	cd docs && python3 -m http.server 8000
