Frequently Asked Questions
==========================

- Is Rmqtools threaded?

    The high-level API in the Rmqtools library, ``RmqConnection`` contains
    mostly threaded methods, while the underlying classes are not threaded,
    but can be threaded if desired. The important thing to remember when
    threading is that each thread must have a unique connection, created in
    that thread. See :doc:`/modules/rmq` for more details.

- How do I report a bug with Rmqtools?

    The `main Rmqtools repository <https://github.com/217690thompson/rmqtools>`_
    is hosted on `GitHub <https://github.com>`_ and we use the
    `Issue tracker <https://github.com/217690thompson/rmqtools/issues>`_ to
    handle bug reports.

- How can I contribute to Rmqtools?

    You can fork the project on GitHub and issue Pull Requests when you believe
    you have something solid to be added to the main repository.
