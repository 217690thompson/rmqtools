import functools
import json
import threading
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable, Union

import pika
from pika.channel import Channel
from pika.exchange_type import ExchangeType
from pika.spec import Basic
from rmqtools import Connection, Publisher, ResponseObject


class RpcServer():
    """Creates a RPC server on the RabbitMQ server for command-response and
    distributed worker systems.

    Parameters
    ----------
    exchange : str
        The name of the exchange this RPC server uses.
    queue : str
        The name of the queue this RPC server uses.

    Attributes
    ----------
    etype : pika.ExchangeType.direct
        The exchange type. This is always ExchangeType.direct because RPC
        systems use direct exchanges.
    exchange_name : str
        The name of the exchange this RPC server uses.
    queue_name : str
        The name of the queue this RPC server uses.
    Connection : rmqtools.Connection
        The Connection object linked to this RPC server, set by the ``connect``
        method. Use a unique connection for each thread.
    channel : pika.BlockingChannel
        The channel this RPC server uses for communication with RabbitMQ.
    exchange : rmqtools.connection.Exchange
        The Exchange object to keep the RPC server's exchange data consistent
        with the Connection object.
    """

    def __init__(self, exchange:str, queue:str):
        """Creates a RPC server on the RabbitMQ server for command-response and
        distributed worker systems.

        Parameters
        ----------
        exchange : str
            The name of the exchange this RPC server uses.
        queue : str
            The name of the queue this RPC server uses.
        """
        self.etype = ExchangeType.direct
        self.exchange_name = exchange
        self.queue_name = queue

    def connect(self, conn:Connection):
        """Connect the RPC server to a Connection object, giving it access to
        the RabbitMQ server. Also declares the exchange and queue defined in
        instance initialization, as well as binding the queue to the exchange
        with the routing key set to the queue's name.

        Parameters
        ----------
        conn : Connection
            The ``rmqtools.Connection`` object to use to connect to RabbitMQ
            and link to this RPC server. Use a unique Connection per thread.
        """
        self.Connection = conn
        self.channel = self.Connection.channel
        self.Connection.exchange_declare(self.exchange_name, self.etype)
        self.exchange = self.Connection.exchanges.get(self.exchange_name)
        self.channel.queue_declare(queue=self.queue_name)
        self.channel.queue_bind(self.queue_name, self.exchange_name,
                                self.queue_name)

    def on_request(self, worker:Callable[[Any], ResponseObject], ch:Channel,
                   method:Basic.Deliver, props:pika.BasicProperties,
                   body:bytes) -> None:
        """Called when the client requests data from the server.

        It parses the ResponseObject sent by the client into positional and
        keyword arguments to be passed to the worker function. The worker
        function responds with a ResponseObject of its own that is then
        serialized and published to the client's reply queue.

        Parameters
        ----------
        worker : (Any) -> ResponseObject
            The worker function that the request will be passed to. Should
            be of the form ``def worker(...)`` where the arguments and keyword
            arguments passed by the RPC client will fill out the parameters
            of the worker function. The worker function should return a
            rmqtools.ResponseObject with the arguments and keyword arguments
            that will be passed to the client's response handler.
        ch : Channel
            Filled in automatically by ``basic_consume``
        method : pika.spec.Basic.Deliver
            Filled in automatically by ``basic_consume``
        props : pika.BasicProperties
            Filled in automatically by ``basic_consume``
        body : bytes
            Filled in automatically by ``basic_consume``
        """
        try:
            data = json.loads(body)
        except:
            data = {}
        if not isinstance(data, dict):
            data = {}
        args = data.get('args', [])
        kwargs = data.get('kwargs', {})

        try:
            response = worker(*args, **kwargs)
        except TypeError:
            raise ValueError("Incorrect arguments supplied to worker "
                             "function!")

        self.channel.basic_publish(
            exchange=self.exchange_name,
            routing_key=props.reply_to,
            properties=pika.BasicProperties(
                correlation_id=props.correlation_id),
            body=json.dumps(response.__dict__),
        )
        self.channel.basic_ack(delivery_tag=method.delivery_tag)

    def serve(self, worker:Callable[[Any], ResponseObject]) -> None:
        """Initialize the RPC server to handle requests.

        Starts by defining with ``basic_qos`` that it handles one message at a
        time. Then starts consuming using the passed worker function as the
        callback for ``basic_consume``. This method will consume indefinitely,
        so it is NOT thread safe.

        Parameters
        ----------
        worker : (Any) -> ResponseObject
            The worker function that the request will be passed to. Should
            be of the form ``def worker(...)`` where the arguments and keyword
            arguments passed by the RPC client will fill out the parameters
            of the worker function. The worker function should return a
            rmqtools.ResponseObject with the arguments and keyword arguments
            that will be passed to the client's response handler.
        """
        self.channel.basic_qos(prefetch_count=1)
        callback = functools.partial(self.on_request, worker)
        self.channel.basic_consume(queue=self.queue_name,
                                   on_message_callback=callback)
        self.channel.start_consuming()

    def serve_threadsafe(self, worker:Callable[[Any], ResponseObject],
                         stop_event:threading.Event) -> None:
        """Similar to the serve method but is safe for use with threading.

        Rather than consuming indefinitely with the ``start_consuming`` method,
        uses the ``consume`` method to handle one message at a time, blocking
        only for 5 seconds at a time. The 5 second timeout allows for the
        stop_event to propagate so it can stop the RPC server.

        Parameters
        ----------
        worker : (Any) -> ResponseObject
            The worker function that the request will be passed to. Should
            be of the form ``def worker(...)`` where the arguments and keyword
            arguments passed by the RPC client will fill out the parameters
            of the worker function. The worker function should return a
            rmqtools.ResponseObject with the arguments and keyword arguments
            that will be passed to the client's response handler.
        stop_event : threading.Event
            The Event used to trigger the shutdown of the RPC server's thread.
        """
        self.channel.basic_qos(prefetch_count=1)

        for method, props, body in self.channel.consume(
            self.queue_name, inactivity_timeout=5):
            if all([method, props, body]):
                self.on_request(worker, self.channel, method, props, body)
            if stop_event.is_set():
                break


class RpcClient():
    """Creates a RPC client on the RabbitMQ server for command-response and
    distributed workload applications.

    Parameters
    ----------
    exchange : str
        The name of the exchange the RPC client and server will operate on.

    Attributes
    ----------
    etype : pika.ExchangeType.direct
        This is always ExchangeType.direct because RPC systems use direct
        exchanges.
    exchange_name : str
        The name of the exchange used by the RPC client and server.
    corr_id : str | None
        The correlation id used to match a request to a reply from the server.
        This is auto-generted with ``uuid.uuid4()`` when the ``call`` method is
        run.
    response : ResponseObject | None
        The ResponseObject returned by the RPC server that is routed to the
        client's request handler. The response attribute is set by the
        ``on_response`` method, which is set as the callback function in
        ``basic_consume``.
    Connection : rmqtools.Connection
        The Connection object linked to this RPC client, set by the ``connect``
        method. Use a unique connection for each thread.
    channel : pika.BlockingChannel
        The channel this RPC client uses for communication with RabbitMQ.
    publisher : rmqtools.Publisher
        The Publisher object that the client uses to send messages to the
        RabbitMQ server.
    callback_queue : str
        The auto-generated identifier of the response queue given to the RPC
        server to reply to.
    """

    def __init__(self, exchange:str):
        """Creates a RPC client on the RabbitMQ server for command-response and
        distributed workload applications.

        Parameters
        ----------
        exchange : str
            The name of the exchange the RPC client and server will operate on.
        """
        self.etype = ExchangeType.direct
        self.exchange_name = exchange
        self.corr_id = None

        self.response: Union[ResponseObject, None]
        self.response = None

    def connect(self, conn:Connection):
        """Connect the RPC client to a Connection object, giving it access to
        the RabbitMQ server. It also creates the Publisher object from the
        exchange_name given in initialization. It then creates the callback
        queue and binds it to the exchange with a routing key that is the
        queue's name. Sets up the ``basic_consume`` method on the callback
        queue with the callback method of ``on_response`` to set the response
        object.

        Parameters
        ----------
        conn : Connection
            The ``rmqtools.Connection`` object to use to connect to RabbitMQ
            and link to this RPC server. Use a unique Connection per thread.
        """
        self.Connection = conn
        self.channel = self.Connection.channel
        self.publisher = Publisher('direct', self.exchange_name)
        self.publisher.connect(conn)

        res = self.channel.queue_declare(queue='', exclusive=True)
        self.callback_queue = res.method.queue
        self.channel.queue_bind(self.callback_queue, self.exchange_name,
                                self.callback_queue)

        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self.on_response,
            auto_ack=True,
        )

    def on_response(self, ch:Channel, method:Basic.Deliver,
                    props:pika.BasicProperties, body:bytes):
        """The callback method that handles the response from the RPC server.
        All it does is set the ``response`` attribute to be used by ``call`` and
        ``call_threadsafe`` methods.

        Parameters
        ----------
        ch : Channel
            Filled in automatically by ``basic_consume``
        method : pika.spec.Basic.Deliver
            Filled in automatically by ``basic_consume``
        props : pika.BasicProperties
            Filled in automatically by ``basic_consume``
        body : bytes
            Filled in automatically by ``basic_consume``
        """
        if self.corr_id == props.correlation_id:
            self.response = ResponseObject(**json.loads(body))

    def _get_publish_props(self):
        props = pika.BasicProperties(
            reply_to=self.callback_queue,
            correlation_id=self.corr_id,
        )
        return props

    def call(self, queue:str, command:ResponseObject) -> ResponseObject:
        """Send a command to a RPC server and get the response.

        This method uses Pika's ``process_data_events`` method with no time limit
        to get the server's response, so it is NOT thread safe.

        Parameters
        ----------
        queue : str
            The name of the queue to call (the name of the RPC server's queue).
        command : ResponseObject
            The command/request to send to the RPC server, in the
            ResponseObject format. The args and kwargs in the ResponseObject
            will be passed into the RPC server's worker function.

        Returns
        -------
        ResponseObject
            Returns the response of the RPC server's worker function, formatted
            with the ResponseObject format, so the args and kwargs can be
            passed into a custom response handler.
        """
        self.response = None
        self.corr_id = str(uuid.uuid4())

        body = command.__dict__
        props = self._get_publish_props()
        self.publisher.publish_json(body, routing_key=queue,
                                    properties=props)
        self.Connection.connection.process_data_events(time_limit=None)
        return self.response

    def call_threadsafe(self, queue:str, stop_event:threading.Event,
                        command:ResponseObject, timeout=None) -> ResponseObject:
        """Similar to the ``call`` method but requests the server in a thread-
        safe manner.

        This method uses Pika's ``process_data_events`` with a timeout of one
        second to allow for checking the stop event to make sure the thread
        closes when it is supposed to.

        Parameters
        ----------
        queue : str
            The name of the queue to call (the name of the RPC server's queue).
        stop_event : threading.Event
            The Event object used to stop the thread this is running on.
        command : ResponseObject
            The command/request to send to the RPC server, in the
            ResponseObject format. The args and kwargs in the ResponseObject
            will be passed into the RPC server's worker function.

        Returns
        -------
        ResponseObject
            Returns the response of the RPC server's worker function, formatted
            with the ResponseObject format, so the args and kwargs can be
            passed into a custom response handler.
        """
        self.response = None
        self.corr_id = str(uuid.uuid4())

        body = command.__dict__
        props = self._get_publish_props()
        self.publisher.publish_json(body, routing_key=queue,
                                    properties=props)
        timeout_time = datetime.max
        if timeout:
            timeout_time = datetime.now() + timedelta(seconds=timeout)
        while not stop_event.is_set():
            self.Connection.connection.process_data_events(time_limit=1)
            if self.response is not None:
                break
            if datetime.now() > timeout_time:
                # command timed out
                self.Connection.channel.queue_purge(queue)
                self.Connection.connection.close()
                self.response = None
                break
        return self.response
