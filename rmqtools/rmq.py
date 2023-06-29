"""Highest level RabbitMQ wrapper"""

import functools
import logging
import inspect
import signal
import sys
import threading
import time
import uuid
from typing import Dict, List, Literal, Tuple, Callable, Any

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.exchange_type import ExchangeType
from rmqtools import Connection, Publisher, Subscriber, RpcClient, RpcServer, ResponseObject


class RmqConnection():

    def __init__(self, username='guest', password='guest', host='localhost',
                 port=5672, autoconnect=True) -> None:
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

        def handle_exit(sig, frame):
            print('Main thread interrupted by user. '
                  'Shutting down all child threads.')
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, handle_exit)
        signal.signal(signal.SIGTERM, handle_exit)

    def _get_connection(self) -> Connection:
        conn = Connection(self.username, self.password, self.host, self.port,
                          self.autoconnect)
        return conn

    def set_status_exchange(self, name:str) -> None:
        self.exchanges.update({'status': (name, ExchangeType.topic)})

    def set_command_exchange(self, name:str) -> None:
        self.exchanges.update({'command': (name, ExchangeType.direct)})

    def add_exchange(self, name:str, purpose:str, etype:ExchangeType) -> None:
        self.exchanges.update({purpose: (name, etype)})

    def get_publisher(self, name:str, err=True):
        publisher = self.publishers.get(name, False)
        if err and not publisher:
            raise ValueError(f"A publisher with name '{name}' could not be "
                             f"found.")
        return publisher

    def add_publisher(self, name:str, ptype:Literal['topic', 'fanout']='topic',
                      exchange=''):
        if ptype not in ['topic', 'fanout']:
            raise ValueError(f"Publisher type must be either 'topic' or "
                             f"'fanout', not '{ptype}'")
        publisher = Publisher(ptype, exchange=exchange)
        pub = self.get_publisher(name, err=False)
        if pub:
            raise ValueError(f"A publisher with name '{name}' already exists!")
        self.publishers.update({name: publisher})
        self.publish_props.update({name: None})

    def set_publish_props(self, publisher_name:str,
                          publish_props:pika.BasicProperties=None) -> None:
        # throws error if publisher doesn't exist
        self.get_publisher(publisher_name)
        self.publish_props.update({publisher_name: publish_props})

    def get_subscriber(self, name:str, err=True):
        subscriber = self.subscribers.get(name, False)
        if err and not subscriber:
            raise ValueError(f"A subscriber with name '{name}' could not be "
                             f"found.")
        return subscriber

    def add_subscriber(self, name:str, queue:str, exchange='',
                       etype:ExchangeType=ExchangeType.topic,
                       routing_keys:List[str]=[]) -> None:
        subscriber = Subscriber(queue=queue, exchange=exchange, etype=etype,
                                routing_keys=routing_keys,
                                queue_arguments={'durable': True})
        sub = self.get_subscriber(name, err=False)
        if sub:
            raise ValueError(f"A subscriber with name '{name}' already "
                             f"exists!")
        self.subscribers.update({name: subscriber})

    def start(self):
        for thread in self.threads:
            thread.start()

    def run(self):
        print("Starting all RabbitMQ threads. Press enter at any time to "
              "shutdown all child threads.")
        self.start()
        input()
        print("Quit command received. Shutting down all child threads...")
        self.stop()

    def stop(self):
        self.stop_event.set()
        for thread in self.threads:
            thread.join()

    def _publish_status(self, func, interval, routing_key, *args, **kwargs):
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

    def publish_status(self, interval, routing_key):
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

    def _subscribe_status(self, callback:Callable, queue, routing_keys) -> None:
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

    def subscribe_status(self, queue, routing_keys):
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

    def _handle_command(self, worker:Callable[[Any], Any], queue:str) -> None:
        exchange, _ = self.exchanges.get('command')
        server = RpcServer(exchange, queue)
        conn = self._get_connection()
        server.connect(conn)
        server.serve_threadsafe(worker, self.stop_event)

    def handle_command(self, queue:str) -> None:
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
        def decorator(func:Callable[[Any], Any]):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            self.response_handlers.update({command_id: func})
            return wrapper
        return decorator

    def _send_command(self, func:Callable[[], ResponseObject],
                      command_id:str, queue:str) -> None:
        def default_handler():
            pass
        command = func()
        response_handler = self.response_handlers.get(
            command_id, default_handler)
        exchange, _ = self.exchanges.get('command')
        client = RpcClient(exchange)
        conn = self._get_connection()
        client.connect(conn)
        response = client.call_threadsafe(queue, self.stop_event, command)
        args = response.args
        kwargs = response.kwargs
        response_handler(*args, **kwargs)

    def send_command(self, command_id:str, queue:str) -> None:
        def decorator(func:Callable[[], ResponseObject]):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            thread = threading.Thread(
                target=self._send_command,
                args=(wrapper, command_id, queue),
            )
            self.threads.append(thread)
            return wrapper
        return decorator
