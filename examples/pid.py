#!/usr/bin/env python3
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
"""This is an example, that demonstrates the most common functions calls of PID controller labnode."""
import asyncio
import logging
import uuid  # pylint: disable=unused-import
import warnings
from binascii import hexlify  # To print the MAC address

from labnode_async import (  # pylint: disable=unused-import
    FeedbackDirection,
    IPConnection,
    PidController,
    SerialConnection,
)


async def main():
    """Connect to the labnode and run the example."""
    try:
        connection = IPConnection(hostname="localhost", port=4224)
        # connection = SerialConnection(tty="/dev/ttyACM0")  # Alternative serial connection
        async with connection as device:
            # Test setters
            # await device.set_serial(1)
            # await device.set_uuid(uuid.uuid4())    # Generate and set a random UUID
            # In this example our input temperature range of the sensor is:
            # -40 °C - 125 °C and will be in Q16.16 (unsigned) notation,
            # this means it will be in the range of [0,1] in Q16.16 notation in units of (1/165 K)
            # The output is a 12 bit DAC, so the output must be interpreted in Q11.20 (11 bits + 1 sign bit)
            # notation.
            # In order to convert from Q16 to Q20 we need divide by 2**16 and multiply by 2**20
            # As the units coming from the sensor are in (1/165 K) we need to multiply k_(pid) by 165.
            # await device.set_kp(200 * 165 / 2**16 * 2**20)
            # await device.set_ki(0.5 * 165 / 2**16 * 2**20)
            # await device.set_kd(2.0 * 165 / 2**16 * 2**20)
            # setpoint = 20.0
            # await device.set_setpoint((setpoint + 40) / 165 * 2**16)
            # await device.set_mac_address([0x00, 0xAA, 0xBB, 0xCC, 0xDE, 0x09])
            # await device.set_lower_output_limit(0)
            # await device.set_upper_output_limit(4095)
            # await device.set_timeout(1000)
            # await device.set_dac_gain(False)
            # await device.set_pid_feedback_direction(FeedbackDirection.NEGATIVE)
            # await device.set_auto_resume(True)
            # await device.set_enabled(False)
            # await device.set_output(1200)
            # await device.set_enabled(True)
            # await device.set_fallback_update_interval(1000)
            # Secondary PID
            # await device.set_kp(0.8*200 * 165 / 2**16 * 2**20, config_id=1)
            # await device.set_ki(0.8*1.5 * 165 / 2**16 * 2**20, config_id=1)
            # await device.set_kd(0.8*2.0 * 165 / 2**16 * 2**20, config_id=1)
            # setpoint = 27.6
            # await device.set_setpoint((setpoint + 40) / 165 * 2**16, config_id=1)
            # await device.set_secondary_config(1)

            # Test getters
            print(f"Device Type: {device.device_identifier.name}")
            print(f"Controller API version: {'.'.join(map(str, device.api_version))}")
            print(f"Controller hardware version: {'.'.join(map(str, await device.get_hardware_version()))}")
            print(f"Controller software version: {'.'.join(map(str, await device.get_software_version()))}")
            print(f"Controller serial number: {await device.get_serial()}")
            print(f"Controller UUID: {await device.get_uuid()}")
            # print(f"Humidity: {await device.get_humidity()} %rH")
            device_temperature = await device.get_device_temperature()
            print(f"Device temperature: {device_temperature} K ({device_temperature - 273.15} °C)")
            # print(f"Humidity: {await device.get_humidity():.2f} %rH")
            print(f"MAC Address: {hexlify(await device.get_mac_address(),':').decode('utf-8').upper()}")
            print(f"Controller is enabled: {await device.is_enabled()}")
            print(f"Controller resumes automatically: {await device.get_auto_resume()}")
            print(f"Controller times out after: {await device.get_timeout()} ms")
            print(f"Fallback update interval: {await device.get_fallback_update_interval()} ms")
            k_p, k_i, k_d = asyncio.gather(device.get_kp(), device.get_ki(), device.get_kd())
            print(f"PID Kp, Ki, Kd: {(k_p/165*2**16/2**20, k_i/165*2**16/2**20, k_d/165*2**16/2**20)}")
            k_p, k_i, k_d = asyncio.gather(
                device.get_kp(config_id=1), device.get_ki(config_id=1), device.get_kd(config_id=1)
            )
            print(f"Secondary PID Kp, Ki, Kd: {(k_p/165*2**16/2**20, k_i/165*2**16/2**20, k_d/165*2**16/2**20)}")
            print(f"Output limit: {(await device.get_lower_output_limit(), await device.get_upper_output_limit())}")
            print(f"PID feedback direction: {await device.get_pid_feedback_direction():s}")
            print(f"Current setpoint: {await device.get_setpoint()*165/2**16-40:.2f} °C")
            print(f"Secondary PID setpoint: {await device.get_setpoint(config_id=1)*165/2**16-40:.2f} °C")
            print(f"Backup config id: {await device.get_secondary_config()}")
            print(f"Output gain (0-10V) enabled: {await device.is_dac_gain_enabled()}")
            output = await device.get_output()
            print(f"Current output: {output} ({output / 40.95:.1f} %)")
            print(f"Number of open sockets: {await device.get_active_connection_count()}")

            # await device.reset()
    except ConnectionRefusedError:
        logging.getLogger(__name__).error("Could not connect to remote target. Connection refused. Is the device up?")
    except asyncio.CancelledError:
        print("Stopped the main loop")
    finally:
        logging.getLogger(__name__).debug("Shutting down the main task")


# Report all mistakes managing asynchronous resources.
warnings.simplefilter("always", ResourceWarning)
logging.basicConfig(level=logging.INFO)  # Enable logs from the ip connection. Set to debug for even more info

# Start the main loop and run the async loop forever
asyncio.run(main(), debug=True)
