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
import asyncio
from collections import namedtuple
from enum import Enum, IntEnum, unique
import time

@unique
class FunctionID(IntEnum):
    set_input = 0,
    set_kp = 1,
    set_ki = 2,
    set_kd = 3,
    set_lower_output_limit = 4,
    set_upper_output_limit = 5,
    set_enabled = 6,
    set_timeout = 7,
    set_direction = 8,
    set_setpoint = 9,
    set_output = 10,
    get_software_version = 11,
    get_serial_number = 12,
    set_serial_number = 16,
    get_device_type = 13,
    set_gain = 14,
    get_board_temperature = 15,
    get_hardware_version = 17,
    get_humidity = 18,
    get_calibration_offset = 19,
    set_calibration_offset = 20,
    reset_settings = 21,

    callback_update_value = 22,

    request_id = 23,
    get_mac_address = 24,
    set_mac_address = 25,
    get_auto_resume = 26,
    set_auto_resume = 27,

    reset           = 30,
    get_api_version = 31,
    is_partial_message = 32,

@unique
class ErrorCode(IntEnum):
    ack = 249,
    valueError = 250,
    invalidFormat = 251,
    invalidCommand = 252,
    notInitialized = 253,
    notImplemented = 254,
    deprecated = 255,

class DeviceIdentifier(IntEnum):
    PID = 0

