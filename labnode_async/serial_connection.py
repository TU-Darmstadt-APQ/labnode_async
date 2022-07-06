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
from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass
from types import TracebackType
from typing import Type

import serial_asyncio

from labnode_async.labnode import Labnode

from .connection import Connection, NotConnectedError


@dataclass
class TtyOptions:
    baudrate: int
    bytesize: int
    parity: str
    stopbits: int
    xonxoff: bool
    rtscts: bool


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
        return self.__tty

    @property
    def baudrate(self) -> int:
        """
        Returns The port used by the connection
        """
        return self.__tty_options.baudrate

    @property
    def endpoint(self) -> str:
        """
        Returns
        -------
        str
            A string representation of the connection endpoint
        """
        return str(self.__tty)

    def __init__(
        self,
        tty: str,
        baudrate: int = 115200,
        bytesize: int = 8,
        parity: str = "N",
        stopbits: int = 1,
        xonxoff: bool = False,
        rtscts: bool = False,
        timeout: float = 2.5,
    ) -> None:
        """
        Parameters
        ----------
        tty: str
            The serial tty like `/dev/ttyUSB0` or `COM3` or an integer port number
        baudrate: int, default=9600
            The baud rate of the serial port
        timeout: float
            the timeout in seconds used when making queries or connection attempts
        """
        super().__init__(timeout)
        self.__tty = tty
        self.__tty_options: TtyOptions = TtyOptions(baudrate, bytesize, parity, stopbits, xonxoff, rtscts)
        self.__logger = logging.getLogger(__name__)
        self.__logger.setLevel(logging.ERROR)  # Only log really important messages

    async def __aenter__(self) -> Labnode:
        await self.connect()
        return await self._get_device()

    async def __aexit__(
        self, exc_type: Type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        await self.disconnect()

    def __str__(self) -> str:
        return f"SerialConnection({self.endpoint})"

    async def send_request(self, data: dict, response_expected: bool = False) -> dict | None:
        try:
            return await super().send_request(data, response_expected)
        except NotConnectedError:
            # reraise with different message
            raise NotConnectedError("Labnode serial connection not connected.") from None

    async def connect(self) -> None:
        self._read_lock = asyncio.Lock() if self._read_lock is None else self._read_lock
        async with self._read_lock:
            if self.is_connected:
                return

            reader, writer = await serial_asyncio.open_serial_connection(
                url=self.__tty, timeout=self.timeout, write_timeout=self.timeout, **asdict(self.__tty_options)
            )
            self.__logger.info("Labnode serial connection established to port '%s'", self.__tty)
            await super()._connect(reader, writer)
