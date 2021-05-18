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

ipcon = IPConnectionAsync()
running_tasks = []

async def process_callbacks(callback_queue):
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

async def shutdown():
    # Clean up: Disconnect ip connection and stop the consumers
    for task in running_tasks:
        task.cancel()
    await asyncio.gather(*running_tasks)
    await ipcon.disconnect()    # Disconnect the ip connection last to allow cleanup

def error_handler(task):
    try:
      task.result()
    except Exception:
      asyncio.ensure_future(shutdown())

async def main():
    try: 
#        await ipcon.connect(host='127.0.0.1', port=4223)
#        await ipcon.connect(host='10.0.0.131', port=4223)
        await ipcon.connect(host='192.168.1.94', port=4223)
        callback_queue = asyncio.Queue()
        running_tasks.append(asyncio.ensure_future(process_callbacks(callback_queue)))
        running_tasks[-1].add_done_callback(error_handler)  # Add error handler to catch exceptions
        if (await ipcon.get_device_id() == DeviceIdentifier.PID):
            pid_controller = PID_Controller(ipcon)
            # Test setters
            #await pid_controller.set_serial(1)
            # In this example our input temperature range of the sensor is:
            # -40 °C - 125 °C and will be in Q16.16 (unsigned) notation,
            # this means it will be in the range of [0,1] in Q16.16 notation in units of (1/165 K)
            # The output is a 12 bit DAC, so the output must be interpreted in Q11.20 (11 bits + 1 sign bit)
            # notation.
            # In order to convert from Q16 to Q20 we need divide by 2**16 and multiply by 2**20
            # As the units coming from the sensor are in (1/165 K) we need to muliply k_(pid) by 165.
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
        print('Stopped the main loop')
    finally:
        logging.getLogger(__name__).debug('Shutting down the main task')
        asyncio.ensure_future(shutdown())

# Report all mistakes managing asynchronous resources.
warnings.simplefilter('always', ResourceWarning)
logging.basicConfig(level=logging.INFO)    # Enable logs from the ip connection. Set to debug for even more info

# Start the main loop and run the async loop forever
asyncio.run(main(),debug=True)
