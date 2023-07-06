"""
Rmqtools
========

Provides wrappers on top of the Pika library for easy RabbitMQ development in
Python.

How to use the documentation
----------------------------
Documentation is available in two forms: docstrings provided with the code,
and an API reference, available on Read the Docs at ...
"""

__version__ = '1.0.0-alpha'

import logging

# suppress logging warnings while importing rabbitmq-tools
logging.getLogger(__name__).addHandler(logging.NullHandler())

from rmqtools.connection import ResponseObject
from rmqtools.connection import Connection
from rmqtools.publisher import Publisher
from rmqtools.subscriber import Subscriber
from rmqtools.rpc import RpcClient, RpcServer

from rmqtools.rmq import RmqConnection
