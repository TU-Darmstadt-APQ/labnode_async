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
"""
The device factory which allows creating instances of Labnodes from their device id
"""
from typing import Any

from .devices import DeviceIdentifier
from .labnode import Labnode
from .pid_controller import PidController


class DeviceFactory:
    """
    A sensor host factory to select the correct driver for given database
    config.
    """
    def __init__(self) -> None:
        self.__available_devices = {}

    def register(self, device: Labnode) -> None:
        """
        Register a driver with the factory. Should only be called in this file.

        Parameters
        ----------
        device: Labnode
            A Labnode device to be registered with the factory.
        """
        self.__available_devices[device.DEVICE_IDENTIFIER] = device

    def get(self, device_id: DeviceIdentifier, connection: 'IPConnection', *args: Any, **kwargs: Any) -> Labnode:
        """
        Look up the driver for a given database entry. Raises a `ValueError` if
        the driver is not registered.

        Parameters
        ----------
        connection: ip_connection.IPConnection
            The ip connection to be used by the device
        device_id: devices.DeviceIdentifier
            The device specific id

        Returns
        -------
        Labnode
            The labnode device

        Raises
        ----------
        ValueError
        """
        try:
            return self.__available_devices[device_id](connection, *args, **kwargs)
        except KeyError:
            raise ValueError(f'No device available for id {device_id}') from None


device_factory = DeviceFactory()
device_factory.register(PidController)
