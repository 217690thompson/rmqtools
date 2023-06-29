from rmqtools import RmqConnection, ResponseObject

rmq = RmqConnection(host='rabbit-3')
rmq.set_command_exchange('spec-command')

@rmq.handle_command('device_command')
def handle_command(device_id=None, command=''):
    print(f"Performing operation '{command}' on device {device_id}...")
    if command == 'start':
        status = 'started'
    else:
        status = 'down'
    kwargs = {'status': status, 'device_id': device_id}
    obj = ResponseObject(kwargs=kwargs)
    return obj

rmq.run()
