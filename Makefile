.PHONY: install run test lint docker-build

install:
	python -m pip install -r requirements.txt

run:
	python app.py

test:
	python -m pytest -q tests

lint:
	python -m black --check .
	python -m flake8 app.py agents models tests

docker-build:
	docker build -t berrylens-ai .
