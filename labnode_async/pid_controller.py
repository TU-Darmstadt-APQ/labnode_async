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
from enum import Enum, unique
import logging
import warnings

from .devices import DeviceIdentifier, ErrorCode, FunctionID
from .errors import NotInitializedError, InvalidReplyError, InvalidFormatError, InvalidModeError


@unique
class FeedbackDirection(Enum):
    NEGATIVE = False
    POSITIVE = True


class PidController:  # pylint: disable=too-many-public-methods
    """
    A simple remote PID controller
    """
    DEVICE_IDENTIFIER = DeviceIdentifier.PID

    RAW_TO_UNIT = {
        # The datasheet is *wrong* about the conversion formula. Slightly wrong
        # but wrong non the less. They are "off by 1" with the conversion of the
        # 16 bit result. They divide by 2**16 but should divide by (2**16 - 1)
        FunctionID.GET_BOARD_TEMPERATURE: lambda x: 175.72 * x / 2**16 - 1 - 46.85,
        # We need to truncate to 100 %rH according to the datasheet
        # The datasheet is *wrong* about the conversion formula. Slightly wrong
        # but wrong non the less. They are "off by 1" with the conversion of the
        # 16 bit result. They divide by 2**16 but should divide by (2**16 - 1)
        FunctionID.GET_HUMIDITY: lambda x: 175.72 * x / 2**16 - 1 - 46.85
    }

    def __init__(self, ipcon):
        self.__ipcon = ipcon
        self.__logger = logging.getLogger(__name__)

    @staticmethod
    def __test_for_errors(result, key):
        if key > 0:
            # We have a setter
            status = ErrorCode(result[key])
            if status is ErrorCode.INVALID_MODE:
                raise InvalidModeError("The controller is set to the wrong mode. Disable it to set the outpout, enable it to set the input")
            elif status is ErrorCode.INVALID_COMMAND:
                raise InvalidCommandError(f"The command {key} is invalid")
            elif status is ErrorCode.INVALID_PARAMETER_TYPE:
                raise ValueError(f"Invalid value for request {key}")
            elif status is ErrorCode.NOT_INITIALIZED:
                raise NotInitializedError("PID controller not initialized, Make sure kp, ki, kd and the setpoint is set")
            elif status is ErrorCode.NOT_IMPLEMENTED:
                raise FunctionNotImplementedError(f"The function {key} is not implemented")
            elif status is ErrorCode.DEPRECATED:
                warnings.warn(f"The function {key} is deprecated", DeprecationWarning)

        # If the controller cannot parse the packet, it will answer with an INVALID_FORMAT error
        # and throw away the input, so we do not get a reply to our request.
        if FunctionID.INVALID_FORMAT in result:
            raise InvalidFormatError(f"Invalid data format. Check the datatype")
        if key not in result:
            # This can only happen, if another process is using the same sequence_number
            raise InvalidReplyError(f"Invalid reply received. Wrong reply for request id {key}. Is someone using the same socket? Data: {result}")

    async def __send_single_request(self, key, value=None):
        result = await self.send_multi_request(
            data={key: value,}
        )
        self.__test_for_errors(result, key)

        if result[key] < 0:
            return ErrorCode(result[key])
        else:
            return result[key]

    async def send_multi_request(self, data):
        return await self.__ipcon.send_request(
            data=data,
            response_expected=True
        )

    async def get_software_version(self):
        """
        Returns The software version running on the device
        """
        return await self.__send_single_request(FunctionID.GET_SOFTWARE_VERSION)

    async def get_hardware_version(self):
        """
        Returns The hardware version of the device
        """
        return await self.__send_single_request(FunctionID.GET_HARDWARE_VERSION)

    async def get_api_version(self):
        """
        Returns The API version used by the device to communicate
        """
        return await self.__send_single_request(FunctionID.GET_API_VERSION)

    async def get_serial(self):
        """
        Returns The serial number of the device
        """
        return await self.__send_single_request(FunctionID.GET_SERIAL_NUMBER)

    async def get_device_temperature(self):
        """
        Returns The temperature of the onboard sensor
        """
        result = await self.__send_single_request(FunctionID.GET_BOARD_TEMPERATURE)
        return PidController.RAW_TO_UNIT[FunctionID.GET_BOARD_TEMPERATURE](result)

    async def get_humidity(self):
        """
        Returns The humidity as read by the onboard sensor
        """
        result = await self.__send_single_request(FunctionID.GET_HUMIDITY)
        return PidController.RAW_TO_UNIT[FunctionID.GET_HUMIDITY](result)

    async def get_mac_address(self):
        """
        Returns The MAC address used by the ethernet port
        """
        result = await self.__send_single_request(FunctionID.GET_MAC_ADDRESS)
        return bytearray(result)

    async def set_mac_address(self, mac):
        """
        Set the MAC address used by the ethernet port
        """
        await self.__send_single_request(FunctionID.SET_MAC_ADDRESS, mac)

    async def get_auto_resume(self):
        """
        Returns The MAC address used by the ethernet port
        """
        return await self.__send_single_request(FunctionID.GET_AUTO_RESUME)

    async def get_calibration_offset(self):
        """
        Returns The offset, which is subtracted from the internal temperature sensor when running in fallback mode. The
        return value is in units of K
        """
        return await self.__send_single_request(FunctionID.GET_CALIBRATION_OFFSET)

    async def set_auto_resume(self, value):
        """
        Set the controller to autmatically load the previous settings and resume its action
        """
        await self.__send_single_request(FunctionID.SET_AUTO_RESUME, bool(value))

    async def set_lower_output_limit(self, limit):
        """
        Set the minium allowed output of the DAC in bit values
        """
        try:
            await self.__send_single_request(FunctionID.SET_LOWER_OUTPUT_LIMIT, limit)
        except InvalidFormatError:
            raise ValueError("Invalid limit")

    async def get_lower_output_limit(self):
        """
        Get the minium allowed output of the DAC in bit values
        """
        return await self.__send_single_request(FunctionID.GET_LOWER_OUTPUT_LIMIT)

    async def set_upper_output_limit(self, limit):
        """
        Set the maximum allowed output of the DAC in bit values
        """
        try:
            await self.__send_single_request(FunctionID.SET_UPPER_OUTPUT_LIMIT, limit)
        except InvalidFormatError:
            raise ValueError("Invalid limit")

    async def get_upper_output_limit(self):
        """
        Get the minium allowed output of the DAC in bit values
        """
        return await self.__send_single_request(FunctionID.GET_UPPER_OUTPUT_LIMIT)

    async def set_timeout(self, timeout):
        """
        Set the timeout, that defines when the controller switched to fallback mode. The time is in ms
        """
        await self.__send_single_request(FunctionID.SET_TIMEOUT, int(timeout))

    async def get_timeout(self):
        return await self.__send_single_request(FunctionID.GET_TIMEOUT)

    async def set_dac_gain(self, enable):
        """
        Set the gain of the DAC to x2. This will increase the output voltage range from 0..5V to 0..10V.
        """
        await self.__send_single_request(FunctionID.SET_GAIN, bool(enable))

    async def is_dac_gain_enabled(self):
        return await self.__send_single_request(FunctionID.GET_GAIN)

    async def set_pid_feedback_direction(self, feedback):
        """
        Set the sign of the pid output. This needs to be adjusted according to the actuator used to
        control the plant. Typically it is assumed, that the feedback is negative. For example, when
        dealing with e.g. tempeature control, this means, that if the temperature is too high,
        an increase in the feedback will increase the cooling action.
        In short: If set to FeedbackDirection.NEGATIVE, a positive error will result in a negative plant response.
        """
        feedback = FeedbackDirection(feedback)
        await self.__send_single_request(FunctionID.SET_DIRECTION, feedback.value)

    async def get_pid_feedback_direction(self):
        return FeedbackDirection(await self.__send_single_request(FunctionID.GET_DIRECTION))

    async def set_output(self, value):
        await self.__send_single_request(FunctionID.SET_OUTPUT, int(value))

    async def get_output(self):
        return await self.__send_single_request(FunctionID.GET_OUTPUT)

    async def set_enabled(self, enabled):
        await self.__send_single_request(FunctionID.SET_ENABLED, bool(enabled))

    async def is_enabled(self):
        return await self.__send_single_request(FunctionID.GET_ENABLED)

    async def set_kp(self, kp):  # pylint: disable=invalid-name
        """
        Set the PID Kp parameter. The Kp, Ki, Kd parameters are stored in Q16.16 format
        """
        try:
            await self.__send_single_request(FunctionID.SET_KP, int(kp))
        except InvalidFormatError:
            raise ValueError("Invalid PID constant") from None

    async def get_kp(self):
        """
        Get the PID Kp parameter. The Kp, Ki, Kd parameters are stored in Q16.16 format
        """
        return await self.__send_single_request(FunctionID.GET_KP)

    async def set_ki(self, ki):  # pylint: disable=invalid-name
        """
        Set the PID Ki parameter. The Kp, Ki, Kd parameters are stored in Q16.16 format
        """
        try:
            await self.__send_single_request(FunctionID.SET_KI, int(ki))
        except InvalidFormatError:
            raise ValueError("Invalid PID constant") from None

    async def get_ki(self):
        """
        Get the PID Ki parameter. The Kp, Ki, Kd parameters are stored in Q16.16 format
        """
        return await self.__send_single_request(FunctionID.GET_KI)

    async def set_kd(self, kd):  # pylint: disable=invalid-name
        """
        Set the PID Kd parameter. The Kp, Ki, Kd parameters are stored in Q16.16 format
        """
        try:
            result = ErrorCode(await self.__send_single_request(FunctionID.SET_KD, int(kd)))
        except InvalidFormatError:
            raise ValueError("Invalid PID constant") from None

    async def get_kd(self):
        """
        Get the PID Kd parameter. The Kp, Ki, Kd parameters are stored in Q16.16 format
        """
        return await self.__send_single_request(FunctionID.GET_KD)

    async def set_input(self, value, return_output=False):
        """
        Set the input, which is fed to the PID controller. The value is in Q16.16 format
        Returns The new outpout
        """
        # We need to send a multi_request, because if return_output is True, we want to get the
        # output after the input has been set
        request = {FunctionID.SET_INPUT: int(value)}
        if return_output:
            request[FunctionID.GET_OUTPUT] = None
        result = await self.send_multi_request(request)

        self.__test_for_errors(result, FunctionID.SET_INPUT)
        if return_output:
            return result[FunctionID.GET_OUTPUT]

    async def set_setpoint(self, value):
        """
        Set the PID setpoint. The value is in Q16.16 format
        """
        try:
            await self.__send_single_request(FunctionID.SET_SETPOINT, int(value))
        except InvalidFormatError:
            raise ValueError("Invalid setpoint") from None

    async def get_setpoint(self):
        """
        Get the PID setpoint. The value is in Q16.16 format
        """
        return await self.__send_single_request(FunctionID.GET_SETPOINT)

    async def set_calibration_offset(self, value):
        """
        Set the offset subtracted from the internal temperature sensor, when running in fallback mode. The value is
        a floating point number in units of K
        """
        try:
            await self.__send_single_request(FunctionID.SET_CALIBRATION_OFFSET, float(value))
        except InvalidFormatError:
            raise ValueError("Invalid calibration offset") from None

    async def reset(self):
        """
        Resets the device. This will trigger a hardware reset
        """
        await self.__send_single_request(FunctionID.RESET)

    async def reset_settings(self):
        """
        Resets the device to default values.
        """
        await self.__send_single_request(FunctionID.RESET_SETTINGS)

    async def set_serial(self, serial):
        try:
            await self.__send_single_request(FunctionID.SET_SERIAL_NUMBER, int(serial))
        except InvalidFormatError:
            raise ValueError("Invalid serial number") from None

    async def get_by_function_id(self, function_id):
        function_id = FunctionID(function_id)
        assert function_id.value < 0    # all getter have negative ids

        result = await self.__send_single_request(function_id)
        if function_id in PidController.RAW_TO_UNIT:
            result = PidController.RAW_TO_UNIT[function_id](result)
        return result
