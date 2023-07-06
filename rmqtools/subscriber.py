"""Tools for a subscriber connection"""

from typing import Any, Dict, List

from pika.exchange_type import ExchangeType
from rmqtools import Connection


class Subscriber():
    """Creates a subscriber object that has methods to easily subscribe to
    messages on a specific RabbitMQ routing key. This class is used by the
    higher-level RmqConnection class.

    Parameters
    ----------
    queue : str, optional
        The name of the queue the subscriber will use, defaults to ''. If left
        blank, the queue will be given an automatically generated name. If
        using a quorum queue, a queue name must be given (it cannot be left
        blank).
    exchange : str, optional
        The name of the exchange the subscriber will use, defaults to ''. If
        left blank, the subscriber will use the default exchange. If an
        exchange name is given, the etype parameter must also be given.
    etype : pika.ExchangeType, optional
        The type of the exchange, given as a pika.ExchangeType object, defaults
        to None. If exchange is not left blank, this field is required.
    routing_keys : List[str], optional
        A list of routing keys for the subscriber to listen on, defaults to [].
        Routing keys can contain wildcards for subscribers - see RabbitMQ
        documentation about routing keys
        (https://www.rabbitmq.com/tutorials/tutorial-four-python.html).
    quorum : bool, optional
        Makes the subscriber use quorum queues, defaults to True. Quorum queues
        are useful for clustered RabbitMQ networks. For more information about
        clustering and quorum queues, see the RabbitMQ documentation on these
        topics (https://www.rabbitmq.com/clustering.html and
        https://www.rabbitmq.com/quorum-queues.html). For a visualization of
        the underlying Raft algorithm that makes quorum queues work, see
        http://thesecretlivesofdata.com/raft/.
    queue_arguments : Dict[str, Any], optional
        Additional keyword arguments to pass to the pika queue_bind function,
        defaults to {}.

    Attributes
    ----------
    queue_name : str
        The name of the queue the subscriber is using.
    exchange_name : str
        The name of the exchange the subscriber is using.
    routing_keys : List[str]
        A list of routing keys the subscriber is listening to.
    quorum : bool
        Whether the subscriber is using quorum queues.
    queue_arguments : Dict[str, Any]
        Additional keyword arguments that were passed to the pika queue_bind
        function.
    Connection : rmqtools.Connection
        The Connection object linked to this subscriber, set by the ``connect``
        method. Use a unique connection for each thread.
    channel : pika.BlockingChannel
        The channel the subscriber uses for communication with RabbitMQ.
    exchange : rmqtools.connection.Exchange
        The Exchange object to keep the subscriber's exchange data consistent
        with the Connection object.
    """

    def __init__(self, queue='', exchange='', etype:ExchangeType=None,
                 routing_keys:List[str]=[], quorum=True,
                 queue_arguments:Dict[str, Any]={}) -> None:
        """Creates a subscriber object that has methods to easily subscribe to
        messages on a specific RabbitMQ routing key. This class is used by the
        higher-level RmqConnection class.

        Parameters
        ----------
        queue : str, optional
            The name of the queue the subscriber will use, defaults to ''. If left
            blank, the queue will be given an automatically generated name. If
            using a quorum queue, a queue name must be given (it cannot be left
            blank).
        exchange : str, optional
            The name of the exchange the subscriber will use, defaults to ''. If
            left blank, the subscriber will use the default exchange. If an
            exchange name is given, the etype parameter must also be given.
        etype : pika.ExchangeType, optional
            The type of the exchange, given as a pika.ExchangeType object, defaults
            to None. If exchange is not left blank, this field is required.
        routing_keys : List[str], optional
            A list of routing keys for the subscriber to listen on, defaults to [].
            Routing keys can contain wildcards for subscribers - see RabbitMQ
            documentation about routing keys
            (https://www.rabbitmq.com/tutorials/tutorial-four-python.html).
        quorum : bool, optional
            Makes the subscriber use quorum queues, defaults to True. Quorum queues
            are useful for clustered RabbitMQ networks. For more information about
            clustering and quorum queues, see the RabbitMQ documentation on these
            topics (https://www.rabbitmq.com/clustering.html and
            https://www.rabbitmq.com/quorum-queues.html). For a visualization of
            the underlying Raft algorithm that makes quorum queues work, see
            http://thesecretlivesofdata.com/raft/.
        queue_arguments : Dict[str, Any], optional
            Additional keyword arguments to pass to the pika queue_bind function,
            defaults to {}.
        """
        # validate data
        if quorum and not queue:
            raise ValueError("Quorum queues must be named explicitly!")
        if exchange and not etype:
            raise ValueError("If specifying an exchange, you must provide an "
                             "exchange type!")
        if not exchange and routing_keys:
            raise ValueError("Routing keys cannot be used on the defualt "
                             "exchange!")

        self.queue_name = queue
        self.exchange_name = exchange
        self.etype = etype
        self.routing_keys = routing_keys
        self.quorum = quorum
        self.queue_arguments = queue_arguments

    def connect(self, conn:Connection) -> None:
        """Connect the subscriber to a Connection object, giving it access to
        the RabbitMQ server. Also declares the exchange defined in instance
        initialization.

        Parameters
        ----------
        conn : Connection
            The ``rmqtools.Connection`` object to use to connect to RabbitMQ
            and link to this subscriber. Use a unique Connection per thread.
        """
        self.Connection = conn
        self.channel = self.Connection.channel
        if self.exchange_name and self.etype:
            self.Connection.exchange_declare(self.exchange_name, self.etype)
            self.exchange = self.Connection.exchanges.get(self.exchange_name)

    def _get_queue_declare_args(self, **kwargs) -> dict:
        args = dict(self.queue_arguments)
        args.update(queue=self.queue_name)
        args.update(**kwargs)
        if self.quorum:
            args.update(arguments={"x-queue-type": "quorum"})
        return args

    def _get_queue_bind_args(self, routing_key, **kwargs) -> dict:
        args = {
            'exchange': self.exchange_name,
            'queue': self.queue_name,
            'routing_key': routing_key,
        }
        args.update(**kwargs)
        return args

    def subscribe(self) -> None:
        """Links the subscriber to the queue defined in the initialization.
        Also binds that queue to the routing keys given in the initialization.
        This must be run after the ``connect`` method because it requires the
        channel attribute to be set.
        """
        self.channel.queue_declare(**self._get_queue_declare_args())
        for key in self.routing_keys:
            self.channel.queue_bind(**self._get_queue_bind_args(key))
