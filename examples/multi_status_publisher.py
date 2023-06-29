import threading
from datetime import datetime

from rmqtools import RmqConnection


response_count = {'ok': 0, 'down': 0}
msg_times = [datetime.now()]

def get_status(device_id):
    if device_id == 5:
        return 'down'
    else:
        return 'ok'

def send_status(device_id):
    status = get_status(device_id)
    count = response_count.get(status)
    response_count.update({status: count + 1})
    msg = {'device': device_id, 'status': status}
    now = datetime.now()
    total = sum(response_count.values())
    if (now - msg_times[-1]).seconds >= 10:
        msg_times.append(now)
        print(f"[{now.isoformat()}] Total status messages sent: {total}", "\n")
    return msg

rmq = RmqConnection(host='rabbit-1')
rmq.set_status_exchange('logs')

for i in range(16):
    thread = threading.Thread(
        target=rmq._publish_status,
        args=(send_status, 1, f'device.{i}.status'),
        kwargs={'device_id': i},
    )
    rmq.threads.append(thread)

rmq.run()
