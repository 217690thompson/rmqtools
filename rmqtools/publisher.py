"""Tools for a publisher connection"""

import json
from typing import Any, Dict, List, Literal, Union

import pika
from pika.exchange_type import ExchangeType
from rmqtools import Connection


class Publisher():
    """Creates a publisher object that has methods to easily publish messages
    to the RabbitMQ server. This class is used by the higher-level
    RmqConnection class.

    Parameters
    ----------
    ptype : 'topic' | 'fanout' | 'direct'
        The type of publisher. Topic publishers send messages to specific
        routing keys. Fanout publishers send messages to all queues on an
        exchange. Direct publishers are used for RPC calls, and they publish
        to a single queue. The exchange type corresponds to the publisher
        type (i.e. direct exchange for direct publisher).
    exchange : str, optional
        The name of the exchange to use for publishing. Leaving this value
        blank uses the default exchange and is not supported for some types
        of interactions.

    Attributes
    ----------
    ptype : 'fanout' | 'topic' | 'direct'
        The type of publisher this is.
    etype : pika.ExchangeType
        The type of exchange used by this publisher. Corresponds to ptype.
    exchange_name : str
        The name of the exchange this publisher operates on.
    Connection : rmqtools.Connection
        The Connection object associated with this publisher.
    channel : pika.BlockingChannel
        The channel used by this publisher to connect to RabbitMQ.
    exchange : rmqtools.connection.Exchange
        The Exchange object associated with etype and exchange_name. Allows
        for syncing the publisher with the Connection object.
    """

    def __init__(self, ptype:Literal['topic', 'fanout', 'direct'],
                 exchange='') -> None:
        """Creates a publisher object that has methods to easily publish messages
        to the RabbitMQ server. This class is used by the higher-level
        RmqConnection class.

        Parameters
        ----------
        ptype : 'topic' | 'fanout' | 'direct'
            The type of publisher. Topic publishers send messages to specific
            routing keys. Fanout publishers send messages to all queues on an
            exchange. Direct publishers are used for RPC calls, and they publish
            to a single queue. The exchange type corresponds to the publisher
            type (i.e. direct exchange for direct publisher).
        exchange : str, optional
            The name of the exchange to use for publishing. Leaving this value
            blank uses the default exchange and is not supported for some types
            of interactions.
        """
        if ptype == 'fanout':
            etype = ExchangeType.fanout
        elif ptype == 'topic':
            etype = ExchangeType.topic
        elif ptype == 'direct':
            etype = ExchangeType.direct
        else:
            raise ValueError(f"Invalid publisher type '{ptype}'!")
        self.ptype = ptype
        self.etype = etype
        self.exchange_name = exchange

    def connect(self, conn:Connection):
        """Connect the publisher to a Connection object, giving it access to
        the RabbitMQ server. Also declares the exchange defined in instance
        initialization.

        Parameters
        ----------
        conn : Connection
            The ``rmqtools.Connection`` object to use to connect to RabbitMQ
            and link to this publisher. Use a unique Connection per thread.
        """
        self.Connection = conn
        self.channel = self.Connection.channel
        self.Connection.exchange_declare(self.exchange_name, self.etype)
        self.exchange = self.Connection.exchanges.get(self.exchange_name)

    def _get_publish_args(self, routing_key='') -> dict:
        e_name = self.exchange.name if self.exchange else self.exchange_name
        args = {'exchange': e_name}
        if self.ptype != 'fanout':
            args.update(routing_key=routing_key)
        return args

    def publish(self, message:str, routing_key='',
                properties:pika.BasicProperties=None, mandatory=False) -> None:
        """Publish a message on the RabbitMQ server.

        Parameters
        ----------
        message : str
            The content of the message to send.
        routing_key : str, optional
            A routing key to publish the message to, by default ''. A blank
            routing key is only used for fanout publishers. Direct publishers
            will use the name of the queue they are publishing to for the
            routing key. For topic publishers, see the RabbitMQ documentation
            on routing keys
            (https://www.rabbitmq.com/tutorials/tutorial-four-python.html)
        properties : pika.BasicProperties, optional
            Any additional publish properties to pass to
            pika.BlockingChannel.basic_publish, by default None
        mandatory : bool, optional
            Set the mandatory parameter in pika.BlockingChannel.basic_publish,
            by default False
        """
        publish_args = self._get_publish_args(routing_key=routing_key)
        self.Connection.channel.basic_publish(
            **publish_args, body=message, properties=properties,
            mandatory=mandatory)

    def publish_json(self, message: Union[Dict[str, Any], List[Any], int, str,
                                          float, bool, None],
                     routing_key='', properties:pika.BasicProperties=None,
                     mandatory=False) -> None:
        """Publish a JSON object on the RabbitMQ server.

        Parameters
        ----------
        message : Dict[str, Any] | List[Any] | int | str | float | bool | None
            A JSON-serializable object to send via RabbitMQ.
        routing_key : str, optional
            A routing key to publish the message to, by default ''. A blank
            routing key is only used for fanout publishers. Direct publishers
            will use the name of the queue they are publishing to for the
            routing key. For topic publishers, see the RabbitMQ documentation
            on routing keys
            (https://www.rabbitmq.com/tutorials/tutorial-four-python.html)
        properties : pika.BasicProperties, optional
            Any additional publish properties to pass to
            pika.BlockingChannel.basic_publish, by default None
        mandatory : bool, optional
            Set the mandatory parameter in pika.BlockingChannel.basic_publish,
            by default False
        """
        try:
            message = json.dumps(message)
        except TypeError:
            message = str(message)
        self.publish(message, routing_key=routing_key, properties=properties,
                     mandatory=mandatory)
