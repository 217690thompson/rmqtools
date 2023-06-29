from rmqtools import RmqConnection, ResponseObject

rmq = RmqConnection(host='rabbit-1')
rmq.set_command_exchange('spec-command')

@rmq.send_command('start_device', 'device_command')
def start() -> ResponseObject:
    device_num = 1
    command = 'start'
    args = [device_num]
    kwargs = {'command': command}
    obj = ResponseObject(args, kwargs)
    print('test')
    return obj

@rmq.handle_response('start_device')
def print_status(device_id, status=''):
    print(f"Device {device_id} status: {status}")

rmq.run()
