"""Highest level RabbitMQ wrapper.

Contains high-level wrappers for RabbitMQ, implementing many common
use cases with built-in threading. The RmqConnection object is meant to
be used on a clustered RabbitMQ server with quorum queues. For details
on clustering and quorum queues, please see the RabbitMQ documentation
of both (https://www.rabbitmq.com/clustering.html and
https://www.rabbitmq.com/quorum-queues.html). For a good visualization of
the underlying Raft algorithm that quorum queues use, see
http://thesecretlivesofdata.com/raft/. Most of the functional methods
contained in RmqConnection are meant to be used as method decorators, though
the private methods they employ can be used in a standalone manner. See
the examples section below.
"""

import functools
import signal
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Literal, Tuple

import pika
from pika.exchange_type import ExchangeType
from rmqtools import (Connection, Publisher, ResponseObject, RpcClient,
                      RpcServer, Subscriber)


class RmqConnection():
    """Contains high-level wrappers for RabbitMQ, implementing many common
    use cases with built-in threading. The RmqConnection object is meant to
    be used on a clustered RabbitMQ server with quorum queues. Most of the
    functional methods contained in this class are meant to be used as method
    decorators, though the private methods they employ can be used in a
    standalone manner.

    Parameters
    ----------
    username : str, optional
        The username to use when logging into the RabbitMQ server, defaults to
        'guest'. Sometimes 'guest' login is not allowed, so it is recommended
        to set up a different user for connecting. The username here must
        correspond to a user with admin privileges.
    password : str, optional
        The password to use when logging into RabbitMQ, defaults to 'guest'.
    host : str, optional
        The hostname of the RabbitMQ server, defaults to 'localhost'. Using
        localhost to host RabbitMQ is fine for some applications, but it is
        not recommended. If using a clustered RabbitMQ server, any of the
        cluster hostnames works (e.g. 'rabbit-1' or 'rabbit-2'). This can also
        use an IP address intead of a hostname, but hostnames are recommended.
    port : int, optional
        The port of the RabbitMQ server, defaults to 5672. Most RabbitMQ
        servers use port 5672, but some applications may have a different port.
        For example, a virtual cluster hosted on one machine may use ports
        5672, 5673, and 5674.
    autoconnect : bool, optional
        Automatically run the ``connect`` method to sync to the Connection
        object, defaults to True. It is recommended to leave autoconnect
        enabled, but some use cases may require connecting at a specific time.
        If this is required, run the ``connect`` method to perform the connection
        tasks.

    Attributes
    ----------
    username : str
        The username used to authenticate with the RabbitMQ server.
    password : str
        The password used for RabbitMQ authentication.
    host : str
        The host (ip or hostname) of the RabbitMQ server (or one of the
        clustered servers).
    port : int
        The port the RabbitMQ server is using (usually 5672).
    autoconnect : bool
        Automatically run the ``connect`` method on initialization if True.
    threads : List[threading.Thread]
        A list of the threads contained within the RmqConnection instance.
        These threads are started with the ``run`` method and stoped with the
        ``stop`` method.
    stop_event : threading.Event
        The threading Event used to shutdown all the threads running RabbitMQ
        processes.
    exchanges : Dict[str, Tuple[str, pika.ExchangeType]]
        A dictionary containing information about all the exchanges involved
        in this RMQ process. The key is the purpose of the exchange (e.g.
        'logs'), and the value is a tuple of the exchange name and the
        exchange type.
    publishers : Dict[str, Publisher]
        A dictionary containing information about all the publishers involved
        in this RMQ process. The key is the name of the publisher (e.g.
        'status') and the value is a Publisher object. These are usually auto-
        generated within the method decorators and are named with the routing
        key they correspond to (e.g. 'device.1.status').
    publish_props : Dict[str, pika.BasicProperties]
        A dictionary containing information about all the publish properties
        involved in this RMQ process. The key is the name of the Publisher (so
        as to map it directly with the ``publishers`` attribute) and the value
        is a pika.BasicProperties object. This is used to pass properties into
        the Publisher's connection to the server and is usually auto-generated.
    subscribers : Dict[str, Subscriber]
        A dictionary containing information about all the subscribers involved
        in this RMQ process. The key is the name of the subscriber (e.g.
        'device_logs') and the value is a Subscriber object. These are usually
        auto-generated within the method decorators used for subscribing.
    response_handlers : Dict[str, (Any) -> Any]
        A dictionary containing information about all the response handlers
        involved in this RMQ process. The key is an identifier and the value
        is a callback function to serve as the response handler for a specific
        process. These response handlers are used in the RPC processes to
        determine which function needs to be called to handle the RPC response.
        The identifier is usually related to a command system (e.g.
        'device_command').
    """

    def __init__(self, username='guest', password='guest', host='localhost',
                 port=5672, autoconnect=True) -> None:
        """Create an instance of the high-level RmqConnection class.

        Parameters
        ----------
        username : str, optional
            The username to use when logging into the RabbitMQ server, defaults to
            'guest'. Sometimes 'guest' login is not allowed, so it is recommended
            to set up a different user for connecting. The username here must
            correspond to a user with admin privileges.
        password : str, optional
            The password to use when logging into RabbitMQ, defaults to 'guest'.
        host : str, optional
            The hostname of the RabbitMQ server, defaults to 'localhost'. Using
            localhost to host RabbitMQ is fine for some applications, but it is
            not recommended. If using a clustered RabbitMQ server, any of the
            cluster hostnames works (e.g. 'rabbit-1' or 'rabbit-2'). This can also
            use an IP address intead of a hostname, but hostnames are recommended.
        port : int, optional
            The port of the RabbitMQ server, defaults to 5672. Most RabbitMQ
            servers use port 5672, but some applications may have a different port.
            For example, a virtual cluster hosted on one machine may use ports
            5672, 5673, and 5674.
        autoconnect : bool, optional
            Automatically run the ``connect`` method to sync to the Connection
            object, defaults to True. It is recommended to leave autoconnect
            enabled, but some use cases may require connecting at a specific time.
            If this is required, run the ``connect`` method to perform the connection
            tasks.
        """
        self.username = username
        self.password = password
        self.host = host
        self.port = port
        self.autoconnect = autoconnect

        self.threads: List[threading.Thread]
        self.threads = []
        self.stop_event = threading.Event()

        self.exchanges: Dict[str, Tuple[str, ExchangeType]]
        self.exchanges = {}

        self.publishers: Dict[str, Publisher]
        self.publishers = {}

        self.publish_props: Dict[str, pika.BasicProperties]
        self.publish_props = {}

        self.subscribers: Dict[str, Subscriber]
        self.subscribers = {}

        self.response_handlers: Dict[str, Callable[[Any], Any]]
        self.response_handlers = {}

        self.timeout_handlers: Dict[str, Callable[[int], None]]
        self.timeout_handlers = {}

        def handle_exit(sig, frame):
            print('Main thread interrupted by user. '
                  'Shutting down all child threads.')
            self.stop()
            sys.exit(0)

        #signal.signal(signal.SIGINT, handle_exit)
        signal.signal(signal.SIGTERM, handle_exit)

    def _get_connection(self) -> Connection:
        conn = Connection(self.username, self.password, self.host, self.port,
                          self.autoconnect)
        return conn

    def set_status_exchange(self, name:str) -> None:
        """Set the exchange used for status messages.

        Parameters
        ----------
        name : str
            The name of the status exchange.
        """
        self.exchanges.update({'status': (name, ExchangeType.topic)})

    def set_command_exchange(self, name:str) -> None:
        """Set the exchange used for commands.

        Parameters
        ----------
        name : str
            The name of the command exchange.
        """
        self.exchanges.update({'command': (name, ExchangeType.direct)})

    def add_exchange(self, name:str, purpose:str, etype:ExchangeType) -> None:
        """Add an exchange.

        Parameters
        ----------
        name : str
            The name of the exchange.
        purpose : str
            The purpose of the exchange (e.g. 'logs').
        etype : ExchangeType
            They type of the exchange (e.g. pika.ExchangeType.topic for a
            topic exchange).
        """
        self.exchanges.update({purpose: (name, etype)})

    def get_publisher(self, name:str, err=True) -> Publisher:
        """Get a Publisher object by name.

        Parameters
        ----------
        name : str
            The name of the publisher.
        err : bool, optional
            Raise an error if no publishers with that name are found, by
            default True

        Returns
        -------
        Publisher
            Returns the publisher corresponding to the given name.

        Raises
        ------
        ValueError
            If err is True and there isn't a publisher with the given name.
        """
        publisher = self.publishers.get(name, False)
        if err and not publisher:
            raise ValueError(f"A publisher with name '{name}' could not be "
                             f"found.")
        return publisher

    def add_publisher(self, name:str,
                      ptype:Literal['topic', 'fanout', 'direct']='topic',
                      exchange=''):
        """Add a publisher.

        See documentation for rmqtools.Publisher for
        additional information about publisher creation.

        Parameters
        ----------
        name : str
            The name of the publisher.
        ptype : Literal['topic'] | Literal['fanout'] | Literal['direct'], optional
            The type of publisher, either 'topic', 'fanout', or 'direct', by
            default 'topic'.
        exchange : str, optional
            The name of the exchange used by the new publisher, by default ''.

        Raises
        ------
        ValueError
            If an invalid publisher type is given.
        ValueError
            If a publisher with the same name already exists.
        """
        if ptype not in ['topic', 'fanout', 'direct']:
            raise ValueError(f"Publisher type must be either 'topic', "
                             f"'fanout', or 'direct', not '{ptype}'")
        publisher = Publisher(ptype, exchange=exchange)
        pub = self.get_publisher(name, err=False)
        if pub:
            raise ValueError(f"A publisher with name '{name}' already exists!")
        self.publishers.update({name: publisher})
        self.publish_props.update({name: None})

    def set_publish_props(self, publisher_name:str,
                          publish_props:pika.BasicProperties=None) -> None:
        """Updates ``publish_props`` with the properties for a publisher.

        Parameters
        ----------
        publisher_name : str
            The name of the Publisher to set the properties of.
        publish_props : pika.BasicProperties, optional
            The pika BasicProperties object to set as the publisher properties,
            by default None. Most use cases will use None here.
        """
        # throws error if publisher doesn't exist
        self.get_publisher(publisher_name)
        self.publish_props.update({publisher_name: publish_props})

    def get_subscriber(self, name:str, err=True) -> Subscriber:
        """Get a subscriber by name.

        Parameters
        ----------
        name : str
            The name of the subscriber.
        err : bool, optional
            Throw an error if no subscribers with that name are found, by
            default True.

        Returns
        -------
        Subscriber
            The subscriber corresponding with the given name.

        Raises
        ------
        ValueError
            If err is True and no subscriber exists with that name.
        """
        subscriber = self.subscribers.get(name, False)
        if err and not subscriber:
            raise ValueError(f"A subscriber with name '{name}' could not be "
                             f"found.")
        return subscriber

    def add_subscriber(self, name:str, queue:str, exchange='',
                       etype:ExchangeType=ExchangeType.topic,
                       routing_keys:List[str]=[]) -> None:
        """Add a subscriber.

        See documentation for rmqtools.Subscriber for more information about
        subscriber creation.

        Parameters
        ----------
        name : str
            The name of the subscriber.
        queue : str
            The name of the queue associated with the subscriber.
        exchange : str, optional
            The name of the exchange associated wit the subscriber, by
            default ''.
        etype : ExchangeType, optional
            The type of the exchange, by default ExchangeType.topic.
        routing_keys : List[str], optional
            A list of routing keys to bind to the subscriber, by default [].

        Raises
        ------
        ValueError
            If a subscriber with the same name already exists.
        """
        subscriber = Subscriber(queue=queue, exchange=exchange, etype=etype,
                                routing_keys=routing_keys,
                                queue_arguments={'durable': True})
        sub = self.get_subscriber(name, err=False)
        if sub:
            raise ValueError(f"A subscriber with name '{name}' already "
                             f"exists!")
        self.subscribers.update({name: subscriber})

    def start(self):
        """Start all the threads in the ``threads`` attribute.
        """
        for thread in self.threads:
            thread.start()

    def run(self):
        """Run the main IO loop for RmqConnection.

        Starts the threads then waits for user input. Any user input will
        trigger the stop command to shutdown all threads.
        """
        print("Starting all RabbitMQ threads. Press enter at any time to "
            "shutdown all child threads.")
        self.start()
        try:
            input()
            print("Quit command received. Shutting down all child threads...")
        except KeyboardInterrupt as e:
            print("Main thread interrupted by user. Shutting down all child "
                "threads...")
        self.stop()

    def stop(self):
        """Safely shutdown all the running threads.
        """
        self.stop_event.set()
        for thread in self.threads:
            thread.join()

    def _publish_status(self, func:Callable[[Any], Any], interval: float,
                        routing_key: str, *args, **kwargs):
        """Publish a status message periodically.

        This method is not automatically threaded, but it is thread safe. It
        checks RmqConnection.stop_event.is_set() to determine if it should
        shut down.

        Parameters
        ----------
        func : (Any) -> Any
            The function that generates the message to be sent via RabbitMQ.
            It must return a JSON-serializable object.
        interval : float
            The time waited between sending each subsequent message.
        routing_key : str
            The routing key to use when publishing.
        args : List[Any], optional
            A list of positional arguments to pass to ``func``.
        kwargs : Dict[str, Any], optional
            A dictionary of keyword arguments to pass to ``func``.
        """
        conn = self._get_connection()
        exchange = self.exchanges.get('status', ('', ExchangeType.topic))
        exchange_name = exchange[0]
        ptype = exchange[1].name
        self.add_publisher(routing_key, ptype=ptype, exchange=exchange_name)
        publisher = self.get_publisher(routing_key)
        publisher.connect(conn)
        props = self.publish_props.get(routing_key)
        while not self.stop_event.is_set():
            data = func(*args, **kwargs) # get status data
            publisher.publish_json(data, routing_key=routing_key,
                                   properties=props)
            # print(data)
            time.sleep(interval)

    def publish_status(self, interval: float, routing_key: str):
        """A method decorator for publishing status messages periodically.

        This method is automatically threaded. The function it wraps must
        return a JSON-serializable object. That return object will then be
        sent with RabbitMQ to a subscriber listening to the given routing
        key. This method calls the private method ``_publish_status``, which
        is also available for more niche use cases.

        Parameters
        ----------
        interval : float
            The number of seconds to wait between each message.
        routing_key : str
            The routing key to use when publishing the message.
        """
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            thread = threading.Thread(
                target=self._publish_status,
                args=(wrapper, interval, routing_key),
            )
            self.threads.append(thread)
            return wrapper
        return decorator

    def _subscribe_status(self, callback:Callable[[pika.spec.Basic.Deliver,
                                                   pika.spec.BasicProperties,
                                                   bytes], Any],
                          queue: str, routing_keys: List[str]) -> None:
        """Subscribe to status messages on a set of routing keys.

        This method is not automatically threaded, but is thread safe. It
        takes a callback method that must take the arguments ``method``,
        ``properties``, and ``body``. See Pika/RabbitMQ documentation for
        specifics about callback functions and how these arguments work.
        See Rmqtools documentation for quick examples of how this works.
        Calls the private method ``_subscribe_status``, which is also
        available to use for more niche cases.

        Parameters
        ----------
        callback : (Deliver, BasicProperties, bytes) -> Any
            The callback method that handles the received message. Must take
            a ``method`` argument of type pika.spec.Basic.Deliver, a
            ``properties`` argument of type pika.spec.BasicProperties, and a
            ``body`` argument of type bytes for the body of the message.
        queue : str
            The name of the queue to use for subscribing.
        routing_keys : List[str]
            A list of routing keys to bind the queue to.
        """
        exchange = self.exchanges.get('status', ('', ExchangeType.topic))
        exchange_name = exchange[0]
        etype = exchange[1]
        self.add_subscriber(queue, queue, exchange_name, etype, routing_keys)
        subscriber = self.get_subscriber(queue)
        conn = self._get_connection()
        subscriber.connect(conn)
        subscriber.subscribe()

        threads = []
        for args in subscriber.channel.consume(
            subscriber.queue_name, auto_ack=True, inactivity_timeout=5):
            if all(args):
                thread = threading.Thread(
                    target=callback,
                    args=(subscriber.channel, *args),
                )
                thread.start()
                threads.append(thread)
                # callback(subscriber.channel, *args)
            if len(threads) >= 1000:
                for thread in threads:
                    thread.join()
                threads = []
            if self.stop_event.is_set():
                break
        for thread in threads:
            thread.join()

    def subscribe_status(self, queue: str, routing_keys: List[str]):
        """A method decorator for subscribing to a set of routing keys.

        This method is automatically threaded. The function it wraps must
        be a callback method that can take the arguments ``method``,
        ``properties``, and ``body``. See Pika/RabbitMQ documentation for
        specifics about callback functions and how these arguments work.
        See Rmqtools documentation for quick examples of how this works.
        Calls the private method ``_subscribe_status``, which is also
        available to use for more niche cases.

        Parameters
        ----------
        queue : str
            The name of the queue to use for subscribing.
        routing_keys : List[str]
            A list of routing keys to bind the queue to.
        """
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            thread = threading.Thread(
                target=self._subscribe_status,
                args=(wrapper, queue, routing_keys),
            )
            self.threads.append(thread)
            return wrapper
        return decorator

    def _handle_command(self, worker:Callable[[Any], ResponseObject],
                        queue:str) -> None:
        """Handle a command sent by an RPC client.

        Creates an RPC server with the worker function as the request handler.
        This method is not automatically threaded, but it is threadsafe using
        the ``stop_event`` defined on the current RmqConnection object.

        Parameters
        ----------
        worker : (Any) -> ResponseObject
            The request handler that takes the positional and keyword arguments
            given by the client's command and processes them. It then needs
            to return a ResponseObject with positional and keyword arguments
            corresponding to the client's response handler.
        queue : str
            The name of the queue to use for handling these commands. This
            name will be the routing key used by the command sender to route
            the command to the correct place.
        """
        exchange, _ = self.exchanges.get('command')
        server = RpcServer(exchange, queue)
        conn = self._get_connection()
        server.connect(conn)
        server.serve_threadsafe(worker, self.stop_event)

    def handle_command(self, queue:str):
        """A method decorator to set the response handler for a command sent
        from an RPC client.

        Creates an RPC server to respond to commands from an RPC client. This
        method is automatically threaded. The function it wraps can take any
        positional and keyword arguments it wants, but those arguments must
        be passed by the client that sends the command. The wrapped function
        must return a ResponseObject with positional and keyword arguments
        matching the response handler of the client. Calls the private method
        ``_handle_command``, which is also available for niche cases.

        Parameters
        ----------
        queue : str
            The name of the queue to use for handling these commands. This
            name will be the routing key used by the command sender to route
            the command to the correct place.
        """
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            thread = threading.Thread(
                target=self._handle_command,
                args=(wrapper, queue),
            )
            self.threads.append(thread)
            return wrapper
        return decorator

    def handle_response(self, command_id:str):
        """A method decorator to set the response handler of an RPC client.

        This method is not threaded, but it will not cause any IO blocking.
        All it does is update the ``response_handlers`` attribute with the
        wrapped function. The wrapped function can have any positional or
        keyword arguments, but those arguments must be matched by the return
        of the associated worker function in the associated RPC server. The
        wrapped function does not need to return any values.

        Parameters
        ----------
        command_id : str
            The identifier of the command this response handler is associated
            with.
        """
        def decorator(func:Callable[[Any], Any]):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            self.response_handlers.update({command_id: func})
            return wrapper
        return decorator

    def handle_timeout(self, command_id:str):
        """A method decorator to set the timeout handler of an RPC client.

        This method is not threaded, but it will not cause any IO blocking.
        All it does is update the ``timeout_handlers`` attribute with the
        wrapped function. The wrapped function should have only one argument
        for the timeout length and should not return anything.

        Parameters
        ----------
        command_id : str
            The identifier of the command this response handler is associated
            with.
        """
        def decorator(func:Callable[[Any], Any]):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            self.timeout_handlers.update({command_id: func})
            return wrapper
        return decorator

    def _send_command(self, func:Callable[[Any], ResponseObject],
                      command_id:str, queue:str, *args, timeout:int=None,
                      **kwargs) -> None:
        """Sends a command to an associated RPC server.

        This method is not automatically threaded, but it is threadsafe. It
        creates an RPC client to send commands to the associated RPC server
        and handle the response. This function should be paired with an
        associated ``handle_response`` decorator to define the response
        handler. If there is no associated handler, the response from the
        server will hit the default handler, which does nothing.

        Parameters
        ----------
        func : (Any) -> ResponseObject
            The function that generates the command data. It can take
            positional and keyword arguments that are given by the ``args``
            and ``kwargs`` parameters. It must return a ResponseObject with
            positional and keyword arguments corresponding to the arguments
            needed by the server's request handler.
        command_id : str
            The identifier of the command, used to map the ``_send_command``
            call with the associated ``handle_response`` decorator.
        queue : str
            The queue name of the RPC server where the command is being sent.
        timeout : int, optional
            How long to wait for a response before timing out. Default behavior
            is no timeout.
        """
        def default_handler(*a, **kw):
            pass
        command = func(*args, **kwargs)
        response_handler = self.response_handlers.get(
            command_id, default_handler)
        timeout_handler = self.timeout_handlers.get(
            command_id, default_handler)
        exchange, _ = self.exchanges.get('command')
        client = RpcClient(exchange)
        conn = self._get_connection()
        client.connect(conn)
        response = client.call_threadsafe(queue, self.stop_event, command,
                                          timeout=timeout)
        if not response:
            return timeout_handler(timeout)
        args = response.args
        kwargs = response.kwargs
        return response_handler(*args, **kwargs)

    def send_command(self, command_id:str, queue:str, timeout:int=None):
        """A method decorator to send a command to an RPC server.

        This method is automatically threaded. It creates an RPC client to
        send commands to the associated RPC server and handle the response.
        This decorator should be paired with a ``handle_response`` decorator
        to define the response handler for the given command. If there is no
        associated response handler, the response from the server will hit
        the default handler, which does nothing. The wrapped function must
        return a ResponseObject with the positional and keyword arguments
        needed by the RPC server's request handler. The wrapped function
        cannot take any arguments.

        Parameters
        ----------
        command_id : str
            The identifier of the command, used to map the ``send_command``
            decorator with the associated ``handle_response`` decorator.
        queue : str
            The queue name of the RPC server where the command is being sent.
        timeout : int, optional
            How long to wait for a response before timing out. Default behavior
            is no timeout.
        """
        def decorator(func:Callable[[], ResponseObject]):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            thread = threading.Thread(
                target=self._send_command,
                args=(wrapper, command_id, queue),
                kwargs={'timeout': timeout},
            )
            self.threads.append(thread)
            return wrapper
        return decorator
