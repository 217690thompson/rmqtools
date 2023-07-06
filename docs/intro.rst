Introduction to Rmqtools
========================
This introduction guide will cover the basics of using RabbitMQ and Rmqtools.
For more detailed information about the underlying Pika library, please read
`Pika's documentation <https://pika.readthedocs.org/en/stable/>`_. For more
information about the underlying RabbitMQ messaging system, please visit
`RabbitMQ's main site <https://rabbitmq.com/>`_.

High-level API
--------------
The high-level API consists of the RmqConnection class and the ResponseObject
structure. The high-level API implements wrappers for several common RabbitMQ
use cases. All methods in the high-level API are threaded, so as to make sure
that Pika's :class:`~pika.adapters.blocking_connection.BlockingConnection`
doesn't interfere with other connections. Essentially, the threading allows
for multiple concurrent producers and consumers to run in the same program.
Detailed documentation for the high-level API can be found at
:doc:`/modules/rmq`, and additional examples can be found in :doc:`/examples`.

Example of a publisher that publishes log messages once per second::

    import rmqtools

    rmq = rmqtools.RmqConnection(host='rabbit-1')
    rmq.set_status_exchange('logs')

    @rmq.publish_status(1, 'device.1.status')
    def send_status():
        status = 'running'
        msg = {'status': status}
        return msg

    rmq.run()

Example of a subscriber that consumes those log messages::

    import rmqtools
    import json

    rmq = rmqtools.RmqConnection(host='rabbit-1')
    rmq.set_status_exchange('logs')

    @rmq.subscribe_status('device_logs', 'device.*.status')
    def handle_response(channel, method, props, body):
        try:
            data = json.loads(body)
        except:
            data = {'status': 'down'}
        print(data.get('status'))

    rmq.run()

Notice how each of these examples end in ``rmq.run()``. This is not a
coincidence, but rather a requirement. Any program that uses the high-level
API must always use the :py:meth:`RmqConnection.run` method at the end to
initiate the program. The method decorators in :class:`RmqConnection` create
threads, and the :py:meth:`RmqConnection.run` method starts all the threads
and waits for either user input or a system interrupt to stop the threads.

Low-level API
-------------
Coming soon!

More examples coming soon!
~~~~~~~~~~~~~~~~~~~~~~~~~~
