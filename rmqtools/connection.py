"""Core connection objects"""

from dataclasses import dataclass, field
from typing import Any, List, Union

import pika
from pika.channel import Channel
from pika.exchange_type import ExchangeType


@dataclass
class ResponseObject:
    """The dataclass used by RPC calls to pass information to callback
    functions and response handlers. All RPC request methods and worker
    functions in RPC calls must return a ResponseObject.

    Parameters
    ----------
    args : list, optional
        A list of positional arguments to pass to the response/request handler,
        defaults to [].
    kwargs : dict, optional
        A dictionary of keyword arguments to pass to the response/request
        handler, defaults to {}.
    """
    args: list = field(default_factory=list)
    kwargs: dict = field(default_factory=dict)


class Exchange():
    """Provides a wrapper for interacting with RabbitMQ exchanges.
    Additionally, stores data about an exchange to be used later by other
    parts of the code.
    """

    def __init__(self, channel:Channel, name:str, exchange_type:ExchangeType,
                 passive=False, durable=False, auto_delete=False,
                 internal=False, autodeclare=True) -> None:
        """A wrapper for interacting with RabbitMQ exchanges

        Parameters
        ----------
        channel : Channel
            The pika Channel object to write the exchange on
        name : str
            The name of the exchange
        exchange_type : ExchangeType
            The pika ExchangeType object defining the type of exchange.
            Valid options are direct, fanout, topic, and headers.
        passive : bool, optional
            If set to True, checks if exchange exists rather than declaring it,
            by default False
        durable : bool, optional
            If set to True, the exchange will survive a reboot of RabbitMQ, by
            default False
        auto_delete : bool, optional
            Remove the exchange if no more queues are attached to it, by
            default False
        internal : bool, optional
            Can only be published to by other exchanges, by default False
        autodeclare : bool, optional
            Declare the exchange on object initialization, by default True
        """
        self.channel = channel
        self.name = name
        self.exchange_type = exchange_type.name
        self.passive = passive
        self.durable = durable
        self.auto_delete = auto_delete
        self.internal = internal
        if autodeclare:
            self._declare()

    def _declare(self) -> None:
        """Declares an exchange with the instantiation variables
        """
        self.declare(self.channel, self.name, self.exchange_type,
                     passive=self.passive, durable=self.durable,
                     auto_delete=self.auto_delete, internal=self.internal)

    def _delete(self, **kwargs) -> None:
        """Deletes an exchange with the instantiation variables

        Parameters
        ----------
        kwargs : optional
            Optional values to pass with the exchange_delete call:
            if_unused : bool
                Only delete if the exchange is unused
            callback : callable
                Method to call after deleting the exchange
        """
        self.delete(self.channel, self.name, **kwargs)

    @classmethod
    def declare(cls, channel:Channel, name:str, exchange_type:ExchangeType,
                **kwargs) -> None:
        """Declares an exchange

        Parameters
        ----------
        channel : Channel
            The channel to declare the exchange on
        name : str
            The name of the exchange
        exchange_type : ExchangeType
            The type of the exchange given as a pika Exchange Type object.
            Allowed values are direct, fanout, headers, and topic.
        kwargs : optional
            passive : bool
                Checks if exchange exists rather than declaring it,
                by default False
            durable : bool
                The exchange will survive a reboot of RabbitMQ, by
                default False
            auto_delete : bool
                Remove the exchange if no more queues are attached to it, by
                default False
            internal : bool
                Can only be published to by other exchanges, by default False
        """
        channel.exchange_declare(name, exchange_type, **kwargs)

    @classmethod
    def delete(cls, channel:Channel, name:str, **kwargs):
        """Deletes the given exchange

        Parameters
        ----------
        channel : Channel
            The channel to delete the exchange from
        name : str
            The name of the exchange
        kwargs : optional
            if_unused : bool
                Only delete if the exchange is unused
            callback : callable
                Method to call after deleting the exchange
        """
        channel.exchange_delete(name, **kwargs)


class Exchanges():
    """Encapsulates a list of Exchange objects. Additionally, provides
    methods for interacting with the list of exchanges, such as implementing
    dictionary-style ``.get()`` and ``.remove()`` methods, as well as list-style
    ``+=`` and ``.append()`` methods. Allows for the storage of information
    about all the exchanges involved in a RabbitMQ operation.
    """

    def __init__(self, exchanges:List[Exchange]=[]):
        """Encapsulates a list of exchanges

        Parameters
        ----------
        exchanges : List[Exchange], optional
            A list of Exchange objects to start (more can be added),
            by default []
        """
        self.exchanges = exchanges

    def __getitem__(self, index:str) -> Exchange:
        """Overrides the __getitem__ method to allow for Exchanges[key]

        Parameters
        ----------
        index : str
            The name attribute of the Exchange object to be pulled

        Returns
        -------
        Exchange
            Returns the exchange with the name corresponding to index

        Raises
        ------
        KeyError
            The indexed exchange could not be found
        """
        for exchange in self.exchanges:
            if exchange.name == index:
                return exchange
        raise KeyError(f"Exchange '{index}' not found in list of exchanges!")

    def get(self, index:str, default=None) -> Union[Exchange, Any]:
        """A dictionary-style ``.get(index, [default])`` for Exchanges

        Parameters
        ----------
        index : str
            The name attribute of an Exchange
        default : Any, optional
            A default value to pass if index not found, by default None

        Returns
        -------
        Exchange | Any
            Exchange such that ``Exchange.name == index``, else returns default
        """
        try:
            return self[index]
        except ValueError as err:
            return default

    def append(self, exchange:Exchange) -> None:
        """Adds an exchange to the list of exchanges

        Parameters
        ----------
        exchange : Exchange
            The exchange object to add

        Raises
        ------
        ValueError
            Exchange names must be unique
        """
        if exchange.name in [e.name for e in self.exchanges]:
            raise ValueError(f"Exchange '{exchange.name}' already exists in "
                             "list of exchanges!")
        self.exchanges.append(exchange)

    def __iadd__(self, obj:Union["Exchanges", Exchange, List[Exchange]]) -> "Exchanges":
        """Implements the ``+=`` operator for Exchanges

        Parameters
        ----------
        obj : Exchanges | Exchange | List[Exchange]
            A valid object to append to the Exchanges object

        Returns
        -------
        Exchanges
            Returns itself with obj added

        Raises
        ------
        TypeError
            If obj isn't the valid type
        """
        if isinstance(obj, Exchanges):
            for exchange in obj.exchanges:
                self.append(exchange)
        elif isinstance(obj, list)\
            and all([isinstance(l, Exchange) for l in obj]):
            for exchange in obj:
                self.append(exchange)
        elif isinstance(obj, Exchange):
            self.append(obj)
        else:
            raise TypeError(f"Cannot merge '{type(obj)}' into Exchanges")
        return self

    def remove(self, name:str, if_unused=False) -> None:
        """Remove an exchange from the list of exchanges

        Parameters
        ----------
        name : str
            The name of the exchange to remove
        if_unused : bool
            If True, only delete the exchange if it is unused, by default False
        """
        exchange = self[name]
        exchange._delete(if_unused=if_unused)
        self.exchanges.remove(name)


class Queue():
    """Provides a wrapper for interacting with RabbitMQ queues. Additionally,
    stores data about a queue for later use by the code."""

    def __init__(self, channel:Channel, name='', binding_keys=[],
                 binding_kwargs={}, autodeclare=True) -> None:
        """Creates a Queue object, optionally declares the queue, and
        optionally binds the queue to routing keys

        Parameters
        ----------
        channel : Channel
            The channel to declare the queue on
        name : str, optional
            The name of the queue, leave blank for auto-naming, by default ''
        binding_keys : list, optional
            A list of routing keys to bind the queue to, by default []
        binding_kwargs : dict, optional
            Optional parameters to pass into queue_bind, by default {}
        autodeclare : bool, optional
            Declare the queue automatically, by default True
        """
        self.channel = channel
        self.name = name
        self.binding_keys = binding_keys
        self.binding_kwargs = binding_kwargs
        if autodeclare:
            self._declare_and_bind()

    def _declare(self) -> None:
        """Declare the queue with the initialization values
        """
        self.declare(self.channel, self.name)

    def _declare_and_bind(self) -> None:
        """Declare the queue with initialization values and bind to the
        routing keys given in initialization.
        """
        self._declare()
        for key in self.binding_keys:
            self._bind(key)

    def _bind(self, routing_key:str, **kwargs) -> None:
        """Bind the queue to a routing key using the initialization values

        Parameters
        ----------
        routing_key : str
            A RabbitMQ routing key (e.g. ``device.*.status``)
        """
        binding_kwargs = self.binding_kwargs
        binding_kwargs.update(kwargs)
        self.bind(self.channel, self.name, routing_key, **binding_kwargs)

    def _delete(self, **kwargs) -> None:
        """Delete the queue using the initialization values
        """
        self.delete(self.channel, self.name, **kwargs)

    @classmethod
    def declare(cls, channel:Channel, name:str, **kwargs) -> None:
        """Declare a queue on ``channel`` with name ``name``

        Parameters
        ----------
        channel : Channel
            The channel to declare the queue on
        name : str
            The name of the queue
        """
        channel.queue_declare(name, **kwargs)

    @classmethod
    def bind(cls, channel:Channel, name:str, routing_key:str, exchange='',
             **kwargs) -> None:
        """Bind a queue to a routing key

        Parameters
        ----------
        channel : Channel
            The channel to use for binding
        name : str
            The name of the queue
        routing_key : str
            A RabbitMQ routing key (e.g. ``device.*.status``)
        exchange : str, optional
            The exchange to bind the queue on, leave blank to bind to the
            default queue, by default ''
        """
        channel.queue_bind(queue=name, exchange=exchange,
                           routing_key=routing_key, **kwargs)

    @classmethod
    def delete(cls, channel:Channel, name:str, **kwargs) -> None:
        """Delete a queue

        Parameters
        ----------
        channel : Channel
            The channel to use for deleting
        name : str
            The name of the queue
        """
        channel.queue_delete(name, **kwargs)


class Queues():
    """Encapsulates a list of Queue objects. Additionally, provides
    methods for interacting with the list of queues, such as implementing
    dictionary-style ``.get()`` and ``.remove()`` methods, as well as list-style
    ``+=`` and ``.append()`` methods. Allows for the storage of information
    about all the queues involved in a RabbitMQ operation."""

    def __init__(self, queues:List[Queue]=[]) -> None:
        """Creates the Queues object

        Parameters
        ----------
        queues : List[Queue], optional
            An initial list of queues (more can be added), by default []
        """
        self.queues = queues

    def __getitem__(self, index:str) -> Queue:
        """Implements dictionary-like indexing of the Queues object (e.g.
        Queues[index])

        Parameters
        ----------
        index : str
            The name of the queue to get from the Queues object

        Returns
        -------
        Queue
            Returns the queue corresponding to index

        Raises
        ------
        KeyError
            The index could not be found
        """
        for queue in self.queues:
            if queue.name == index:
                return queue
        raise KeyError(f"Queue '{index}' not found in list of queues!")

    def get(self, index:str, default=None) -> Union[Queue, Any]:
        """A dictionary-style ``.get(index, [default])`` for Queues

        Parameters
        ----------
        index : str
            The name attribute of a Queue
        default : Any, optional
            A default value to pass if index not found, by default None

        Returns
        -------
        Queue | Any
            Queue such that ``Queue.name == index``, else returns default
        """
        try:
            return self[index]
        except ValueError as err:
            return default

    def append(self, queue:Queue) -> None:
        """Adds a queue to the list of queues

        Parameters
        ----------
        queue : Queue
            The exchange object to add

        Raises
        ------
        ValueError
            Queue names must be unique
        """
        if queue.name in [q.name for q in self.queues]:
            raise ValueError(f"Queue '{queue.name}' already exists in "
                             "list of queues!")
        self.queues.append(queue)

    def __iadd__(self, obj:Union["Queues", Queue, List[Queue]]) -> "Queues":
        """Implements the ``+=`` operator for Queues

        Parameters
        ----------
        obj : Queues | Queue | List[Queue]
            A valid object to append to the Queues object

        Returns
        -------
        Queues
            Returns itself with obj added

        Raises
        ------
        TypeError
            If obj isn't the valid type
        """
        if isinstance(obj, Queues):
            for queue in obj.queues:
                self.append(queue)
        elif isinstance(obj, list)\
            and all([isinstance(l, Queue) for l in obj]):
            for queue in obj:
                self.append(queue)
        elif isinstance(obj, Queue):
            self.append(obj)
        else:
            raise TypeError(f"Cannot merge '{type(obj)}' into Queues")
        return self

    def remove(self, name:str) -> None:
        """Remove a queue from the list of queues

        Parameters
        ----------
        name : str
            The name of the queue to remove
        """
        queue = self[name]
        queue._delete()
        self.queues.remove(name)


class Connection():
    """The core class that implements communication with RabbitMQ through Pika.
    This class is used by most of the other classes in rmqtools as the base
    method of interacting with the RabbitMQ server.

    Parameters
    ----------
    username : str, optional
        The username to use for logging into the RabbitMQ server, by
        default 'guest'. It is not necessary, but recommended to create
        a user other than the default 'guest' to use for server
        authentication.
    password : str, optional
        The password to use for logging into the RabbitMQ server, by
        default 'guest'.
    host : str, optional
        The host of the RabbitMQ server, by default 'localhost'. This can
        either be an address (e.g. '192.168.0.1') or a host name (e.g.
        'rabbit-1'). Using a host name is prefered to using an address.
        Only host with 'localhost' if all connections are coming from the
        same machine as the RabbitMQ server.
    port : int, optional
        The port to connect over, by default 5672. This is almost always
        5672, unless there are multiple RabbitMQ servers running on the
        same host, which is discouraged.
    autoconnect : bool, optional
        Whether to connect to the RabbitMQ server and open a channel
        automatically, by default True.

    Attributes
    ----------
    username : str
        The username used to log into the server.
    password : str
        The password used to log into the server.
    host : str
        The name or address of the host server for this connection ('localhost'
        can be used single machine setups). Names (e.g. 'rabbit-1') are
        prefered to addresses (e.g. '192.168.0.1').
    port : int
        The port to connect to the server on (usually 5672).
    connection : pika.BlockingConnection | pika.BaseConnection | pika.SelectConnection
        The actual Pika connection object.
    channel : pika.channel.Channel | pika.BlockingChannel
        The Pika channel that RabbitMQ requests are sent on.
    exchanges : rmqtools.connection.Exchanges
        The object that contains all of the rmqtools.connection.Exchange
        objects associated with this connection. Each Exchange object contains
        information about exchanges created on the RabbitMQ server using this
        connection.
    queues : rmqtools.connection.Queues
        The object that contains all of the rmqtools.connection.Queue
        objects associated with this connection. Each Queue object contains
        information about a queue created on the RabbitMQ server using this
        connection.
    credentials : pika.PlainCredentials
        The credentials used to log into the RabbitMQ server. Uses username
        and password attributes.
    parameters : pika.ConnectionParameters
        The parameters used when connecting to the RabbitMQ server. Uses the
        credentials, host, and port attributes.
    """

    def __init__(self, username='guest', password='guest', host='localhost',
                 port=5672, autoconnect=True) -> None:
        """Connection initialization requires a username, password, host, and
        port, but has default values for all of these. If autoconnect is true,
        the Connection object will automatically connect to the RabbitMQ
        server. Otherwise, the user must call Connection.connect() and
        Connection.set_channel() after initializing the Connection object.

        Parameters
        ----------
        username : str, optional
            The username to use for logging into the RabbitMQ server, by
            default 'guest'. It is not necessary, but recommended to create
            a user other than the default 'guest' to use for server
            authentication.
        password : str, optional
            The password to use for logging into the RabbitMQ server, by
            default 'guest'.
        host : str, optional
            The host of the RabbitMQ server, by default 'localhost'. This can
            either be an address (e.g. '192.168.0.1') or a host name (e.g.
            'rabbit-1'). Using a host name is prefered to using an address.
            Only host with 'localhost' if all connections are coming from the
            same machine as the RabbitMQ server.
        port : int, optional
            The port to connect over, by default 5672. This is almost always
            5672, unless there are multiple RabbitMQ servers running on the
            same host, which is discouraged.
        autoconnect : bool, optional
            Whether to connect to the RabbitMQ server and open a channel
            automatically, by default True.
        """
        self.username = username
        self.password = password
        self.host = host
        self.port = port
        self.credentials = None
        self._set_credentials()
        self.parameters = None
        self._set_parameters()
        self.connection = None
        self.channel = None
        if autoconnect:
            self.connect()
            self.set_channel()
        self.exchanges = Exchanges()
        self.queues = Queues()

    def _set_credentials(self, username:str=None, password:str=None,
                         erase_on_connect=False) -> None:
        username = username if username else self.username
        password = password if password else self.password
        credentials = pika.PlainCredentials(
            username, password, erase_on_connect=erase_on_connect)
        self.credentials = credentials

    def _set_parameters(self, host:str=None, port:int=None,
                        credentials:pika.PlainCredentials=None,
                        **kwargs) -> None:
        host = host if host else self.host
        port = port if port else self.port
        credentials = credentials if credentials else self.credentials
        parameters = pika.ConnectionParameters(
            host=host, port=port, credentials=credentials, **kwargs,
            heartbeat=60)
        self.parameters = parameters

    def connect(self, connection_type='blocking',
                 parameters:pika.ConnectionParameters=None,
                 **kwargs) -> None:
        """Creates a connection on the RabbitMQ server.

        Stores the connection in the ``connection`` attribute.

          - If ``connection_type`` is 'blocking', creates a BlockingConnection.
          - If ``connection_type`` is 'base', creates a BaseConnection
          - If ``connection_type`` is 'select', creates a SelectConnection

        Parameters
        ----------
        connection_type : str, optional
            The connection type, options are 'blocking', 'base', and 'select',
            by default 'blocking'
        parameters : pika.ConnectionParameters, optional
            Any additional connection parameters (see pika.BlockingConnection
            documentation for details), by default None

        Raises
        ------
        ValueError
            If an invalid connection type is given.
        """
        parameters = parameters if parameters else self.parameters
        allowed_connection_types = ['blocking', 'base', 'select']
        if connection_type not in allowed_connection_types:
            raise ValueError(f"Invalid connection type. "
                             f"Expected one of: {allowed_connection_types}")
        if connection_type == 'blocking':
            connection = pika.BlockingConnection(parameters=parameters)
        elif connection_type == 'base':
            connection = pika.BaseConnection(parameters=parameters, **kwargs)
        elif connection_type == 'select':
            connection = pika.SelectConnection(parameters=parameters, **kwargs)
        else:
            raise ValueError(f"Wrong connection type: {connection_type}")
        self.connection = connection

    def set_channel(self, channel_number:int=None,
                     on_open_callback:callable=None) -> None:
        """Creates a channel on the RabbitMQ server using the ``connection``
        attribute and sets the created channel to the ``channel`` attribute.

        Parameters
        ----------
        channel_number : int, optional
            An optional numerical identifier for the channel, by default None
        on_open_callback : callable, optional
            An optional callback method to call on channel creation,
            by default None

        Raises
        ------
        ValueError
            If the ``connection`` attribute is not set or is an invalid type.
        """
        if isinstance(self.connection, pika.BlockingConnection):
            channel = self.connection.channel(channel_number=channel_number)
        elif isinstance(self.connection, pika.SelectConnection):
            channel = self.connection.channel(
                channel_number=channel_number,
                on_open_callback=on_open_callback)
        elif isinstance(self.connection, pika.BaseConnection):
            channel = self.connection.channel(
                channel_number=channel_number,
                on_open_callback=on_open_callback)
        else:
            raise ValueError(
                f"Incorrect connection type: {type(self.connection)}")
        self.channel = channel

    def exchange_declare(self, name:str, exchange_type:ExchangeType,
                         **kwargs) -> None:
        """Declares an exchange on the RabbitMQ server.

        Creates the exchange using the rmqtools.connection.Exchange class,
        allowing for the storage of information about the exchange. Adds the
        created exchange to the list of exchanges (rmqtools.connection.
        Exchanges) for ease of access later.

        Parameters
        ----------
        name : str
            The name of the exchange
        exchange_type : ExchangeType
            A pika.ExchangeType, e.g. pika.ExchangeType.topic
        """
        e = Exchange(self.channel, name, exchange_type, **kwargs)
        try:
            self.exchanges += e
        except ValueError as err:
            # log that exchange already exists so skipping the creation of it
            # print(f"Exchange '{name}' already exists on this channel. "
            #       "Skipping creation, instead verifying the exchange.")
            pass

    def exchange_delete(self, name:str, if_unused=False) -> None:
        """Deletes the given exchange on the RabbitMQ server and removes it
        from the ``exchanges`` attribute.

        Parameters
        ----------
        name : str
            The name of the exchange to delete.
        if_unused : bool, optional
            If True, only delete the exchange if it is unused, by default False
        """
        self.exchanges.remove(name, if_unused=if_unused)

    def queue_declare(self, name='', binding_keys=[],
                      binding_kwargs={}) -> None:
        """Declares a queue on the RabbitMQ server using the ``channel``
        attribute as the channel to declare the queue on.

        Parameters
        ----------
        name : str, optional
            The name of the queue, by default ''
        binding_keys : list, optional
            An optional list of routing keys to bind the queue to,
            by default []
        binding_kwargs : dict, optional
            An optional dictionary of keyword arguments to pass to the queue
            binding function (see pika.queue_bind for details), by default {}
        """
        q = Queue(self.channel, name=name, binding_keys=binding_keys,
                  binding_kwargs=binding_kwargs)
        try:
            self.queues += q
        except ValueError as err:
            # log that queue already exists so skipping the creation of it
            # print(f"Queue '{name}' already exists on this channel. "
            #       "Skipping creation, instead verifying the queue.")
            pass
