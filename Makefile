.PHONY: help doctor seed reset test evidence board console graph demo clean strip-reference

help:
	@echo "  make doctor      check this machine before class"
	@echo "  make seed        create the database"
	@echo "  make test        the whole evidence suite (A observed, B and C asserted)"
	@echo "  make evidence    the same, as a readable report"
	@echo "  make board       print the Attack Board"
	@echo "  make console     control room on http://localhost:8899"
	@echo "  make graph       the node/edge structure"
	@echo "  make demo        facilitator: the same attack against reference controls"
	@echo "  make strip-reference   remove the answer key before handing the repo out"

doctor:
	python -m kestrel doctor

seed:
	python -m kestrel seed

reset:
	python -m kestrel seed --reset

test:
	python -m unittest discover -s tests -v

graph:
	python -m kestrel graph

evidence:
	python -m kestrel --narrow evidence all

board:
	python -m kestrel --narrow board --markdown

console:
	python -m kestrel --narrow console

demo:
	KESTREL_CONTROLS=reference python -m kestrel --narrow evidence all

clean:
	rm -f kestrel.db board.md
	find . -name __pycache__ -type d -exec rm -rf {} +

strip-reference:
	rm -rf reference
	@echo "reference/ removed. Nothing in kestrel/ imports it."
