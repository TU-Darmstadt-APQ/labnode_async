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
from collections import namedtuple
from decimal import Decimal
from enum import Enum, IntEnum, unique
import logging

from .devices import FunctionID, ErrorCode

@unique
class FeedbackDirection(IntEnum):
    negative = 0,
    positive = 1,

class PID_Controller(object):
    """
    A simple remote PID controller
    """

    def __init__(self, ipcon):
        """
        Creates an object with the unique device ID *uid* and adds it to
        the IP Connection *ipcon*.
        """
        self.__ipcon = ipcon
        self.__logger = logging.getLogger(__name__)

    async def __send_single_request(self, key, value=None):
      result = await self.__ipcon.send_request(
              data={
                  key: value,
              },
              response_expected=True
          )
      try:
          return result[key]
      except KeyError:
          # This can happen, if another process is using the same sequence_number
          self.__logger.error("Invalid reply received. Wrong reply for request id %(request_id)s. Is someone using the same id? data: %(data)s", {'request_id': key, 'data': result})

    async def __send_multi_request(self, data):
      return await self.__ipcon.send_request(
            data=data,
            response_expected=True
        )

    async def get_software_version(self):
        """
        Returns The software version running on the device
        """
        return await self.__send_single_request(FunctionID.get_software_version)

    async def get_hardware_version(self):
        """
        Returns The hardware version of the device
        """
        return await self.__send_single_request(FunctionID.get_hardware_version)

    async def get_api_version(self):
        """
        Returns The API version used by the device to communicate
        """
        return await self.__send_single_request(FunctionID.get_api_version)

    async def get_serial(self):
        """
        Returns The serial number of the device
        """
        return await self.__send_single_request(FunctionID.get_serial_number)


    async def get_device_temperature(self):
        """
        Returns The temperature of the onboard sensor
        """
        # The datasheet is *wrong* about the conversion formula. Slightly wrong
        # but wrong non the less. They are "off by 1" with the conversion of the
        # 16 bit result. They divide by 2**16 but should divide by (2**16 - 1)
        result = await self.__send_single_request(FunctionID.get_board_temperature)
        return 175.72 * result / (2**16 - 1) - 46.85

    async def get_humidity(self):
        """
        Returns The humidity as read by the onboard sensor
        """
        result = await self.__send_single_request(FunctionID.get_humidity)
        # We need to truncate to 100 %rH according to the datasheet
        # The datasheet is *wrong* about the conversion formula. Slightly wrong
        # but wrong non the less. They are "off by 1" with the conversion of the
        # 16 bit result. They divide by 2**16 but should divide by (2**16 - 1)
        return min(125 * result / (2**16 - 1) - 6, 100)

    async def get_mac_address(self):
        """
        Returns The MAC address used by the ethernet port
        """
        result = await self.__send_single_request(FunctionID.get_mac_address)
        return bytearray(result)

    async def set_mac_address(self, mac):
        """
        Set the MAC address used by the ethernet port
        """
        result = ErrorCode(await self.__send_single_request(FunctionID.set_mac_address, mac))
        if result == ErrorCode.valueError:
          raise ValueError("Invalid MAC address")

    async def get_auto_resume(self):
        """
        Returns The MAC address used by the ethernet port
        """
        return await self.__send_single_request(FunctionID.get_auto_resume)

    async def get_calibration_offset(self):
        """
        Returns The offset, which is subtracted from the internal temperature sensor when running in fallback mode. The
        return value is in units of K
        """
        return await self.__send_single_request(FunctionID.get_calibration_offset)

    async def set_auto_resume(self, value):
        """
        Set the controller to autmatically load the previous settings and resume its action
        """
        result = ErrorCode(await self.__send_single_request(FunctionID.set_auto_resume, bool(value)))
        if result == ErrorCode.valueError:
            raise ValueError()

    async def set_lower_output_limit(self, limit):
        """
        Set the minium allowed output of the DAC in bit values
        """
        result = ErrorCode(await self.__send_single_request(FunctionID.set_lower_output_limit, limit))
        if result == ErrorCode.valueError:
            raise ValueError("Invalid limit")

    async def set_upper_output_limit(self, limit):
        """
        Set the maximum allowed output of the DAC in bit values
        """
        result = ErrorCode(await self.__send_single_request(FunctionID.set_upper_output_limit, limit))
        if result == ErrorCode.valueError:
            raise ValueError("Invalid limit")

    async def set_timeout(self, timeout):
        """
        Set the timeout, that defines when the controller switched to fallback mode. The time is in ms
        """
        result = ErrorCode(await self.__send_single_request(FunctionID.set_timeout, int(timeout)))
        if result == ErrorCode.valueError:
          raise ValueError()    # TODO: There is no error yet

    async def set_dac_gain(self, enable):
        """
        Set the gain of the DAC to x2. This will increase the output voltage range from 0..5V to 0..10V.
        """
        result = ErrorCode(await self.__send_single_request(FunctionID.set_gain, bool(enable)))
        if result == ErrorCode.valueError:
            raise ValueError()    # TODO: There is no error yet

    async def set_pid_feedback_direction(self, feedback):
        """
        Set the sign of the pid output. This needs to be adjusted according to the actuator used to
        control the plant. Typically it is assumed, that the feedback is negative. For example, when
        dealing with e.g. tempeature control, this means, that if the temperature is too high,
        an increase in the feedback will increase the cooling action.
        In short: If set to FeedbackDirection.negative, a positive error will result in a negative plant response.
        """
        result = ErrorCode(await self.__send_single_request(FunctionID.set_direction, bool(feedback)))
        if result == ErrorCode.valueError:
            raise ValueError()    # TODO: There is no error yet

    async def set_output(self, value):
        """
        Set the sign of the pid output. This needs to be adjusted according to the actuator used to
        control the plant. Typically it is assumed, that the feedback is negative. For example, when
        dealing with e.g. tempeature control, this means, that, using negative feedback, if the temperature
        is too high an increase in the feedback will increase the cooling action.
        In short: If set to FeedbackDirection.negative, a positive error will result in a negative plant response.
        """
        result = ErrorCode(await self.__send_single_request(FunctionID.set_output, int(value)))
        if result == ErrorCode.valueError:
            raise ValueError()    # TODO: There is no error yet

    async def set_enabled(self, enabled):
        """
        Set the sign of the pid output. This needs to be adjusted according to the actuator used to
        control the plant. Typically it is assumed, that the feedback is negative. For example, when
        dealing with e.g. tempeature control, this means, that, using negative feedback, if the temperature
        is too high an increase in the feedback will increase the cooling action.
        In short: If set to FeedbackDirection.negative, a positive error will result in a negative plant response.
        """
        result = ErrorCode(await self.__send_single_request(FunctionID.set_enabled, bool(enabled)))
        if result == ErrorCode.valueError:
            raise ValueError()    # TODO: There is no error yet

    async def set_kp(self, kp):
        """
        Set the PID Kp parameter. The Kp, Ki, Kd parameters are stored in Q16.16 format
        """
        result = ErrorCode(await self.__send_single_request(FunctionID.set_kp, int(kp)))
        if result == ErrorCode.valueError:
          raise ValueError()

    async def set_ki(self, ki):
        """
        Set the PID Ki parameter. The Kp, Ki, Kd parameters are stored in Q16.16 format
        """
        result = ErrorCode(await self.__send_single_request(FunctionID.set_ki, int(ki)))
        if result == ErrorCode.valueError:
            raise ValueError()

    async def set_kd(self, kd):
        """
        Set the PID Kd parameter. The Kp, Ki, Kd parameters are stored in Q16.16 format
        """
        result = ErrorCode(await self.__send_single_request(FunctionID.set_kd, int(kd)))
        if result == ErrorCode.valueError:
            raise ValueError()

    async def set_input(self, value):
        """
        Set the input, which is fed to the PID controller. The value is in Q16.16 format
        Returns The new outpout
        """
        # We need to send a multi_request, because set input will return an ACK and a return value
        result = await __send_multi_request({FunctionID.set_input: int(value)})
        error_code = ErrorCode(result[FunctionID.set_input])
        if error_code == ErrorCode.valueError:
            raise ValueError()

        return result[FunctionID.callback_update_value]

    async def set_setpoint(self, value):
        """
        Set the PID setpoint. The value is in Q16.16 format
        """
        result = ErrorCode(await self.__send_single_request(FunctionID.set_setpoint, int(value)))
        if result == ErrorCode.valueError:
            raise ValueError("Invalid setpoint")

    async def set_calibration_offset(self):
        """
        Set the offset subtracted from the internal temperature sensor, when running in fallback mode. The value is
        a floating point number in units of K
        """
        result = ErrorCode(await self.__send_single_request(FunctionID.set_calibration_offset, float(value)))
        if result == ErrorCode.valueError:
            raise ValueError("Invalid calibration offset")

    async def reset(self):
        """
        Resets the device. This will trigger a hardware reset
        """
        await self.__send_single_request(FunctionID.reset)

    async def reset_settings(self):
        """
        Resets the device to default values.
        """
        await self.__send_single_request(FunctionID.reset_settings)

    async def set_serial(self, serial):
        """
       
        """
        result = ErrorCode(await self.__send_single_request(FunctionID.set_serial_number, int(serial)))
        if result == ErrorCode.valueError:
            raise ValueError("Invalid serial number")

    
