help:
	@echo 'Individual commands:'
	@echo ' lint             - Lint the code with pylint and flake8 and check imports'
	@echo '                    have been sorted correctly'
	@echo ' test             - Run tests'
	@echo ' base             - Run the flask container without elasticsearch'
	@echo ' build            - Build both flask and elasticsearch containers'
	@echo ' up               - Run both flask and elasticsearch containers'
	@echo ' down             - Remove containers and network'
	@echo ''
	@echo 'Grouped commands:'
	@echo ' linttest         - Run lint and test'
lint:
	# Lint the python code
	pylint *
	flake8
	isort --check-only .
test:
	# Run python tests
	pytest -v -s tests/tests.py
linttest: lint test
base:
	docker compose -f development/docker-compose-base.yml up
build:
	docker compose -f development/docker-compose.yml up --build
up:
	docker compose -f development/docker-compose.yml up
down:
	docker compose -f development/docker-compose.yml down
build-local:
	python3 -m venv venv && source venv/bin/activate && pip install -r requirements/base.txt
down-local:
	source venv/bin/activate && deactivate
up-local:
	source venv/bin/activate && python -u -m app.video
