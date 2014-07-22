PKGNAME = spillway
PYTHON ?= python

check:
	$(PYTHON) setup.py test

check-all:
	tox

clean:
	rm -rf build dist *.egg-info
	find . -iname '*.py[co]' -delete

coverage:
	coverage run --source=$(PKGNAME) setup.py test
	[ -n $$DISPLAY ] && \
		coverage report -m && \
		coverage html && \
		type xdg-open > /dev/null && \
		xdg-open htmlcov/index.html

dist: clean
	$(PYTHON) setup.py sdist
