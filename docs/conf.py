# Configuration file for the Sphinx documentation builder.
import sys
sys.path.insert(0, '../')
# needs_sphinx = '1.0'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'sphinx.ext.napoleon',
]

intersphinx_mapping = {
    'python': ('https://docs.python.org/3/',
               'https://docs.python.org/3/objects.inv'),
    'pika': ('https://pika.readthedocs.io/en/stable/',
             'https://pika.readthedocs.io/en/stable/objects.inv'),
}

templates_path = ['_templates']

source_suffix = '.rst'
master_doc = 'index'

project = 'rmqtools'
copyright = '2023, Christian Thompson, Paul Horton'
author = 'Christian Thompson, Paul Horton'
release = '1.0.0-alpha'
version = '.'.join(release.split('.')[0:2])

exclude_patterns = ['_build']
add_function_parenthesis = True
add_module_names = True
show_authors = True
pygments_style = 'sphinx'
modindex_common_prefix = ['rmqtools']
html_theme = 'default'
html_static_path = ['_static']

# autoclass_content = 'both'
