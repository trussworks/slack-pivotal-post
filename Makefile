build:
	bin/build

deps:
	pip install -r requirements.txt

test:
	pytest
