"""Tools for a publisher connection"""

import json
import logging
from typing import Literal

import pika
from pika.exchange_type import ExchangeType
from pika.delivery_mode import DeliveryMode

from rmqtools import Connection


class Publisher():

    def __init__(self, ptype:Literal['topic', 'fanout', 'direct'],
                 exchange='') -> None:
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
        publish_args = self._get_publish_args(routing_key=routing_key)
        self.Connection.channel.basic_publish(
            **publish_args, body=message, properties=properties,
            mandatory=mandatory)

    def publish_json(self, message, routing_key='',
                properties:pika.BasicProperties=None, mandatory=False) -> None:
        try:
            message = json.dumps(message)
        except TypeError:
            message = str(message)
        self.publish(message, routing_key=routing_key, properties=properties,
                     mandatory=mandatory)
