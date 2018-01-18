build:
	bin/build

deps:
	pip install -r requirements.txt

test:
	pytest

plan:
	cd terraform && \
	terraform plan

apply:
	cd terraform && \
	terraform apply

deploy: build apply
