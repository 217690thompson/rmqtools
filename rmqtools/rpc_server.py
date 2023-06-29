import functools
import json
import logging
import threading
import uuid
from typing import Any, Dict, List, Literal, Callable, Optional

import pika
from pika.channel import Channel
from pika.spec import Basic
from pika.exchange_type import ExchangeType
from rmqtools import Connection, ResponseObject


class RpcServer():

    def __init__(self, exchange:str, queue:str):
        self.etype = ExchangeType.direct
        self.exchange_name = exchange
        self.queue_name = queue

    def connect(self, conn:Connection):
        self.Connection = conn
        self.channel = self.Connection.channel
        self.Connection.exchange_declare(self.exchange_name, self.etype)
        self.exchange = self.Connection.exchanges.get(self.exchange_name)
        self.channel.queue_declare(queue=self.queue_name)
        self.channel.queue_bind(self.queue_name, self.exchange_name,
                                self.queue_name)

    def on_request(self, worker:Callable[[Any], ResponseObject], ch:Channel,
                   method:Basic.Deliver, props:pika.BasicProperties,
                   body:bytes):
        """Called when the client requests data from the server.
        Usage:
        >>> callback = functools.partial(on_request, worker)
        >>> channel.basic_consume(queue='rpc_queue',
                                  on_message_callback=callback)

        Parameters
        ----------
        worker : (Any) -> ResponseObject
            The worker function that the request will be passed to. Should
            be of the form `def worker(...)` where the arguments and keyword
            arguments passed by the RPC client will fill out the parameters
            of the worker function. The worker function should return a
            rmqtools.ResponseObject with the arguments and keyword arguments
            that will be passed to the client's response handler.
        ch : Channel
            Filled in automatically by `basic_consume`
        method : Deliver
            Filled in automatically by `basic_consume`
        props : BasicProperties
            Filled in automatically by `basic_consume`
        body : bytes
            Filled in automatically by `basic_consume`

        Returns
        -------
        Any
            Returns the response of the worker function
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
        self.channel.basic_qos(prefetch_count=1)
        callback = functools.partial(self.on_request, worker)
        self.channel.basic_consume(queue=self.queue_name,
                                   on_message_callback=callback)
        self.channel.start_consuming()

    def serve_threadsafe(self, worker:Callable[[Any], ResponseObject],
                         stop_event:threading.Event) -> None:
        self.channel.basic_qos(prefetch_count=1)

        for method, props, body in self.channel.consume(
            self.queue_name, inactivity_timeout=5):
            if all([method, props, body]):
                self.on_request(worker, self.channel, method, props, body)
            if stop_event.is_set():
                break
