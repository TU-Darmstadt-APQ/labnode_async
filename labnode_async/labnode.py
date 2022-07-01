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
from abc import ABC, abstractmethod

from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from labnode_async import IPConnection
    from labnode_async.devices import DeviceIdentifier


class Labnode(ABC):
    """
    The labnode base class used by all Labnode devices
    """

    @classmethod
    @property
    @abstractmethod
    def device_identifier(cls) -> DeviceIdentifier:
        """
        Returns
        -------
        DeviceIdentifier
            The device identifier version of the device
        """

    @property
    def api_version(self) -> tuple[int, int, int]:
        """
        Returns
        -------
        tuple
            The API version used by the device to communicate
        """
        return self.__api_version

    @property
    def connection(self) -> IPConnection:
        """
        Returns
        -------
        IPConnection
            The ip connection used by the device
        """
        return self.__connection

    def __init__(self, connection: IPConnection, api_version: tuple[int, int, int]) -> None:
        self.__api_version = api_version
        self.__connection = connection

    @abstractmethod
    async def get_software_version(self) -> tuple[int, int, int]:
        """
        Returns
        -------
        tuple
            The firmware version of the device
        """

    @abstractmethod
    async def get_hardware_version(self) -> tuple[int, int, int]:
        """
        Returns
        -------
        tuple
            The hardware version of the device
        """

    @abstractmethod
    async def get_serial(self) -> int:
        """
        Returns
        -------
        int
            The serial number of the device
        """

    @abstractmethod
    async def get_uuid(self) -> UUID:
        """
        Returns
        -------
        UUID
            The universally unique identifier of the node
        """

    async def set_uuid(self, uuid: UUID) -> None:
        """
        Set the universally unique identifier of the node

        Parameters
        ----------
        uuid: UUID
            The universally unique identifier of the node
        """
