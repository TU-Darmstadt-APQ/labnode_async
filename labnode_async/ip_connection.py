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
"""The ip connection module for all Labnodes"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Tuple

from .connection import Connection, NotConnectedError
from .devices import FunctionID


class IPConnection(Connection):
    """
    The ip connection is one of the two types of connections supported by the labnodes. See the`SerialConnection` for
    the other option.
    """

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
        """A string representation of the connection properties"""
        return f"{self.hostname}:{self.port}"

    def __init__(self, hostname: str, port: int = 4223, timeout: float = 2.5) -> None:
        """
        Parameters
        ----------
        hostname: str
            hostname of the connection
        port: int
            port of the connection
        timeout: float
            the timeout in seconds used when making queries or connection attempts
        """
        super().__init__(timeout)
        self.__host: Tuple[str, int] = hostname, port
        self.__logger = logging.getLogger(__name__)
        self.__logger.setLevel(logging.ERROR)  # Only log really important messages

    def __str__(self) -> str:
        return f"IPConnection({self.hostname}:{self.port})"

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
            raise NotConnectedError("Labnode IP connection not connected.") from None

    async def connect(self) -> None:
        """
        Connect to the Labnode using an ip connection and start the connection listener.
        """
        async with self._read_lock:
            if self.is_connected:
                return

            # wait_for() blocks until the request is done if timeout is None
            reader, writer = await asyncio.wait_for(asyncio.open_connection(*self.__host), self.timeout)
            self.__logger.info("Labnode IP connection established to host '%s:%i'", *self.__host)
            await super()._connect(reader, writer)
