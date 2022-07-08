#!/usr/bin/env python3
"""This is simple example that queries the Labnode for some basic information about itself."""
import asyncio

from labnode_async import IPConnection, PidController


async def main():
    """Connect to the labnode and run the example."""
    connection = IPConnection(hostname="localhost")
    # connection = SerialConnection(tty="/dev/ttyACM0")  # Alternative serial connection
    device: PidController
    async with connection as device:
        # Test getters
        print(f"Controller hardware version: {await device.get_hardware_version()}")
        print(f"Controller software version: {await device.get_software_version()}")
        print(f"Controller serial number: {await device.get_serial()}")
        print(f"Controller UUID: {await device.get_uuid()}")


# Start the main loop and run the async loop forever
asyncio.run(main(), debug=True)
