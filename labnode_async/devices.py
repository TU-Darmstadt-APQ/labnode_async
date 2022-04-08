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
from enum import IntEnum, unique  # We use IntEnum, because those can be easily serialized using the standard CBOR converter


@unique
class FunctionID(IntEnum):
    REQUEST_ID = 0
    SET_INPUT = 1
    SET_KP = 2
    SET_KI = 3
    SET_KD = 4
    SET_LOWER_OUTPUT_LIMIT = 5
    SET_UPPER_OUTPUT_LIMIT = 6
    SET_ENABLED = 7
    SET_TIMEOUT = 8
    SET_DIRECTION = 9
    SET_SETPOINT = 10
    SET_OUTPUT = 11
    SET_SERIAL_NUMBER = 12
    SET_GAIN = 13
    SET_SECONDARY_SETPOINT = 14
    SET_MAC_ADDRESS = 15
    SET_AUTO_RESUME = 16
    SET_FALLBACK_UPDATE_INTERVAL = 17
    SET_SECONDARY_KP = 18
    SET_SECONDARY_KI = 19
    SET_SECONDARY_KD = 20
    SET_SECONDARY_PID_PARAMETER_SET = 21
    RESET = 30
    RESET_SETTINGS = 31

    GET_INPUT = -1
    GET_KP = -2
    GET_KI = -3
    GET_KD = -4
    GET_LOWER_OUTPUT_LIMIT = -5
    GET_UPPER_OUTPUT_LIMIT = -6
    GET_ENABLED = -7
    GET_TIMEOUT = -8
    GET_DIRECTION = -9
    GET_SETPOINT = -10
    GET_OUTPUT = -11
    GET_SERIAL_NUMBER = -12
    GET_GAIN = -13
    GET_SECONDARY_SETPOINT = -14
    GET_MAC_ADDRESS = -15
    GET_AUTO_RESUME = -16
    GET_FALLBACK_UPDATE_INTERVAL = -17
    GET_SECONDARY_KP = -18
    GET_SECONDARY_KI = -19
    GET_SECONDARY_KD = -20
    GET_SECONDARY_PID_PARAMETER_SET = -21
    GET_BOARD_TEMPERATURE = -25
    GET_HUMIDITY = -26
    CALLBACK_UPDATE_VALUE = -27
    GET_ACTIVE_CONNECTION_COUNT = -28
    GET_DEVICE_TYPE = -29
    GET_SOFTWARE_VERSION = -30
    GET_HARDWARE_VERSION = -31
    GET_API_VERSION = -32

    INVALID_FORMAT = 251

@unique
class ErrorCode(IntEnum):
    INVALID_PARAMETER_TYPE = 248
    ACK = 249
    INVALID_MODE = 250
    INVALID_COMMAND = 252
    NOT_INITIALIZED = 253
    NOT_IMPLEMENTED = 254
    DEPRECATED = 255


@unique
class DeviceIdentifier(IntEnum):
    PID = 0
