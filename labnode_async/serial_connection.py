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
"""The serial connection module for all Labnodes"""
from __future__ import annotations

import logging
from typing import Any

import serial_asyncio

from .connection import Connection, NotConnectedError
from .devices import FunctionID


class SerialConnection(Connection):
    """
    The serial connection is one of the two types of connections supported by the labnodes. See the`IPConnection` for
    the other option.
    """

    @property
    def tty(self) -> str:
        """
        Returns The hostname of the connection
        """
        return self.__tty_kwargs["url"]

    @property
    def baudrate(self) -> int:
        """
        Returns The port used by the connection
        """
        return self.__tty_kwargs["baudrate"]

    @property
    def endpoint(self) -> str:
        """
        Returns
        -------
        str
            A string representation of the connection endpoint
        """
        return self.tty

    def __init__(self, url: str, *, baudrate: int = 115200, timeout: float = 2.5, **kwargs: Any) -> None:
        """
        Parameters
        ----------
        url: str
            The serial tty like `/dev/ttyUSB0` or `COM3` or an integer port number
        baudrate: int, default=115200
            The baud rate of the serial port
        timeout: float
            the timeout in seconds used when making queries or connection attempts
        *: tuple, optional
            arguments will be ignored
        **kwargs: dict, optional
            keyword arguments will be passed on to Serial(). See
            `https://pyserial.readthedocs.io/en/latest/pyserial_api.html` for more information.
        """
        super().__init__(timeout)
        self.__tty_kwargs = kwargs.copy()
        self.__tty_kwargs["url"] = url
        self.__tty_kwargs["baudrate"] = baudrate
        self.__tty_kwargs["write_timeout"] = timeout

        self.__logger = logging.getLogger(__name__)
        self.__logger.setLevel(logging.ERROR)  # Only log really important messages

    def __str__(self) -> str:
        return f"SerialConnection({self.endpoint})"

    async def send_request(
        self, data: dict[FunctionID | int, Any], response_expected: bool = False
    ) -> dict[int, Any] | None:
        """
        Send a request to the Labnode
        Parameters
        ----------
        data: dict
            The dictionary with the requests.
        response_expected: bool
            Must be true if this is a query or if an ACK is requested
        Returns
        -------
        dict
            A dictionary with results and/or ACKs. They dictionary keys are the FunctionIDs of the request.
        """
        try:
            return await super().send_request(data, response_expected)
        except NotConnectedError:
            # reraise with different message
            raise NotConnectedError("Labnode serial connection not connected.") from None

    async def connect(self) -> None:
        """
        Connect to the Labnode using a serial connection and start the connection listener.
        """
        async with self._read_lock:
            if self.is_connected:
                return

            reader, writer = await serial_asyncio.open_serial_connection(**self.__tty_kwargs)
            self.__logger.info("Labnode serial connection established to port '%s'", self.tty)
            await super()._connect(reader, writer)
