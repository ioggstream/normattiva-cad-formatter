clean:
	rm -fr docs/_*
	rm -fr _*

build:
	tox -e build
