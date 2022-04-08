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
from typing import Tuple


class Labnode:
    @property
    def api_version(self) -> Tuple:
        """
        Returns The API version used by the device to communicate
        """
        return self.__api_version

    @property
    def ipcon(self) -> 'IPConnection':
        """
        Returns The ip connection used by the device
        """
        return self.__ipcon

    def __init__(self, ipcon: 'IPConnection', api_version: Tuple) -> None:
        self.__api_version = api_version
        self.__ipcon = ipcon
