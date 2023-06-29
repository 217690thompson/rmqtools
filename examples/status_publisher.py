from rmqtools import RmqConnection


rmq = RmqConnection(host='rabbit-1')
rmq.set_status_exchange('status')

def get_status(device_id):
    if device_id == 1:
        return 'ok'
    else:
        return 'down'

@rmq.publish_status(1, 'device.1.status')
def device_status():
    status = get_status(device_id=1)
    msg = f"Device 1 status: {status}"
    return msg

rmq.run()
