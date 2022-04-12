# -*- coding: utf-8 -*-
# ##### BEGIN GPL LICENSE BLOCK #####
#
# Copyright (C) 2022  Patrick Baus
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
import errno
import logging
from asyncio import StreamReader, StreamWriter
from typing import AsyncIterator, Optional

# All messages are COBS encoded, while the data is serialized using the CBOR protocol
from cobs import cobs
import cbor2 as cbor

from .devices import FunctionID, DeviceIdentifier
from .device_factory import device_factory
from .labnode import Labnode


class NotConnectedError(ConnectionError):
    """
    Raised if there is no connection
    """


class Connection:
    _SEPARATOR = b'\x00'

    @property
    def timeout(self) -> float:
        """
        Returns the timeout for async operations in seconds
        """
        return self.__timeout

    @timeout.setter
    def timeout(self, value: float) -> None:
        self.__timeout = None if value is None else abs(float(value))

    @property
    def is_connected(self) -> bool:
        """
        Returns *True* if, the connection is established.
        """
        return self.__writer is not None and not self.__writer.is_closing()

    @property
    def endpoint(self) -> str:
        """
        Returns
        -------
        str
            A string representation of the connection endpoint
        """
        raise NotImplementedError

    def __init__(self, timeout: float = 2.5) -> None:
        """
        Parameters
        ----------
        timeout: float
            the timeout in seconds used when making queries or connection attempts
        """
        self.__running_tasks = []
        self.__reader, self.__writer = None, None
        self.__request_id_queue = None
        self.timeout = timeout
        self._read_lock = None  # We need to lock the asyncio stream reader
        self.__pending_requests = {}

        self.__logger = logging.getLogger(__name__)
        self.__logger.setLevel(logging.WARNING)     # Only log really important messages

    def __encode_data(self, data: str) -> bytearray:
        return bytearray(cobs.encode(data) + self._SEPARATOR)

    @staticmethod
    def __decode_data(data):
        return cobs.decode(data[:-1])  # Strip the separator

    async def get_device_id(self) -> tuple[DeviceIdentifier, tuple[int, int, int]]:
        self.__logger.debug("Getting device type")
        result = await self.send_request(
            data={
              FunctionID.GET_DEVICE_TYPE: None,
              FunctionID.GET_API_VERSION: None,
            },
            response_expected=True
        )
        try:
            return DeviceIdentifier(result[FunctionID.GET_DEVICE_TYPE]), tuple(result[FunctionID.GET_API_VERSION])
        except KeyError:
            self.__logger.error("Got invalid reply for device id request: %s", result)
            raise

    async def _get_device(self) -> Labnode:
        device_id, api_version = await self.get_device_id()
        return device_factory.get(device_id, self, api_version=api_version)

    async def connect(self, reader: StreamReader, writer: StreamWriter) -> None:
        self.__reader, self.__writer = reader, writer

        # The maximum sequence number is a uint8_t. That means 255.
        # We only use the range of 0 to 23, because that requires only
        # one byte when CBOR encoded
        self.__request_id_queue = asyncio.Queue(maxsize=24)
        for i in range(24):
            self.__request_id_queue.put_nowait(i)

        self.__running_tasks.append(asyncio.create_task(self.main_loop()))

    async def send_request(self, data: dict, response_expected: bool = False) -> Optional[dict]:
        # Check for `is_connected` before calling this function
        # If we are waiting for a response, send the request, then pass on the response as a future
        request_id = await self.__request_id_queue.get()
        try:
            data[FunctionID.REQUEST_ID] = request_id
            self.__logger.debug("Sending data: %(payload)s", {'payload': data})
            request = self.__encode_data(
                cbor.dumps(data)
            )
            self.__logger.debug('Sending request: %(payload)s', {'payload': request})
            self.__writer.write(request)
            if response_expected:
                self.__logger.debug('Waiting for reply for request number %(request_id)s.', {'request_id': request_id})
                # The future will be resolved by the main_loop() and __process_packet()
                self.__pending_requests[request_id] = asyncio.Future()
                try:
                    # wait_for() blocks until the request is done if timeout is None
                    response = await asyncio.wait_for(self.__pending_requests[request_id], self.__timeout)
                finally:
                    # Cleanup. Note: The request_id, might not be in the dict anymore, because
                    # if the remote endpoint shuts down the connection, __close_transport() is called,
                    # which clears all pending requests.
                    self.__pending_requests.pop(request_id, None)
                self.__logger.debug(
                    "Got reply for request number %(request_id)s: %(response)s",
                    {'request_id': request_id, 'response': response}
                )
                # strip the request id, because we have added it, and the result should be transparent
                del response[FunctionID.REQUEST_ID]
                return response
                # TODO: Raise invalid command errors (252)
        finally:
            # Return the sequence number
            self.__request_id_queue.put_nowait(request_id)

    async def __read_packets(self) -> AsyncIterator[dict]:
        while 'loop not cancelled':
            try:
                # We need to lock the stream reader, because only one coroutine is allowed to read
                # data
                async with self._read_lock:
                    data = await self.__reader.readuntil(self._SEPARATOR)
                self.__logger.debug("Received COBS encoded data: %(data)s", {'data': data.hex()})
                data = self.__decode_data(data)
                self.__logger.debug("Unpacked CBOR encoded data: %(data)s", {'data': data.hex()})
                data = cbor.loads(data)
                self.__logger.debug("Decoded received data: %(data)s", {'data': data})

                yield data
            except (asyncio.exceptions.IncompleteReadError, ConnectionResetError):
                # the remote endpoint closed the connection
                self.__logger.error(
                    "Labnode serial connection: The remote endpoint '%s' closed the connection.",
                    self.endpoint
                )
                break   # terminate the connection
            except cobs.DecodeError as exp:
                # raised by `self.__decode_data()`
                self.__logger.error("Cobs decode error: %s, Data was '%s'", exp, data.hex())
            except Exception:  # We parse undefined content from an external source pylint: disable=broad-except
                # TODO: Add explicit error handling for CBOR
                self.__logger.exception('Error while reading packet.')
                await asyncio.sleep(0.1)

    async def __process_packet(self, data: dict) -> None:
        try:
            request_id = data.get(FunctionID.REQUEST_ID)
        except AttributeError:
            self.__logger.error("Received invalid data: %(data)s", {'data': data})
        else:
            try:
                # Get the future and mark it as done
                future = self.__pending_requests[request_id]
                if not future.cancelled():
                    # TODO: Check for invalid commands and raise errors
                    future.set_result(data)
            except KeyError:
                # Drop the packet, because it is not our sequence number
                pass

    async def main_loop(self) -> None:
        try:
            async for packet in self.__read_packets():
                # Read packets from the socket and process them.
                await self.__process_packet(packet)
        finally:
            await self.__close_transport()

    async def disconnect(self) -> None:
        if not self.is_connected:
            return
        # This will cancel the main task, which will shut down the transport via __close_transport()
        [task.cancel() for task in self.__running_tasks]
        try:
            await asyncio.gather(*self.__running_tasks)
        except asyncio.CancelledError:
            pass
        finally:
            self._read_lock = None

    async def __close_transport(self) -> None:
        # Flush data
        try:
            if self.__writer.can_write_eof():
                self.__writer.write_eof()
            await self.__writer.drain()
            self.__writer.close()
            await self.__writer.wait_closed()
        except ConnectionError:
            # Ignore connection related errors, because we are dropping the connection anyway
            pass
        except OSError as exc:
            if exc.errno == errno.ENOTCONN:
                pass    # Socket is no longer connected, so we can't send the EOF.
            else:
                raise
        finally:
            self.__writer, self.__reader = None, None
            # Cancel all pending requests, that have not been resolved
            for _, future in self.__pending_requests.items():
                if not future.done():
                    future.set_exception(ConnectionError(f"Connection to '{self.endpoint}' closed."))
            self.__pending_requests = {}
