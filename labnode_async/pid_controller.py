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

from decimal import Decimal
from enum import Enum, unique
import logging
import warnings
from typing import Any, Optional, Union, TYPE_CHECKING

from .devices import DeviceIdentifier, ErrorCode, PidFunctionID
from .errors import FunctionNotImplementedError, InvalidCommandError, InvalidFormatError, InvalidModeError, \
    InvalidReplyError, NotInitializedError
from .labnode import Labnode

if TYPE_CHECKING:
    from .ip_connection import IPConnection


@unique
class FeedbackDirection(Enum):
    NEGATIVE = False
    POSITIVE = True


class PidController(Labnode):  # pylint: disable=too-many-public-methods
    """
    A Labnode PID controller. This is the API to configure and control the Labnode.
    """
    __DEVICE_IDENTIFIER = DeviceIdentifier.PID

    @classmethod
    @property
    def device_identifier(cls) -> DeviceIdentifier:
        """

        Returns
        -------
        DeviceIdentifier
            The device identifier used to identify the device type
        """
        return cls.__DEVICE_IDENTIFIER

    RAW_TO_UNIT = {
        # The datasheet is *wrong* about the conversion formula. Slightly wrong
        # but wrong non the less. They are "off by 1" with the conversion of the
        # 16 bit result. They divide by 2**16 but should divide by (2**16 - 1)
        # Return Kelvin
        PidFunctionID.GET_BOARD_TEMPERATURE:
            lambda x: (Decimal("175.72") * x / (2**16 - 1) + Decimal("226.3")).quantize(Decimal("1.00")),
        # We need to truncate to 100 %rH according to the datasheet
        # The datasheet is *wrong* about the conversion formula. Slightly wrong
        # but wrong non the less. They are "off by 1" with the conversion of the
        # 16 bit result. They divide by 2**16 but should divide by (2**16 - 1)
        # Return %rH (above liquid water water), rH values below 0°C need to be compensated.
        PidFunctionID.GET_HUMIDITY:
            lambda x: (max(min(125 * Decimal(x) / (2**16 - 1) - 6, 100), 0)).quantize(Decimal("1.00")),
        PidFunctionID.GET_MAC_ADDRESS: bytearray,
    }

    RAW_TO_UNIT_11 = {
        PidFunctionID.GET_BOARD_TEMPERATURE: lambda x: (Decimal(x) + Decimal("273.15")).quantize(Decimal("1.00")),
        PidFunctionID.GET_HUMIDITY: lambda x: Decimal(x).quantize(Decimal("1.00")),
        PidFunctionID.GET_MAC_ADDRESS: bytearray,
    }

    def __init__(self, connection: IPConnection, api_version: tuple[int, int, int]) -> None:
        super().__init__(connection, api_version)
        self.__RAW_TO_UNIT = PidController.RAW_TO_UNIT_11 if api_version >= (0, 11, 0) else PidController.RAW_TO_UNIT
        self.__logger = logging.getLogger(__name__)

    @staticmethod
    def __test_for_errors(result: dict, key: int) -> None:
        """

        Parameters
        ----------
        result: dict
            A dict containing key value pairs of PidFunctionIDs and the results as returned by the device
        key
            The key to be tested for errors

        Raises
        -------
        TypeError
            If the key is not found in the dict, we will raise a TypeError

        """
        if key > 0:
            # We have a setter
            status = ErrorCode(result[key])
            if status is ErrorCode.INVALID_MODE:
                raise InvalidModeError(
                    "The controller is set to the wrong mode. Disable it to set the output, enable it to set the input"
                )
            if status is ErrorCode.INVALID_COMMAND:
                raise TypeError(f"The command '{key}' is invalid")
            if status is ErrorCode.INVALID_PARAMETER_TYPE:
                raise ValueError(f"Invalid value for request {key}")
            if status is ErrorCode.NOT_INITIALIZED:
                raise NotInitializedError(
                    "PID controller not initialized, Make sure kp, ki, kd and the setpoint is set"
                )
            if status is ErrorCode.NOT_IMPLEMENTED:
                raise FunctionNotImplementedError(f"The function {key} is not implemented")
            if status is ErrorCode.DEPRECATED:
                warnings.warn(f"The function {key} is deprecated", DeprecationWarning)

        # If the controller cannot parse the packet, it will answer with an INVALID_FORMAT error
        # and throw away the input, so we do not get a reply to our request.
        if PidFunctionID.INVALID_FORMAT in result:
            raise InvalidFormatError("Invalid data format. Check the datatype")
        if key not in result:
            # This can only happen, if another process is using the same sequence_number
            raise InvalidReplyError(
                f"Invalid reply received for request id {key}. Is someone using the same socket? Data: {result}"
            )

    async def __send_single_request(self, key: int, value: Optional[Any] = None) -> Any:
        result = await self.send_multi_request(
            data={key: value, }
        )
        self.__test_for_errors(result, key)

        if key > 0:
            return ErrorCode(result[key])

        return result[key]

    async def send_multi_request(self, data: dict[Union[PidFunctionID, int], Any]) -> dict:
        if self.api_version < (0, 11, 0):
            # We need to rewrite some function ids
            if PidFunctionID.GET_HUMIDITY in data:
                data[-21] = data[PidFunctionID.GET_HUMIDITY]
                del data[PidFunctionID.GET_HUMIDITY]
            if PidFunctionID.GET_BOARD_TEMPERATURE in data:
                data[-20] = data[PidFunctionID.GET_BOARD_TEMPERATURE]
                del data[PidFunctionID.GET_BOARD_TEMPERATURE]

        result = await self.connection.send_request(
            data=data,
            response_expected=True
        )

        if self.api_version < (0, 11, 0):
            # We need to rewrite some function ids
            if -21 in result:
                result[PidFunctionID.GET_HUMIDITY.value] = result[-21]
                del result[-21]
            if -20 in result:
                result[PidFunctionID.GET_BOARD_TEMPERATURE.value] = result[-20]
                del result[-20]

        try:
            result = {PidFunctionID(key): value for key, value in result.items()}
        except ValueError:
            # Raised by PidFunctionID(key)
            self.__logger.error("Received unknown function id in data: %(data)s", {'data': data})
            return result
        return result

    async def get_software_version(self) -> tuple[int, int, int]:
        """
        Returns The software version running on the device
        """
        return await self.get_by_function_id(PidFunctionID.GET_SOFTWARE_VERSION)

    async def get_hardware_version(self) -> tuple[int, int, int]:
        """
        Returns The hardware version of the device
        """
        return await self.get_by_function_id(PidFunctionID.GET_HARDWARE_VERSION)

    async def get_serial(self) -> int:
        """
        Returns The serial number of the device
        """
        return await self.get_by_function_id(PidFunctionID.GET_SERIAL_NUMBER)

    async def get_device_temperature(self) -> float:
        """
        Returns The temperature of the onboard sensor
        """
        return await self.get_by_function_id(PidFunctionID.GET_BOARD_TEMPERATURE)

    async def get_humidity(self) -> float:
        """
        Returns The humidity as read by the onboard sensor
        """
        return await self.get_by_function_id(PidFunctionID.GET_HUMIDITY)

    async def get_mac_address(self) -> bytearray:
        """
        Returns The MAC address used by the ethernet port
        """
        return await self.get_by_function_id(PidFunctionID.GET_MAC_ADDRESS)

    async def set_mac_address(self, mac: Union[tuple[int, int, int, int, int, int], list[int], bytearray]) -> None:
        """
        Set the MAC address used by the ethernet port
        """
        assert len(mac) == 6
        mac = tuple(mac)  # convert bytearray if it is one
        await self.__send_single_request(PidFunctionID.SET_MAC_ADDRESS, mac)

    async def get_auto_resume(self) -> bool:
        """
        Returns The MAC address used by the ethernet port
        """
        return await self.get_by_function_id(PidFunctionID.GET_AUTO_RESUME)

    async def set_auto_resume(self, value: bool):
        """
        Set the controller to automatically load the previous settings and resume its action
        """
        await self.__send_single_request(PidFunctionID.SET_AUTO_RESUME, bool(value))

    async def set_lower_output_limit(self, limit: int) -> None:
        """
        Set the minimum allowed output of the DAC in bit values
        """
        try:
            await self.__send_single_request(PidFunctionID.SET_LOWER_OUTPUT_LIMIT, limit)
        except InvalidFormatError:
            raise ValueError("Invalid limit") from None

    async def get_lower_output_limit(self) -> int:
        """
        Get the minimum allowed output of the DAC in bit values
        """
        return await self.get_by_function_id(PidFunctionID.GET_LOWER_OUTPUT_LIMIT)

    async def set_upper_output_limit(self, limit: int) -> None:
        """
        Set the maximum allowed output of the DAC in bit values
        """
        try:
            await self.__send_single_request(PidFunctionID.SET_UPPER_OUTPUT_LIMIT, limit)
        except InvalidFormatError:
            raise ValueError("Invalid limit") from None

    async def get_upper_output_limit(self) -> int:
        """
        Get the minimum allowed output of the DAC in bit values
        """
        return await self.get_by_function_id(PidFunctionID.GET_UPPER_OUTPUT_LIMIT)

    async def set_timeout(self, timeout: int) -> None:
        """
        Set the timeout, that defines when the controller switched to fallback mode. The time is in ms
        """
        assert timeout > 0
        await self.__send_single_request(PidFunctionID.SET_TIMEOUT, int(timeout))

    async def get_timeout(self) -> int:
        return await self.get_by_function_id(PidFunctionID.GET_TIMEOUT)

    async def set_dac_gain(self, enable: bool) -> None:
        """
        Set the gain of the DAC to x2. This will increase the output voltage range from 0..5V to 0..10V.
        """
        await self.__send_single_request(PidFunctionID.SET_GAIN, bool(enable))

    async def is_dac_gain_enabled(self) -> bool:
        return await self.get_by_function_id(PidFunctionID.GET_GAIN)

    async def set_pid_feedback_direction(self, feedback: FeedbackDirection) -> None:
        """
        Set the sign of the pid output. This needs to be adjusted according to the actuator used to
        control the plant. Typically, it is assumed, that the feedback is negative. For example, when
        dealing with e.g. temperature control, this means, that if the temperature is too high,
        an increase in the feedback will increase the cooling action.
        In short: If set to `FeedbackDirection.NEGATIVE`, a positive error will result in a negative plant response.
        """
        feedback = FeedbackDirection(feedback)
        await self.__send_single_request(PidFunctionID.SET_DIRECTION, feedback.value)

    async def get_pid_feedback_direction(self) -> FeedbackDirection:
        return FeedbackDirection(await self.get_by_function_id(PidFunctionID.GET_DIRECTION))

    async def set_output(self, value: int) -> None:
        await self.__send_single_request(PidFunctionID.SET_OUTPUT, int(value))

    async def get_output(self) -> int:
        return await self.get_by_function_id(PidFunctionID.GET_OUTPUT)

    async def set_enabled(self, enabled: bool) -> None:
        await self.__send_single_request(PidFunctionID.SET_ENABLED, bool(enabled))

    async def is_enabled(self) -> bool:
        return await self.get_by_function_id(PidFunctionID.GET_ENABLED)

    async def __set_kx(self, function_id: PidFunctionID, kx: int) -> None:
        """
        Set the PID K{p,i,d} parameter. The Kp, Ki, Kd parameters are stored in Q16.16 format
        """
        if self.api_version < (0, 11, 0) and function_id in \
                (PidFunctionID.SET_SECONDARY_KP, PidFunctionID.SET_SECONDARY_KI, PidFunctionID.SET_SECONDARY_KD):
            raise FunctionNotImplementedError(f"{function_id.name} is only supported in api version >= 0.11.0")
        try:
            await self.__send_single_request(function_id, int(kx))
        except InvalidFormatError:
            raise ValueError("Invalid PID constant") from None

    async def set_kp(self, kp: int, config_id: int = 0) -> None:  # pylint: disable=invalid-name
        """
        Set the PID Kp parameter. The Kp, Ki, Kd parameters are stored in Q16.16 format

        Parameters
        ----------
        kp: int
            The PID k_p parameter in Q16.16 format
        config_id: {0, 1}
            The id of the parameter set. The controller supports two pid parameter sets.
            Either 0 or 1.
        """
        assert config_id in (0, 1)
        if config_id == 0:
            await self.__set_kx(PidFunctionID.SET_KP, kp)
        else:
            await self.__set_kx(PidFunctionID.SET_SECONDARY_KP, kp)

    async def get_kp(self, config_id: int = 0) -> int:
        """
        Get the PID Kp parameter. The Kp, Ki, Kd parameters are stored in Q16.16 format

        Parameters
        ----------
        config_id: {0, 1}
            The id of the parameter set. The controller supports two pid parameter sets.
            Either 0 or 1.
        """
        assert config_id in (0, 1)
        if config_id == 0:
            return await self.get_by_function_id(PidFunctionID.GET_KP)

        if self.api_version >= (0, 11, 0):
            return await self.get_by_function_id(PidFunctionID.GET_SECONDARY_KP)

        raise FunctionNotImplementedError(
            f"{PidFunctionID.GET_SECONDARY_KP.name} is only supported in api version >= 0.11.0"
        )

    async def set_ki(self, ki: int, config_id: int = 0) -> None:  # pylint: disable=invalid-name
        """
        Set the PID Ki parameter. The Kp, Ki, Kd parameters are stored in Q16.16 format
        """
        assert config_id in (0, 1)
        if config_id == 0:
            await self.__set_kx(PidFunctionID.SET_KI, ki)
        else:
            await self.__set_kx(PidFunctionID.SET_SECONDARY_KI, ki)

    async def get_ki(self, config_id: int = 0) -> int:
        """
        Get the PID Ki parameter. The Kp, Ki, Kd parameters are stored in Q16.16 format
        """
        assert config_id in (0, 1)
        if config_id == 0:
            return await self.get_by_function_id(PidFunctionID.GET_KI)

        if self.api_version >= (0, 11, 0):
            return await self.get_by_function_id(PidFunctionID.GET_SECONDARY_KI)

        raise FunctionNotImplementedError(
            f"{PidFunctionID.GET_SECONDARY_KI.name} is only supported in api version >= 0.11.0"
        )

    async def set_kd(self, kd: int, config_id: int = 0) -> None:  # pylint: disable=invalid-name
        """
        Set the PID Kd parameter. The Kp, Ki, Kd parameters are stored in Q16.16 format
        """
        assert config_id in (0, 1)
        if config_id == 0:
            await self.__set_kx(PidFunctionID.SET_KD, kd)
        else:
            await self.__set_kx(PidFunctionID.SET_SECONDARY_KD, kd)

    async def get_kd(self, config_id: int = 0) -> int:
        """
        Get the PID Kd parameter. The Kp, Ki, Kd parameters are stored in Q16.16 format
        """
        assert config_id in (0, 1)
        if config_id == 0:
            return await self.get_by_function_id(PidFunctionID.GET_KD)

        if self.api_version >= (0, 11, 0):
            return await self.get_by_function_id(PidFunctionID.GET_SECONDARY_KD)

        raise FunctionNotImplementedError(
            f"{PidFunctionID.GET_SECONDARY_KD.name} is only supported in api version >= 0.11.0"
        )

    async def set_input(self, value: int, return_output: bool = False) -> None:
        """
        Set the input, which is fed to the PID controller. The value is in Q16.16 format
        Returns The new output
        """
        # We need to send a multi_request, because if return_output is True, we want to get the
        # output after the input has been set
        request = {PidFunctionID.SET_INPUT: int(value)}
        if return_output:
            request[PidFunctionID.GET_OUTPUT] = None
        result = await self.send_multi_request(request)

        # We need to test for errors, which would normally be done by __send_single_request()
        self.__test_for_errors(result, PidFunctionID.SET_INPUT)
        if return_output:
            return result[PidFunctionID.GET_OUTPUT]

    async def set_setpoint(self, value: int, config_id: int = 0) -> None:
        """
        Set the PID setpoint. The value is in Q16.16 format
        """
        assert config_id in (0, 1)
        try:
            if config_id == 0:
                await self.__send_single_request(PidFunctionID.SET_SETPOINT, int(value))
            else:
                if self.api_version >= (0, 11, 0):
                    await self.__send_single_request(PidFunctionID.SET_SECONDARY_SETPOINT, int(value))
                else:
                    raise FunctionNotImplementedError(
                        f"{PidFunctionID.SET_SECONDARY_SETPOINT.name} is only supported in api version >= 0.11.0"
                    )
        except InvalidFormatError:
            raise ValueError("Invalid setpoint") from None

    async def get_setpoint(self, config_id: int = 0) -> int:
        """
        Get the PID setpoint. The value is in Q16.16 format
        """
        assert config_id in (0, 1)
        if config_id == 0:
            return await self.get_by_function_id(PidFunctionID.GET_SETPOINT)

        if self.api_version >= (0, 11, 0):
            return await self.get_by_function_id(PidFunctionID.GET_SECONDARY_SETPOINT)

        raise FunctionNotImplementedError(
            f"{PidFunctionID.GET_SECONDARY_SETPOINT.name} is only supported in api version >= 0.11.0"
        )

    async def set_secondary_config(self, config_id: int) -> None:
        """
        Set the offset added to the internal temperature sensor, when running in fallback mode. The value is
        a floating point number in units of K
        """
        assert config_id in (0, 1)
        try:
            await self.__send_single_request(PidFunctionID.SET_SECONDARY_PID_PARAMETER_SET, int(config_id))
        except InvalidFormatError:
            raise ValueError("Invalid configuration set. Use either 0 or 1.") from None

    async def get_secondary_config(self) -> int:
        """
        Returns The offset, which is subtracted from the internal temperature sensor when running in fallback mode. The
        return value is in units of K
        """
        return await self.get_by_function_id(PidFunctionID.GET_SECONDARY_PID_PARAMETER_SET)

    async def set_fallback_update_interval(self, value: int):
        """
        Set the update interval, when running in fallback mode. This value should be same as, when
        not running in fallback mode, to keep the PID constants the same. The value is
        an integer in ms
        """
        assert value > 0
        try:
            await self.__send_single_request(PidFunctionID.SET_FALLBACK_UPDATE_INTERVAL, int(value))
        except InvalidFormatError:
            raise ValueError("Invalid calibration offset") from None

    async def get_fallback_update_interval(self) -> int:
        """
        Returns The update interval, which is used when running in fallback mode. The
        return value is in units of K
        """
        return await self.get_by_function_id(PidFunctionID.GET_FALLBACK_UPDATE_INTERVAL)

    async def reset(self) -> None:
        """
        Resets the device. This will trigger a hardware reset
        """
        await self.__send_single_request(PidFunctionID.RESET)

    async def reset_settings(self) -> None:
        """
        Resets the device to default values.
        """
        await self.__send_single_request(PidFunctionID.RESET_SETTINGS)

    async def set_serial(self, serial: int) -> None:
        try:
            await self.__send_single_request(PidFunctionID.SET_SERIAL_NUMBER, int(serial))
        except InvalidFormatError:
            raise ValueError("Invalid serial number") from None

    async def get_active_connection_count(self) -> int:
        return await self.get_by_function_id(PidFunctionID.GET_ACTIVE_CONNECTION_COUNT)

    async def get_by_function_id(self, function_id: PidFunctionID) -> Any:
        try:
            function_id = PidFunctionID(function_id)
        except ValueError:
            raise InvalidCommandError(f"Command {function_id} is invalid.") from None
        assert function_id.value < 0    # all getter have negative ids

        result = await self.__send_single_request(function_id)

        if function_id in self.__RAW_TO_UNIT:
            result = self.__RAW_TO_UNIT[function_id](result)

        return result
