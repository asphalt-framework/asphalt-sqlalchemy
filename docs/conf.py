#!/usr/bin/env python3
from importlib.metadata import version

from packaging.version import parse

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx_autodoc_typehints",
    "sphinxcontrib.asyncio",
]

templates_path = ["_templates"]
source_suffix = ".rst"
master_doc = "index"
project = "asphalt-sqlalchemy"
author = "Alex Grönholm"
copyright = "2015, " + author

v = parse(version(project))
version = v.base_version
release = v.public

language = None

exclude_patterns = ["_build"]
pygments_style = "sphinx"
highlight_language = "python3"
todo_include_todos = False

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
htmlhelp_basename = project.replace("-", "") + "doc"

intersphinx_mapping = {
    "python": ("http://docs.python.org/3/", None),
    "asphalt": ("http://asphalt.readthedocs.io/en/latest/", None),
    "sqlalchemy": ("http://docs.sqlalchemy.org/en/latest/", None),
}
