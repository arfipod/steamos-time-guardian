SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

.PHONY: help bootstrap build test lint format install uninstall status diagnose package smoke clean
help:
	@printf '%s\n' \
	  'bootstrap  Create a local development environment' \
	  'build      Compile Python and the Decky frontend' \
	  'test       Run automated tests' \
	  'lint       Run repository checks' \
	  'format     Format supported source files' \
	  'install    Install for the current user' \
	  'uninstall  Remove program files, retain data' \
	  'status     Show service status' \
	  'diagnose   Generate diagnostics' \
	  'package    Build distributable archives' \
	  'smoke      Exercise the daemon in simulation mode' \
	  'clean      Remove generated files'
bootstrap:
	./scripts/bootstrap-dev.sh
build:
	./scripts/build.sh
test:
	./scripts/test.sh
lint:
	./scripts/lint.sh
format:
	./scripts/format.sh
install:
	./scripts/install-user.sh
uninstall:
	./scripts/uninstall-user.sh
status:
	./scripts/status.sh
diagnose:
	./scripts/diagnose.sh
package:
	./scripts/package.sh
smoke:
	./scripts/smoke-test.sh
clean:
	rm -rf build dist .coverage htmlcov .pytest_cache .mypy_cache .ruff_cache decky-plugin/dist daemon/src/*.egg-info
