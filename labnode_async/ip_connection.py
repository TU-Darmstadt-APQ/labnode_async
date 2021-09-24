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
from enum import Enum, unique
import errno
import logging

# All messages are COBS encoded, while the data is serialized using the CBOR protocol
from cobs import cobs
import cbor2 as cbor

from .devices import FunctionID, DeviceIdentifier

class UnknownFunctionError(Exception):
    pass

@unique
class EnumerationType(Enum):
    AVAILABLE = 0
    CONNECTED = 1
    DISCONNECTED = 2

@unique
class MessageType(Enum):
    DEVICE_CONNECTED = 0
    DEVICE_DISCONNECTED = 1

@unique
class Flags(Enum):
    OK = 0
    INVALID_PARAMETER = 1
    FUNCTION_NOT_SUPPORTED = 2

DEFAULT_WAIT_TIMEOUT = 2.5 # in seconds

class IPConnectionAsync:
    SEPARATOR = b'\x00'

    @property
    def timeout(self):
        """
        Returns the timeout for async operations in seconds
        """
        return self.__timeout

    @timeout.setter
    def timeout(self, value):
        self.__timeout = abs(int(value))

    @property
    def logger(self):
        return self.__logger

    def __init__(self, host=None, port=4223):
        self.__running_tasks = []
        self.__reader, self.__writer = None, None
        self.__host = host
        self.__port = port
        self.__request_id_queue = None
        self.__timeout = DEFAULT_WAIT_TIMEOUT
        self.__pending_requests = {}

        self.__logger = logging.getLogger(__name__)

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        await self.disconnect()

    def __encode_data(self, data):
        return bytearray(cobs.encode(data) + self.SEPARATOR)

    @staticmethod
    def __decode_data(data):
        return cobs.decode(data[:-1])  # Strip the separator

    async def get_device_id(self):
        self.logger.debug('Getting device type')
        result = await self.send_request(
            data={
              FunctionID.GET_DEVICE_TYPE: None,
            },
            response_expected=True
        )
        return DeviceIdentifier(result[FunctionID.GET_DEVICE_TYPE])

    async def send_request(self, data, response_expected=False):
        # If we are waiting for a response, send the request, then pass on the response as a future
        request_id =  await self.__request_id_queue.get()
        data[FunctionID.REQUEST_ID] = request_id
        self.logger.debug('Sending data: %(payload)s', {'payload': data})
        request = self.__encode_data(
          cbor.dumps(data)
        )
        self.logger.debug('Sending request: %(payload)s', {'payload': request})
        try:
            self.__writer.write(request)
            if response_expected:
                self.logger.debug('Waiting for reply for request number %(request_id)s.', {'request_id': request_id})
                # The future will be resolved by the main_loop() and __process_packet()
                self.__pending_requests[request_id] = asyncio.Future()
                response  = await asyncio.wait_for(self.__pending_requests[request_id], self.__timeout)
                self.logger.debug('Got reply for request number %(request_id)s: %(response)s', {'request_id': request_id, 'response': response})
                return response
        finally:
            # Return the sequence number
            self.__request_id_queue.put_nowait(request_id)

    async def __read_packets(self):
        while 'loop not cancelled':
            try:
                data = await asyncio.wait_for(self.__reader.readuntil(self.SEPARATOR), self.__timeout)
                self.logger.debug('Received COBS encoded data: %(data)s', {'data': data.hex()})
                data = self.__decode_data(data)
                self.logger.debug('Unpacked CBOR encoded data: %(data)s', {'data': data.hex()})
                data = cbor.loads(data)
                data = {FunctionID(key) : value for key, value in data.items()}
                self.logger.debug('Decoded received data: %(data)s', {'data': data})

                yield data
            except ValueError:
                # Raised by FunctionID(key)
                self.logger.error('Received invalid function id in data: %(data)s', {'data': data})
                yield data
            except asyncio.TimeoutError:
                pass
            except Exception:  # We parse undefined content from an external source pylint: disable=broad-except
                # TODO: Add explicit error handling for CBOR
                self.logger.exception('Error while reading packet.')
                pass

    async def __process_packet(self, data):
        try:
            request_id = data.get(FunctionID.REQUEST_ID)
        except AttributeError:
            self.logger.error('Received invalid data: %(data)s', {'data': data})
        else:
            try:
                # Get the future and mark it as done
                future = self.__pending_requests.pop(request_id)
                future.set_result(data)
            except KeyError:
                # Drop the packet, because it is not our sequence number
                pass

    async def main_loop(self):
        self.logger.info('Sensornode IP connection established to host %(host)s', {'host': self.__host})
        try:
            async for packet in self.__read_packets():
                # Read packets from the socket and process them.
                await self.__process_packet(packet)
        finally:
            await self.__close_transport()

    async def connect(self, host=None, port=None):
        if host is not None:
            self.__host = host
        if port is not None:
            self.__port = port

        # The maximum sequency number is a uint8_t. That means 255.
        # We only use the range of 0 to 23, because that requires only
        # one byte when CBOR encoded
        self.__request_id_queue = asyncio.Queue(maxsize=24)
        for i in range(24):
            self.__request_id_queue.put_nowait(i)

        self.__reader, self.__writer = await asyncio.open_connection(self.__host, self.__port)
        self.__running_tasks.append(asyncio.create_task(self.main_loop()))

    async def disconnect(self):
        for task in self.__running_tasks:
            task.cancel()
        try:
            await asyncio.gather(*self.__running_tasks)
        except asyncio.CancelledError:
            pass
        self.__host = None

    async def __close_transport(self):
        # Flush data
        try:
            self.__writer.write_eof()
            await self.__writer.drain()
            self.__writer.close()
            await self.__writer.wait_closed()
        except OSError as exc:
            if exc.errno == errno.ENOTCONN:
                pass # Socket is no longer connected, so we can't send the EOF.
            else:
                raise
        finally:
            self.__writer, self.__reader = None, None
            # Cancel all pending requests, that have not been resolved
            for _, future in self.__pending_requests.items():
                if not future.done():
                    future.set_exception(ConnectionError('Sensornode IP connection closed.'))
            self.__pending_requests = {}
