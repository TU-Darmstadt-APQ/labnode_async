#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ##### BEGIN GPL LICENSE BLOCK #####
#
# Copyright (C) 2020  Patrick Baus
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####
import asyncio
import logging
import sys
sys.path.append("..") # Adds higher directory to python modules path.
import warnings

from source.ip_connection import IPConnectionAsync
from source.devices import DeviceIdentifier
from source.pid_controller import PID_Controller, FeedbackDirection

from binascii import hexlify  # To print the MAC address

loop = asyncio.get_event_loop()
ipcon = IPConnectionAsync(loop=loop)
callback_queue = asyncio.Queue()

running_tasks = []

async def process_callbacks():
    """
    This infinite loop will print all callbacks.
    It waits for packets from the callback queue,
    which the ip connection will push.
    """
    try:
        while 'queue not canceled':
            packet = await callback_queue.get()
            print('Callback received', packet)
    except asyncio.CancelledError:
        logging.getLogger(__name__).debug('Callback queue canceled')

async def stop_loop():
    # Clean up: Disconnect ip connection and stop the consumers
    await ipcon.disconnect()
    for task in running_tasks:
        task.cancel()
    await asyncio.gather(*running_tasks)
    loop.stop()    

def error_handler(task):
    try:
      task.result()
    except Exception:
      asyncio.ensure_future(stop_loop())

async def main():
    try: 
#e        await ipcon.connect(host='127.0.0.1', port=4223)
#        await ipcon.connect(host='10.0.0.131', port=4223)
        await ipcon.connect(host='192.168.1.94', port=4223)
        running_tasks.append(asyncio.ensure_future(process_callbacks()))
        running_tasks[-1].add_done_callback(error_handler)  # Add error handler to catch exceptions
        if (await ipcon.get_device_id() == DeviceIdentifier.PID):
            pid_controller = PID_Controller(ipcon)
            # Test setters
            #await pid_controller.set_serial(1)
            #await pid_controller.set_kp(300 * 165 / 2**16 * 2**20)
            #await pid_controller.set_ki(1.0 * 165 / 2**16 * 2**20)
            #await pid_controller.set_kd(2.0 * 165 / 2**16 * 2**20)
            #await pid_controller.set_setpoint((20.0 + 40) / 165 * 2**16)
            #await pid_controller.set_mac_address([0x00, 0xAA, 0xBB, 0xCC, 0xDE, 0x09])
            #await pid_controller.set_lower_output_limit(0)
            #await pid_controller.set_upper_output_limit(4095)
            #await pid_controller.set_timeout(1000)
            #await pid_controller.set_dac_gain(False)
            #await pid_controller.set_pid_feedback_direction(FeedbackDirection.negative)
            #await pid_controller.set_auto_resume(True)
            #await pid_controller.set_enabled(False)
            #await pid_controller.set_output(1200)
            #await pid_controller.set_enabled(True)

            # Test getters
            print("Device Type: {}".format((await ipcon.get_device_id()).name))
            print("Controller API version: {}.{}.{}".format(*await pid_controller.get_api_version()))
            print("Controller hardware version: {}.{}.{}".format(*await pid_controller.get_hardware_version()))
            print("Controller software version: {}.{}.{}".format(*await pid_controller.get_software_version()))
            print("Controller serial number: {}".format(await pid_controller.get_serial()))
            print("Device temperature: {:.2f} °C".format(await pid_controller.get_device_temperature()))
            print("Humidity: {:.2f} %rH".format(await pid_controller.get_humidity()))
            print("MAC Address: {}".format(hexlify(await pid_controller.get_mac_address(),":").decode("utf-8")))
            print("Controller resumes automatically: {}".format(await pid_controller.get_auto_resume()))
            print("Calibration offset: {} K".format(await pid_controller.get_calibration_offset()))
            #await pid_controller.reset()
    except ConnectionRefusedError:
        logging.getLogger(__name__).error('Could not connect to remote target. Connection refused. Is the device up?')
    except asyncio.CancelledError:
        logging.getLogger(__name__).debug('Stopped the main loop')
    finally:
        asyncio.ensure_future(stop_loop())

# Report all mistakes managing asynchronous resources.
warnings.simplefilter('always', ResourceWarning)
logging.basicConfig(level=logging.INFO)    # Enable logs from the ip connection. Set to debug for even more info

# Start the main loop, then run the async loop forever
running_tasks.append(asyncio.ensure_future(main()))
running_tasks[-1].add_done_callback(error_handler)  # Add error handler to catch exceptions
loop.set_debug(enabled=True)    # Raise all execption and log all callbacks taking longer than 100 ms
#loop.set_exception_handler(handle_exception)
loop.run_forever()
loop.close()
