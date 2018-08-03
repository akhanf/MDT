#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# mdt documentation build configuration file, created by
# sphinx-quickstart on Tue Jul  9 22:26:36 2013.
#
# This file is execfile()d with the current directory set to its
# containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

import sys
import os
from datetime import datetime
from functools import wraps
from unittest.mock import MagicMock
import builtins
import glob
import re
from textwrap import dedent


mock_as_class = ['QWidget', 'QMainWindow', 'QDialog', 'QObject',
                 'CLRoutine', 'InputData', 'NumDiffInfo', 'SampleModelInterface',
                 'NumericalDerivativeInterface', 'CLFunction', 'SimpleCLFunction']
mock_as_decorator = ['pyqtSlot']
mock_modules = ['mot', 'pyopencl', 'PyQt5', 'matplotlib', 'mpl_toolkits']


def mock_decorator(*args, **kwargs):
    """Mocked decorator, needed in the case we need to mock a decorator"""
    def _called_decorator(dec_func):
        @wraps(dec_func)
        def _decorator(*args, **kwargs):
            return dec_func()
        return _decorator
    return _called_decorator


class MockNamedComponent(MagicMock):
    """Some of the loaded components require the __name__ property to be set, this mock class makes that so."""
    @classmethod
    def __name__(cls):
        return MagicMock()


class MockModule(MagicMock):
    """The base mocking class. This mimics a module."""
    @classmethod
    def __getattr__(cls, name):
        if name in mock_as_class:
            class MockClass(MagicMock):
                @classmethod
                def __getattr__(cls, name):
                    return MockModule()
            return MockClass
        if name in mock_as_decorator:
            return mock_decorator
        return MockNamedComponent()


orig_import = __import__


def import_mock(name, *args, **kwargs):
    """Mock all modules starting with one of the mock_modules names."""
    if any(name.startswith(s) for s in mock_modules):
        return MockModule()
    return orig_import(name, *args, **kwargs)

builtins.__import__ = import_mock


def get_cli_doc_items():
    items = []

    for file in sorted(glob.glob('../mdt/cli_scripts/*.py')):
        module_name = os.path.splitext(os.path.basename(file))[0]
        command_name = module_name.replace('_', '-')

        def get_command_class_name():
            with open(file) as f:
                match = re.search(r'class (\w*)\(', f.read())
                if match:
                    return match.group(1)
                return None

        command_class_name = get_command_class_name()

        if command_class_name is not None:
            item = dedent("""
                .. _cli_index_{command_name}:

                {command_name}
                {command_name_highlight}

                .. argparse::
                   :ref: mdt.cli_scripts.{module_name}.get_doc_arg_parser
                   :prog: {command_name}
            """).format(command_name=command_name, command_name_highlight='='*len(command_name),
                        module_name=module_name)

            items.append(item)
    return items

# enable again when supported on read the docs
# with open('auto_gen_cli_index.rst', 'w') as f:
#     for item in get_cli_doc_items():
#         f.write(item[1:] + '\n\n\n')


# If extensions (or modules to document with autodoc) are in another
# directory, add these directories to sys.path here. If the directory is
# relative to the documentation root, use os.path.abspath to make it
# absolute, like shown here.
#sys.path.insert(0, os.path.abspath('..'))

# Building from inside the docs/ directory?
if os.path.basename(os.getcwd()) == 'docs':
    sys.path.insert(1, os.path.abspath(os.path.join('..')))


os.environ["MDT.LOAD_COMPONENTS"] = "0"
import mdt

# -- General configuration ---------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.viewcode', 'sphinx.ext.napoleon', 'sphinx.ext.intersphinx',
              'sphinx.ext.mathjax', 'sphinxcontrib.bibtex'] # 'sphinxarg.ext' # enable again when supported on read the

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The encoding of source files.
#source_encoding = 'utf-8-sig'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'MDT'
year = datetime.now().year
copyright = u'%d Robbert Harms' % year

# The version info for the project you're documenting, acts as replacement
# for |version| and |release|, also used in various other places throughout
# the built documents.
#
# The short X.Y version.
version = mdt.__version__
# The full version, including alpha/beta/rc tags.
release = mdt.__version__

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#language = None

# There are two options for replacing |today|: either, you set today to
# some non-false value, then it is used:
#today = ''
# Else, today_fmt is used as the format for a strftime call.
#today_fmt = '%B %d, %Y'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['_build', '_getting_started', '_dynamic_modules', 'auto_gen_cli_index.rst']

# The reST default role (used for this markup: `text`) to use for all
# documents.
#default_role = None

# If true, '()' will be appended to :func: etc. cross-reference text.
add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
#add_module_names = True

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
#show_authors = False

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# A list of ignored prefixes for module index sorting.
modindex_common_prefix = ['mdt.']

# If true, keep warnings as "system message" paragraphs in the built
# documents.
#keep_warnings = False

# map to other projects
intersphinx_mapping = {
    'mot': ('http://mot.readthedocs.io/en/latest/', None),
}


# -- Options for HTML output -------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = 'alabaster'

# Theme options are theme-specific and customize the look and feel of a
# theme further.  For a list of options available for each theme, see the
# documentation.
html_theme_options = {
    'show_powered_by': False,
    'description': "Microstructure Diffusion Toolbox",
    'logo_name': True,
    'sidebar_collapse': True,
    'fixed_sidebar': False,
    'extra_nav_links': {'Module index': 'py-modindex.html'}
}


# Add any paths that contain custom themes here, relative to this directory.
#html_theme_path = []

# The name for this set of Sphinx documents.  If None, it defaults to
# "<project> v<release> documentation".
#html_title = None

# A shorter title for the navigation bar.  Default is the same as
# html_title.
#html_short_title = None

# The name of an image file (relative to this directory) to place at the
# top of the sidebar.
#html_logo = None

# The name of an image file (within the static path) to use as favicon
# of the docs.  This file should be a Windows icon file (.ico) being
# 16x16 or 32x32 pixels large.
html_favicon = '_static/html_favicon.ico'

# Add any paths that contain custom static files (such as style sheets)
# here, relative to this directory. They are copied after the builtin
# static files, so a file named "default.css" will overwrite the builtin
# "default.css".
html_static_path = ['_static']

# If not '', a 'Last updated on:' timestamp is inserted at every page
# bottom, using the given strftime format.
#html_last_updated_fmt = '%b %d, %Y'

# If true, SmartyPants will be used to convert quotes and dashes to
# typographically correct entities.
#html_use_smartypants = True

# Custom sidebar templates, maps document names to template names.
html_sidebars = {
   '**': ['about.html',
          'navigation.html',
          'searchbox.html']
}

# Additional templates that should be rendered to pages, maps page names
# to template names.
#html_additional_pages = {}

# If false, no module index is generated.
#html_domain_indices = True

# If false, no index is generated.
#html_use_index = True

# If true, the index is split into individual pages for each letter.
#html_split_index = False

# If true, links to the reST sources are added to the pages.
html_show_sourcelink = False

# If true, "Created using Sphinx" is shown in the HTML footer.
# Default is True.
html_show_sphinx = False

# If true, "(C) Copyright ..." is shown in the HTML footer.
# Default is True.
#html_show_copyright = True

# If true, an OpenSearch description file will be output, and all pages
# will contain a <link> tag referring to it.  The value of this option
# must be the base URL from which the finished HTML is served.
#html_use_opensearch = ''

# This is the file name suffix for HTML files (e.g. ".xhtml").
#html_file_suffix = None

# Output file base name for HTML help builder.
htmlhelp_basename = 'mdtdoc'


# -- Options for LaTeX output ------------------------------------------

latex_elements = {
    # The paper size ('letterpaper' or 'a4paper').
    'papersize': 'a4paper',

    # The font size ('10pt', '11pt' or '12pt').
    'pointsize': '10pt',

    # Additional stuff for the LaTeX preamble.
    'preamble': r"""
        \makeatletter
        \def\@makechapterhead#1{%
          %%%%\vspace*{50\p@}% %%% removed!
          {\parindent \z@ \raggedright \normalfont
            \ifnum \c@secnumdepth >\m@ne
                \huge\bfseries \@chapapp\space \thechapter
                \par\nobreak
                \vskip 20\p@
            \fi
            \interlinepenalty\@M
            \Huge \bfseries #1\par\nobreak
            \vskip 40\p@
          }}
        \def\@makeschapterhead#1{%
          %%%%%\vspace*{50\p@}% %%% removed!
          {\parindent \z@ \raggedright
            \normalfont
            \interlinepenalty\@M
            \Huge \bfseries  #1\par\nobreak
            \vskip 40\p@
          }}
        \makeatother

        \setcounter{secnumdepth}{1}
        
        \usepackage{titlesec}
        \titlespacing*{\section}{0pt}{6ex plus 1ex minus .2ex}{1ex plus .1ex}
        \titlespacing*{\subsection}{0pt}{4ex plus 1ex minus .2ex}{0ex plus .1ex}
        \titlespacing*{\subsubsection}{0pt}{3ex plus 1ex minus .2ex}{0ex}
    """,
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass
# [howto/manual]).
latex_documents = [
    ('index_latex', 'mdt.tex',
     u'Microstructure Diffusion Toolbox',
     u'Robbert Harms', 'manual'),
]

# The name of an image file (relative to this directory) to place at
# the top of the title page.
latex_logo = '../mdt/data/logo_docs.png'

# For "manual" documents, if this is true, then toplevel headings
# are parts, not chapters.
#latex_use_parts = False

# If true, show page references after internal links.
#latex_show_pagerefs = False

# If true, show URL addresses after external links.
#latex_show_urls = False

# Documents to append as an appendix to all manuals.
#latex_appendices = []

# If false, no module index is generated.
#latex_domain_indices = True


# -- Options for manual page output ------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    ('index_man', 'mdt',
     u'Microstructure Diffusion Toolkit',
     [u'Robbert Harms'], 1)
]

# If true, show URL addresses after external links.
#man_show_urls = False


# -- Options for Texinfo output ----------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    ('index_latexz', 'mdt',
     u'Microstructure Diffusion Toolbox',
     u'Robbert Harms',
     'mdt',
     'One line description of project.',
     'Miscellaneous'),
]

# Documents to append as an appendix to all manuals.
#texinfo_appendices = []

# If false, no module index is generated.
#texinfo_domain_indices = True

# How to display URL addresses: 'footnote', 'no', or 'inline'.
#texinfo_show_urls = 'footnote'

# If true, do not generate a @detailmenu in the "Top" node's menu.
#texinfo_no_detailmenu = False

# -- Options for napoleon ----
autoclass_content = 'both'
