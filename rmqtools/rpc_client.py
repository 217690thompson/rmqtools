import json
import logging
import threading
import uuid
from typing import Any, Dict, List, Literal, Callable, Union

import pika
from pika.exchange_type import ExchangeType
from rmqtools import Connection, Publisher, ResponseObject


class RpcClient():

    def __init__(self, exchange:str):
        self.etype = ExchangeType.direct
        self.exchange_name = exchange
        self.corr_id = None

        self.response: Union[ResponseObject, None]
        self.response = None

    def connect(self, conn:Connection):
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

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = ResponseObject(**json.loads(body))

    def _get_publish_props(self):
        props = pika.BasicProperties(
            reply_to=self.callback_queue,
            correlation_id=self.corr_id,
        )
        return props

    def call(self, queue:str, command:ResponseObject) -> ResponseObject:
        self.response = None
        self.corr_id = str(uuid.uuid4())

        body = ResponseObject.__dict__
        props = self._get_publish_props()
        self.publisher.publish_json(body, routing_key=queue,
                                    properties=props)
        self.Connection.connection.process_data_events(time_limit=None)
        return self.response

    def call_threadsafe(self, queue:str, stop_event:threading.Event,
                        command:ResponseObject) -> ResponseObject:
        self.response = None
        self.corr_id = str(uuid.uuid4())

        body = command.__dict__
        props = self._get_publish_props()
        print(queue)
        self.publisher.publish_json(body, routing_key=queue,
                                    properties=props)
        print('foo')
        while not stop_event.is_set():
            self.Connection.connection.process_data_events(time_limit=1)
            if self.response is not None:
                break
        return self.response
