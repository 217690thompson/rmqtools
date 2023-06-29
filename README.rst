Rmqtools
========
Rmqtools provides enhanced features for RabbitMQ development in Python.

Introduction
------------
Rmqtools is a set of wrappers for the Pika library, making it easier to use,
as well as integrating it with the threading library for multithreading
applications.

- Supports Python 3.8+
- Requires Pika 1.3.0+
- Rmqtools comes prebuilt with high-level wrappers for common applications.
  Some examples include a publishing/receiving a periodic status message,
  sending/receiving commands over RPC, etc. These high-level wrappers are
  located in the ``RmqConnection`` class.
- We recognize that there are more specific use cases that require fine
  tweaking to the individual parameters of the connection. As such, there
  are lower-level classes exposed for use cases outside of those contained
  in ``RmqConnection``. ``Publisher`` and ``Subscriber``, for example, allow
  for unique publish-subscribe relationships to be set up outside of the
  periodic status message use case contained in the high-level wrappers.

Documentation
-------------
Documentation coming soon.

Examples
--------
Below are some examples of several of the high-level use cases. Detailed
examples can also be found in the ``examples`` directory.

Periodic Status Messages
~~~~~~~~~~~~~~~~~~~~~~~~
This is an example of a publisher-subscriber relationship that publishes
status messages on a periodic basis. There are two files, ``publisher.py``
and ``subscriber.py``.

publisher.py:

.. code :: python

    from rmqtools import RmqConnection

    rmq = RmqConnection(host='rabbit-1')
    rmq.set_status_exchange('logs')

    @rmq.publish_status(1, 'device.1.status')
    def send_status():
        status = 'running'
        msg = {'status': status}
        return msg

    rmq.run()

subscriber.py:

.. code :: python

    from datetime import datetime
    import json

    from rmqtools import RmqConnection

    rmq = RmqConnection(host='rabbit-3')
    rmq.set_status_exchange('logs')

    response_count = {}
    msg_times = [datetime.now()]

    @rmq.subscribe_status('device_logs', ['device.*.status'])
    def handle_response(channel, method, props, body):
        try:
            data = json.loads(body)
        except:
            data = {'status': 'down'}
        running_count = response_count.get('running', 0)
        down_count = response_count.get('down', 0)
        if data.get('status') == 'running':
            running_count = running_count + 1
        else:
            down_count = down_count + 1
        response_count.update(running=running_count, down=down_count)

        # display the total messages received every 10 seconds
        total = sum(response_count.values())
        now = datetime.now()
        if (now - msg_times[-1]).seconds >= 10:
            msg_times.pop() # must use in-place methods because of threading
            msg_times.append(now)
            print(f"[{now.isoformat()}] Total status messages received: "
                  f"{total}\n")

    rmq.run()

Exposed Classes
---------------

- ``rmqtools.RmqConnection`` - high-level wrappers for common use cases; all
  methods in this class are threaded to ensure consistent timing
- ``rmqtools.Connection`` - the base class that interacts with the Pika
  library; each thread requires a unique Connection object to operate properly
- ``rmqtools.Publisher`` - provides methods for publishing messages with or
  without routing keys
- ``rmqtools.Subscriber`` - provides methods for subscribing to published
  messages with routing keys
- ``rmqtools.RpcClient`` - provides methods for setting up an RPC client to
  send requests and receive responses
- ``rmqtools.RpcServer`` - provides methods for setting up an RPC server to
  handle requests with worker functions
- ``rmqtools.ResponseObject`` - a ``NamedTuple`` that is used in RPC calls;
  consists of two elements: ``args`` and ``kwargs``

  - ``args : list`` - a list of positional arguments to pass to a response
    handler, defaults to ``[]``; operates like ``*args``
  - ``kwargs : dict`` - a dictionary of keyword arguments to pass to the
    response handler, defaults to ``{}``; operates like ``**kwargs``
