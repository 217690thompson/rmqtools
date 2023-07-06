.. rmqtools documentation master file, created by
   sphinx-quickstart on Thu Jun 29 13:22:51 2023.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Rmqtools!
====================
Rmqtools provides enhanced features for RabbitMQ development in Python. It is
based on the Pika_ library.

If you have not developed with Rmqtools, Pika, or RabbitMQ before, the
:doc:`intro` documentation is a good place to get started.

Installing Rmqtools
-------------------

Prerequisites
~~~~~~~~~~~~~

* Pika (`version 1.3.0+ <https://pika.readthedocs.io/en/stable/#installing-pika>`_)
* RabbitMQ (`version 3.12.0+ <https://rabbitmq.com/download.html>`_)

Note: Pika should be automatically installed when installing Rmqtools

Rmqtools is not currently available for download with PyPI. Once it is
available, it can be installed via pip::

    pip install rmqtools

To install the latest version before Rmqtools is available on PyPI, use the
latest_ release on GitHub and download ``rmqtools-<version>-py3-none-any.whl``.
Then install the wheel file with pip::

    pip install rmqtools-<version>-py3-none-any.whl

To install directly from source, run "python setup.py install" in the root
source directory.

Using Rmqtools
--------------
.. toctree::
   :glob:
   :maxdepth: 2

   intro
   modules/index
   examples
   faq
   contributors


Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. aliases below here
.. _Pika: https://pika.readthedocs.io
.. _latest: https://github.com/217690thompson/rmqtools/releases/latest
.. |repo_base| replace:: https://github.com/217690thompson/rmqtools
