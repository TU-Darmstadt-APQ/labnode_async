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
from binascii import hexlify  # To print the MAC address
import logging
import warnings

from labnode_async import IPConnection, PidController, FeedbackDirection
from labnode_async.devices import DeviceIdentifier

async def main():
    try:
        ipcon = IPConnection(host='127.0.0.1', port=4223)
        async with ipcon as pid_controller:
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
            #await pid_controller.set_pid_feedback_direction(FeedbackDirection.NEGATIVE)
            #await pid_controller.set_auto_resume(True)
            #await pid_controller.set_enabled(False)
            #await pid_controller.set_output(1200)
            #await pid_controller.set_enabled(True)

            # Test getters
            print(f"Device Type: {pid_controller.DEVICE_IDENTIFIER.name}")
            print(f"Controller API version: {'.'.join(map(str, await pid_controller.get_api_version()))}")
            print(f"Controller hardware version: {'.'.join(map(str, await pid_controller.get_hardware_version()))}")
            print(f"Controller software version: {'.'.join(map(str, await pid_controller.get_software_version()))}")
            print(f"Controller serial number: {await pid_controller.get_serial()}")
            print(f"Device temperature: {await pid_controller.get_device_temperature():.2f} °C")
            print(f"Humidity: {await pid_controller.get_humidity():.2f} %rH")
            print(f"MAC Address: {hexlify(await pid_controller.get_mac_address(),':').decode('utf-8')}")
            print(f"Controller resumes automatically: {await pid_controller.get_auto_resume()}")
            print(f"Calibration offset: {await pid_controller.get_calibration_offset()} K")
            #await pid_controller.reset()
    except ConnectionRefusedError:
        logging.getLogger(__name__).error('Could not connect to remote target. Connection refused. Is the device up?')
    except asyncio.CancelledError:
        print('Stopped the main loop')
    finally:
        logging.getLogger(__name__).debug('Shutting down the main task')

# Report all mistakes managing asynchronous resources.
warnings.simplefilter('always', ResourceWarning)
logging.basicConfig(level=logging.INFO)    # Enable logs from the ip connection. Set to debug for even more info

# Start the main loop and run the async loop forever
asyncio.run(main(),debug=True)
