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
from enum import IntEnum, unique  # We use IntEnum, because those can be easily serialized using the standard CBOR converter


@unique
class FunctionID(IntEnum):
    SET_INPUT = 0
    SET_KP = 1
    SET_KI = 2
    SET_KD = 3
    SET_LOWER_OUTPUT_LIMIT = 4
    SET_UPPER_OUTPUT_LIMIT = 5
    SET_ENABLED = 6
    SET_TIMEOUT = 7
    SET_DIRECTION = 8
    SET_SETPOINT = 9
    SET_OUTPUT = 10
    GET_SOFTWARE_VERSION = 11
    GET_SERIAL_NUMBER = 12
    SET_SERIAL_NUMBER = 16
    GET_DEVICE_TYPE = 13
    SET_GAIN = 14
    GET_BOARD_TEMPERATURE = 15
    GET_HARDWARE_VERSION = 17
    GET_HUMIDITY = 18
    GET_CALIBRATION_OFFSET = 19
    SET_CALIBRATION_OFFSET = 20
    RESET_SETTINGS = 21

    CALLBACK_UPDATE_VALUE = 22

    REQUEST_ID = 23
    GET_MAC_ADDRESS = 24
    SET_MAC_ADDRESS = 25
    GET_AUTO_RESUME = 26
    SET_AUTO_RESUME = 27

    RESET           = 30
    GET_API_VERSION = 31
    IS_PARTIAL_MESSAGE = 32


@unique
class ErrorCode(IntEnum):
    ACK = 249
    VALUE_ERROR = 250
    INVALID_FORMAT = 251
    INVALID_COMMAND = 252
    NOT_INITIALIZED = 253
    NOT_IMPLEMENTED = 254
    DEPRECATED = 255


@unique
class DeviceIdentifier(IntEnum):
    PID = 0
