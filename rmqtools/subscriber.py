"""Tools for a publisher connection"""

import json
import logging
from typing import Any, Dict, List, Literal

import pika
from pika.exchange_type import ExchangeType
from rmqtools import Connection


class Subscriber():

    def __init__(self, queue='', exchange='', etype:ExchangeType=None,
                 routing_keys:List[str]=[], quorum=True,
                 queue_arguments:Dict[str, Any]={}) -> None:
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
        self.channel.queue_declare(**self._get_queue_declare_args())
        for key in self.routing_keys:
            self.channel.queue_bind(**self._get_queue_bind_args(key))
