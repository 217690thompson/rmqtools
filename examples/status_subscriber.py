from datetime import datetime
import json

from rmqtools import RmqConnection
from pika.adapters.blocking_connection import BlockingChannel

rmq = RmqConnection(host='rabbit-3')
rmq.set_status_exchange('logs')

response_count = {'ok': 0, 'down': 0}
response_count_2 = {'ok': 0, 'down': 0}
msg_times = [datetime.now()]
msg_times_2 = [datetime.now()]

@rmq.subscribe_status('device_logs', ['device.*.status'])
def handle_response(channel:BlockingChannel, method, properties, body):
    try:
        data = json.loads(body)
    except:
        data = {'status': 'down'}
    ok_count = response_count.get('ok')
    down_count = response_count.get('down')
    if data.get('status') == 'ok':
        ok_count = ok_count + 1
    else:
        down_count = down_count + 1
    response_count.update(ok=ok_count, down=down_count)

    total = sum(response_count.values())
    now = datetime.now()
    if (now - msg_times[-1]).seconds >= 10:
        msg_times.append(now)
        print(f"(1) [{now.isoformat()}] Total status messages received: {total}", "\n")

@rmq.subscribe_status('device_logs_2', ['device.*.status'])
def handle_response_2(channel:BlockingChannel, method, properties, body):
    try:
        data = json.loads(body)
    except:
        data = {'status': 'down'}
    ok_count = response_count_2.get('ok')
    down_count = response_count_2.get('down')
    if data.get('status') == 'ok':
        ok_count = ok_count + 1
    else:
        down_count = down_count + 1
    response_count_2.update(ok=ok_count, down=down_count)

    total = sum(response_count_2.values())
    now = datetime.now()
    if (now - msg_times_2[-1]).seconds >= 10:
        msg_times_2.append(now)
        print(f"(2) [{now.isoformat()}] Total status messages received: {total}", "\n")

rmq.run()
