set shell := ["bash", "-c"]

default: test

run *args:
    python hashbrownie.py {{args}}

test:
    pytest -v

lint:
    ruff check .
    pylint hashbrownie.py test_hashbrownie.py
    mypy hashbrownie.py test_hashbrownie.py

format:
    ruff format .

install:
    uv sync
