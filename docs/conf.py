#!/usr/bin/env python3
import pkg_resources


extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx_autodoc_typehints'
]

templates_path = ['_templates']
source_suffix = '.rst'
master_doc = 'index'
project = 'asphalt-sqlalchemy'
author = 'Alex Grönholm'
copyright = '2015, ' + author

v = pkg_resources.get_distribution('asphalt-sqlalchemy').parsed_version
version = v.base_version
release = v.public

language = None

exclude_patterns = ['_build']
pygments_style = 'sphinx'
todo_include_todos = False

html_theme = 'classic'
html_static_path = ['_static']
htmlhelp_basename = 'asphaltsqlalchemydoc'

intersphinx_mapping = {'python': ('http://docs.python.org/3/', None),
                       'asphalt': ('http://asphalt.readthedocs.org/en/latest/', None),
                       'sqlalchemy': ('http://docs.sqlalchemy.org/en/latest/', None)}
