.PHONY: dev build

dev:
	briefcase dev

build:
	rm -rf build && rm -rf dist && briefcase build macOS && briefcase package macOS
