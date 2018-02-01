build:
	bin/build

.deps.stamp: requirements.txt
	pip install -r requirements.txt
	touch .deps.stamp

deps: .deps.stamp

test: deps
	pytest

.PHONY: deps test build
