from datetime import datetime
import json

from rmqtools import RmqConnection

rmq = RmqConnection(host='')
rmq.set_status_exchange('status')

response_count = {'ok': 0, 'down': 0}
response_count_2 = {'ok': 0, 'down': 0}
msg_times = [datetime.now()]
msg_times_2 = [datetime.now()]

@rmq.subscribe_status('device_logs', ['spec.*.status'])
def handle_response(channel, method, properties, body):
    print(body)
    # try:
    #     data = json.loads(body)
    # except:
    #     data = {'status': 'down'}
    # ok_count = response_count.get('ok')
    # down_count = response_count.get('down')
    # if data.get('status') == 'ok':
    #     ok_count = ok_count + 1
    # else:
    #     down_count = down_count + 1
    # response_count.update(ok=ok_count, down=down_count)

    # total = sum(response_count.values())
    # now = datetime.now()
    # if (now - msg_times[-1]).seconds >= 10:
    #     msg_times.append(now)
    #     print(f"(1) [{now.isoformat()}] Total status messages received: {total}", "\n")

rmq.run()
