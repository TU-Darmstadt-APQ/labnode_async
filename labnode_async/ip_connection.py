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
from types import TracebackType
from typing import Type

from .connection import Connection, NotConnectedError
from .labnode import Labnode


class IPConnection(Connection):
    @property
    def hostname(self) -> str:
        """
        Returns The hostname of the connection
        """
        return self.__host[0]

    @property
    def port(self) -> int:
        """
        Returns The port used by the connection
        """
        return self.__host[1]

    @property
    def endpoint(self) -> str:
        return f"{self.hostname}:{self.port}"

    def __init__(self, hostname: str | None = None, port: int = 4223, timeout: float = 2.5) -> None:
        """
        Parameters
        ----------
        host: str
            hostname of the connection
        port: int
            port of the connection
        timeout: float
            the timeout in seconds used when making queries or connection attempts
        """
        super().__init__(timeout)
        self.__host = hostname, port
        self.__logger = logging.getLogger(__name__)
        self.__logger.setLevel(logging.ERROR)  # Only log really important messages

    async def __aenter__(self) -> Labnode:
        await self.connect()
        return await self._get_device()

    async def __aexit__(
            self,
            exc_type: Type[BaseException] | None,
            exc: BaseException | None,
            traceback: TracebackType | None
    ) -> None:
        await self.disconnect()

    def __str__(self) -> str:
        return f"IPConnection({self.hostname}:{self.port})"

    async def send_request(self, data: dict, response_expected: bool = False) -> dict | None:
        if not self.is_connected:
            raise NotConnectedError("Labnode IP connection not connected.")
        # If we are waiting for a response, send the request, then pass on the response as a future
        return await super().send_request(data, response_expected)

    async def connect(self, hostname: str | None = None, port: int | None = None) -> None:
        # We need to lock the `connect()` call, because we
        self._read_lock = asyncio.Lock() if self._read_lock is None else self._read_lock
        async with self._read_lock:
            if self.is_connected:
                return

            self.__host = self.__host[0] if hostname is None else hostname, self.__host[1] if port is None else port

            # wait_for() blocks until the request is done if timeout is None
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(*self.__host),
                self.timeout
            )
            self.__logger.info("Labnode IP connection established to host '%s:%i'", *self.__host)
            await super().connect(reader, writer)
