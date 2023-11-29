from rmqtools import RmqConnection, ResponseObject

rmq = RmqConnection(host='localhost')
rmq.set_command_exchange('test_exg')

@rmq.send_command('start_device', 'device_command')
def start() -> ResponseObject:
    spec_id = 'spec1'
    command = 'stop'
    kwargs = {'spec_id': spec_id, 'command': command}
    obj = ResponseObject(kwargs=kwargs)
    return obj

@rmq.handle_response('start_device')
def print_status(success='', error=''):
    if error:
        print(f"[ERROR] {error}")
    else:
        print(f"Device status: {success}")

rmq.run()
