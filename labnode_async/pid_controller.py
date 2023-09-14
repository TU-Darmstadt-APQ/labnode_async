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
"""The labnode PID controller driver"""
from __future__ import annotations

import logging
import warnings
from decimal import Decimal
from enum import Enum, unique
from typing import TYPE_CHECKING, Any, Callable
from uuid import UUID

from .devices import DeviceIdentifier, ErrorCode, PidFunctionID
from .errors import (
    FunctionNotImplementedError,
    InvalidCommandError,
    InvalidFormatError,
    InvalidModeError,
    InvalidReplyError,
    PidNotInitializedError,
)
from .labnode import Labnode

if TYPE_CHECKING:
    from .connection import Connection


@unique
class FeedbackDirection(Enum):
    """
    The sign of the feedback action of the PID controller. A positive direction means, that a positive disturbance
    causes a positive output from the PID. A negative direction causes feedback in the opposing direction. This is the
    default and should be selected for most systems.
    """

    NEGATIVE = False
    POSITIVE = True


class PidController(Labnode):  # pylint: disable=too-many-public-methods
    """
    A Labnode PID controller. This is the API to configure and control the Labnode.
    """

    __DEVICE_IDENTIFIER = DeviceIdentifier.PID

    @classmethod
    def device_identifier(cls) -> DeviceIdentifier:
        """The device identifier used to identify the device type"""
        return cls.__DEVICE_IDENTIFIER

    _RAW_TO_UNIT: dict[PidFunctionID, Callable] = {
        # We need to truncate to 100 %rH according to the datasheet.
        # The datasheet is *wrong* about the conversion formula. Slightly wrong, but wrong nonetheless.
        # They are "off by 1" with the conversion of the 16 bit result. They divide by 2**16 but should divide by
        # (2**16 - 1). Most likely this was done for performance reason and acceptable.
        # Return Kelvin
        PidFunctionID.GET_BOARD_TEMPERATURE: lambda x: (
            Decimal("175.72") * x / (2**16 - 1) + Decimal("226.3")
        ).quantize(Decimal("1.00")),
        # We need to truncate to 100 %rH according to the datasheet.
        # The datasheet is *wrong* about the conversion formula. Slightly wrong, but wrong nonetheless.
        # They are "off by 1" with the conversion of the 16 bit result. They divide by 2**16 but should divide by
        # (2**16 - 1). Most likely this was done for performance reason and acceptable.
        # Return %rH (above liquid water), rH values below 0°C need to be compensated.
        PidFunctionID.GET_HUMIDITY: lambda x: (
            max(min(125 * Decimal(x) / Decimal(2**16 - 1) - 6, Decimal(100)), Decimal(0))
        ).quantize(Decimal("1.00")),
        PidFunctionID.GET_MAC_ADDRESS: bytearray,
    }

    _RAW_TO_UNIT_11: dict[PidFunctionID, Callable] = {
        PidFunctionID.GET_BOARD_TEMPERATURE: lambda x: (Decimal(x) + Decimal("273.15")).quantize(Decimal("1.00")),
        PidFunctionID.GET_HUMIDITY: lambda x: Decimal(x).quantize(Decimal("1.00")),
        PidFunctionID.GET_MAC_ADDRESS: bytearray,
    }

    def __init__(self, connection: Connection, api_version: tuple[int, int, int]) -> None:
        """
        Create a pid controller. The API version is required to automatically adapt the different api versions.

        Parameters
        ----------
        connection: Connection
            Either an ethernet or a serial connection
        api_version:
            The api version as enumerated by the connection
        """
        super().__init__(connection, api_version)
        self.__raw_to_unit: dict[PidFunctionID, Callable] = (
            PidController._RAW_TO_UNIT_11 if api_version >= (0, 11, 0) else PidController._RAW_TO_UNIT
        )
        self.__logger = logging.getLogger(__name__)

    def __str__(self):
        return f"Labnode at {self.connection}"

    @staticmethod
    def __test_for_errors(result: dict, key: int) -> None:
        """
        Test the reply from the device for error messages and raise exceptions accordingly.

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
                raise PidNotInitializedError(
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

    async def __send_single_request(self, key: int, value: Any | None = None) -> Any:
        result = await self.send_multi_request(
            data={
                key: value,
            }
        )
        self.__test_for_errors(result, key)

        if key > 0:
            return ErrorCode(result[key])

        return result[key]

    async def send_multi_request(self, data: dict[PidFunctionID | int, Any]) -> dict:
        """
        Send one or more requests to the device.

        Parameters
        ----------
        data

        Returns
        -------

        Raises
        ------
        ValueError
            If an unknown function id was sent and `response_expected` was set to True
        """
        if self.api_version < (0, 11, 0):
            # We need to rewrite some function ids
            if PidFunctionID.GET_HUMIDITY in data:
                data[-21] = data[PidFunctionID.GET_HUMIDITY]
                del data[PidFunctionID.GET_HUMIDITY]
            if PidFunctionID.GET_BOARD_TEMPERATURE in data:
                data[-20] = data[PidFunctionID.GET_BOARD_TEMPERATURE]
                del data[PidFunctionID.GET_BOARD_TEMPERATURE]

        result = await self.connection.send_request(data=data, response_expected=True)
        assert result is not None

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
            self.__logger.error("Received unknown function id in data: %(data)s", {"data": data})
            return result
        return result

    async def get_software_version(self) -> tuple[int, int, int]:
        """
        Get the firmware version running on the device. The response is a tuple of ints, that represents the version
        number.

        Returns
        -------
        Tuple of int
            The version number
        """
        return await self.get_by_function_id(PidFunctionID.GET_SOFTWARE_VERSION)

    async def get_hardware_version(self) -> tuple[int, int, int]:
        """
        Get the hardware revision of the device. The response is a tuple of ints, that represents the version number.

        Returns
        -------
        Tuple of int
            The revision number
        """
        return await self.get_by_function_id(PidFunctionID.GET_HARDWARE_VERSION)

    async def get_serial(self) -> int:
        """
        Get the serial number of the device.

        Returns
        -------
        int
            The serial number of the device
        """
        return await self.get_by_function_id(PidFunctionID.GET_SERIAL_NUMBER)

    async def get_device_temperature(self) -> Decimal:
        """
        Query the temperature of the onboard sensor.

        Returns
        -------
        Decimal
            The temperature of the onboard sensor in Kelvin
        """
        return await self.get_by_function_id(PidFunctionID.GET_BOARD_TEMPERATURE)

    async def get_humidity(self) -> Decimal:
        """
        Returns the humidity as read by the onboard sensor.

        Returns
        -------
        Decimal
            The humidity in %rH
        """
        return await self.get_by_function_id(PidFunctionID.GET_HUMIDITY)

    async def get_mac_address(self) -> bytearray:
        """
        Get the MAC address used by the ethernet port.

        Returns
        -------
        bytearray
            An array of length 6 which contains the MAC
        """
        return await self.get_by_function_id(PidFunctionID.GET_MAC_ADDRESS)

    async def set_mac_address(self, mac: tuple[int, int, int, int, int, int] | list[int] | bytearray) -> None:
        """
        Set the MAC address used by the ethernet port.

        Parameters
        ----------
        mac: bytearray or tuple of int
            The MAC address as a bytearray of length 6
        """
        assert len(mac) == 6
        mac = bytearray(mac)  # convert to bytearray, this also makes sure, that all values are in range(0, 256)
        await self.__send_single_request(PidFunctionID.SET_MAC_ADDRESS, mac)

    async def get_uuid(self) -> UUID:
        """
        Get the universally unique identifier of the node.

        Returns
        -------
        UUID
            The universally unique identifier of the node

        Raises
        ------
        FunctionNotImplementedError
            If the firmware version does not support the request.
        """
        if self.api_version < (0, 12, 0):
            raise FunctionNotImplementedError(
                f"{PidFunctionID.GET_UUID.name} is only supported in api version >= 0.12.0"
            )
        result = await self.get_by_function_id(PidFunctionID.GET_UUID)
        return UUID(bytes=bytes(result))

    async def set_uuid(self, uuid: UUID) -> None:
        """
        Set the universally unique identifier of the node.

        Parameters
        ----------
        uuid: UUID
            The universally unique identifier of the node

        Raises
        ------
        FunctionNotImplementedError
            If the firmware version does not support the request.
        """
        if self.api_version < (0, 12, 0):
            raise FunctionNotImplementedError(
                f"{PidFunctionID.SET_UUID.name} is only supported in api version >= 0.12.0"
            )
        await self.__send_single_request(PidFunctionID.SET_UUID, tuple(uuid.bytes))

    async def get_auto_resume(self) -> bool:
        """
        Query the node, whether is automatically resumes after a reset (intentionally or unintentionally). If set, the
        node will return to the same state. If not, the node will always come up as disabled with default settings.

        Returns
        -------
        bool
            True if the node keeps its enabled state after a reset
        """
        return await self.get_by_function_id(PidFunctionID.GET_AUTO_RESUME)

    async def set_auto_resume(self, value: bool):
        """
        Set the controller to automatically load the previous settings and resume its action.

        Parameters
        ----------
        value: bool
            Set to True to load the node settings on boot
        """
        await self.__send_single_request(PidFunctionID.SET_AUTO_RESUME, bool(value))

    async def set_lower_output_limit(self, limit: int) -> None:
        """
        Set the minimum output of the DAC in bit values.

        Parameters
        ----------
        limit: int
            The minimum output value of the DAC

        Raises
        ------
        ValueError
            If the limit was out of bounds.
        """
        try:
            await self.__send_single_request(PidFunctionID.SET_LOWER_OUTPUT_LIMIT, limit)
        except InvalidFormatError:
            raise ValueError("Invalid limit") from None

    async def get_lower_output_limit(self) -> int:
        """
        Get the minimum output value of the DAC.

        Returns
        -------
        int
            The minimum output in bit
        """
        return await self.get_by_function_id(PidFunctionID.GET_LOWER_OUTPUT_LIMIT)

    async def set_upper_output_limit(self, limit: int) -> None:
        """
        Set the maximum output of the DAC in bit values.

        Parameters
        ----------
        limit: int
            The maximum output value of the DAC

        Raises
        ------
        ValueError
            If the limit was out of bounds.
        """
        try:
            await self.__send_single_request(PidFunctionID.SET_UPPER_OUTPUT_LIMIT, limit)
        except InvalidFormatError:
            raise ValueError("Invalid limit") from None

    async def get_upper_output_limit(self) -> int:
        """
        Get the maximum output of the DAC in bit values.

        Returns
        -------
        int
            The upper limit for the output DAC
        """
        return await self.get_by_function_id(PidFunctionID.GET_UPPER_OUTPUT_LIMIT)

    async def set_timeout(self, timeout: float) -> None:
        """
        Set the timeout, that defines when the controller switches to fallback mode. The time is measured in s.

        Parameters
        ----------
        timeout
            The timeout in seconds
        """
        assert timeout > 0
        await self.__send_single_request(PidFunctionID.SET_TIMEOUT, int(timeout * 1000))

    async def get_timeout(self) -> float:
        """
        Get the time, that must pass between updates, before the controller switches to fallback mode.

        Returns
        -------
        float
            The time in seconds, that the controller waits between updates
        """
        return (await self.get_by_function_id(PidFunctionID.GET_TIMEOUT)) / 1000

    async def set_dac_gain(self, enable: bool) -> None:
        """
        Set the gain of the DAC to x2. This will increase the output voltage range from 0..5V to 0..10V.

        Parameters
        ----------
        enable
            True to enable the gain
        """
        await self.__send_single_request(PidFunctionID.SET_GAIN, bool(enable))

    async def is_dac_gain_enabled(self) -> bool:
        """
        Return True if the DAC output goes from 0-10 V. False if the DAC gain is disabled and the output is 0-5 V.

        Returns
        -------
        bool
            True if the gain is enabled
        """
        return await self.get_by_function_id(PidFunctionID.GET_GAIN)

    async def set_pid_feedback_direction(self, feedback: FeedbackDirection) -> None:
        """
        Set the sign of the pid output. This needs to be adjusted according to the actuator used to
        control the plant. Typically, it is assumed, that the feedback is negative. For example, when
        dealing with e.g. temperature control, this means, that if the temperature is too high,
        an increase in the feedback will increase the cooling action.
        In short: If set to `FeedbackDirection.NEGATIVE`, a positive error will result in a negative plant response.

        Parameters
        ----------
        feedback: FeedbackDirection
            The direction of the controller response
        """
        feedback = FeedbackDirection(feedback)
        await self.__send_single_request(PidFunctionID.SET_DIRECTION, feedback.value)

    async def get_pid_feedback_direction(self) -> FeedbackDirection:
        """
        Get the sign of the pid output. If set to `FeedbackDirection.NEGATIVE`, a positive error will result in a
        negative plant response.

        Returns
        -------
        FeedbackDirection
            The direction of the controller response
        """
        return FeedbackDirection(await self.get_by_function_id(PidFunctionID.GET_DIRECTION))

    async def set_output(self, value: int) -> None:
        """
        Set the output value of the DAC. This function only works, when the controller mode is set to disabled (manual).
        Use `set_enabled(false)`.

        Parameters
        ----------
        value: int
            The output in bit
        """
        await self.__send_single_request(PidFunctionID.SET_OUTPUT, int(value))

    async def get_output(self) -> int:
        """
        Queries the output value of the DAC.

        Returns
        -------
        int
            The output of the DAC in bit
        """
        return await self.get_by_function_id(PidFunctionID.GET_OUTPUT)

    async def set_enabled(self, enabled: bool) -> None:
        """
        Set the PID controller to enabled/automatic or disabled/manual mode.

        Parameters
        ----------
        enabled: bool
            True to enable the PID controller
        """
        await self.__send_single_request(PidFunctionID.SET_ENABLED, bool(enabled))

    async def is_enabled(self) -> bool:
        """
        Queries the state of the PID controller.

        Returns
        -------
        bool
            True if the controller is enabled
        """
        return await self.get_by_function_id(PidFunctionID.GET_ENABLED)

    async def __set_kx(self, function_id: PidFunctionID, kx: int) -> None:  # pylint: disable=invalid-name
        """
        Set the PID K{p,i,d} parameter. The Kp, Ki, Kd parameters are stored in Q16.16 format

        Parameters
        ----------
        function_id: PidFunctionID
            Select which parameter set should be updated
        kx: int
            The value of the Kp, Ki or Kd parameter

        Raises
        ------
        InvalidFormatError
            If the pid constant was rejected.
        """
        if self.api_version < (0, 11, 0) and function_id in (
            PidFunctionID.SET_SECONDARY_KP,
            PidFunctionID.SET_SECONDARY_KI,
            PidFunctionID.SET_SECONDARY_KD,
        ):
            raise FunctionNotImplementedError(f"{function_id.name} is only supported in api version >= 0.11.0")
        try:
            await self.__send_single_request(function_id, int(kx))
        except InvalidFormatError:
            raise ValueError("Invalid PID constant") from None

    async def set_kp(self, kp: int, config_id: int = 0) -> None:  # pylint: disable=invalid-name
        """
        Set the PID Kp parameter. The Kp, Ki, Kd parameters are stored in Q16.16 format.

        Parameters
        ----------
        kp: int
            The PID k_p parameter in Q16.16 format
        config_id: {0, 1}, default=0
            The id of the parameter set. The controller supports two pid parameter sets. Either 0 or 1.
        """
        assert config_id in (0, 1)
        if config_id == 0:
            await self.__set_kx(PidFunctionID.SET_KP, kp)
        else:
            await self.__set_kx(PidFunctionID.SET_SECONDARY_KP, kp)

    async def get_kp(self, config_id: int = 0) -> int:
        """
        Get the PID Kp parameter. The Kp, Ki, Kd parameters are stored in Q16.16 format.

        Parameters
        ----------
        config_id: {0, 1}, default=0
            The id of the parameter set. The controller supports two pid parameter sets. Either 0 or 1.

        Raises
        ------
        FunctionNotImplementedError
            If the firmware version does not support the request.
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
        Set the PID Ki parameter. The Kp, Ki, Kd parameters are stored in Q16.16 format.

        Parameters
        ----------
        ki: int
            The parameter value in Q16.16 format (32 bit)
        config_id: {0, 1}, default=0
            The id of the parameter set. The controller supports two pid parameter sets. Either 0 or 1.
        """
        assert config_id in (0, 1)
        if config_id == 0:
            await self.__set_kx(PidFunctionID.SET_KI, ki)
        else:
            await self.__set_kx(PidFunctionID.SET_SECONDARY_KI, ki)

    async def get_ki(self, config_id: int = 0) -> int:
        """
        Get the PID Ki parameter. The Kp, Ki, Kd parameters are stored in Q16.16 format.

        Parameters
        ----------
        config_id: {0, 1}, default=0
            The id of the parameter set. The controller supports two pid parameter sets. Either 0 or 1.

        Raises
        ------
        FunctionNotImplementedError
            If the firmware version does not support the request.
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
        Set the PID Kd parameter. The Kp, Ki, Kd parameters are stored in Q16.16 format.

        Parameters
        ----------
        kd: int
            The parameter value in Q16.16 format (32 bit)
        config_id: {0, 1}, default=0
            The id of the parameter set. The controller supports two pid parameter sets. Either 0 or 1.
        """
        assert config_id in (0, 1)
        if config_id == 0:
            await self.__set_kx(PidFunctionID.SET_KD, kd)
        else:
            await self.__set_kx(PidFunctionID.SET_SECONDARY_KD, kd)

    async def get_kd(self, config_id: int = 0) -> int:
        """
        Get the PID Kd parameter. The Kp, Ki, Kd parameters are stored in Q16.16 format.

        Parameters
        ----------
        config_id: {0, 1}, default=0
            The id of the parameter set. The controller supports two pid parameter sets. Either 0 or 1.

        Raises
        ------
        FunctionNotImplementedError
            If the firmware version does not support the request.
        """
        assert config_id in (0, 1)
        if config_id == 0:
            return await self.get_by_function_id(PidFunctionID.GET_KD)

        if self.api_version >= (0, 11, 0):
            return await self.get_by_function_id(PidFunctionID.GET_SECONDARY_KD)

        raise FunctionNotImplementedError(
            f"{PidFunctionID.GET_SECONDARY_KD.name} is only supported in api version >= 0.11.0"
        )

    async def set_input(self, value: int, return_output: bool = False) -> int | None:
        """
        Set the input, which is fed to the PID controller. The value is in Q16.16 format.

        Parameters
        ----------
        value: int
            The input value in Q16.16 format
        return_output: bool
            Returns the output of the controller if True

        Returns
        -------
        int or None:
            Returns the output of the controller if return_output is set
        """
        # We need to send a multi_request, because if return_output is True, we want to get the
        # output after the input has been set
        request: dict[int, int | None] = {PidFunctionID.SET_INPUT: int(value)}
        if return_output:
            request[PidFunctionID.GET_OUTPUT] = None
        result = await self.send_multi_request(request)

        # We need to test for errors, which would normally be done by __send_single_request()
        self.__test_for_errors(result, PidFunctionID.SET_INPUT)
        if return_output:
            return result[PidFunctionID.GET_OUTPUT]

        return None

    async def set_setpoint(self, value: int, config_id: int = 0) -> None:
        """
        Set the PID setpoint. The value is in Q16.16 format.

        Parameters
        ----------
        value: int
            The setpoint of the PID controller in Q16.16 format.
        config_id: {0, 1}, default=0
            The id of the parameter set. The controller supports two pid parameter sets. Either 0 or 1.

        Raises
        ------
        FunctionNotImplementedError
            If the firmware version does not support the request.
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
        Get the PID setpoint. The value is in Q16.16 format.

        Parameters
        ----------
        config_id: {0, 1}, default=0
            The id of the parameter set. The controller supports two pid parameter sets. Either 0 or 1.
        Returns
        -------
        int
            The setpoint value for the given config set.

        Raises
        ------
        FunctionNotImplementedError
            If the firmware version does not support the request.
        """
        assert config_id in (0, 1)
        if config_id == 0:
            return await self.get_by_function_id(PidFunctionID.GET_SETPOINT)

        # Only allow the secondary parameter set on API version >=0.11.0
        if self.api_version >= (0, 11, 0):
            return await self.get_by_function_id(PidFunctionID.GET_SECONDARY_SETPOINT)

        raise FunctionNotImplementedError(
            f"{PidFunctionID.GET_SECONDARY_SETPOINT.name} is only supported in api version >= 0.11.0"
        )

    async def set_secondary_config(self, config_id: int) -> None:
        """
        Set the configuration used when running in fallback mode.

        Parameters
        ----------
        config_id: {0, 1}
            The configuration to be used. The controller supports two pid parameter sets. Either 0 or 1.

        Raises
        ------
        FunctionNotImplementedError
            If the firmware version does not support the request.
        InvalidFormatError
            If the config_id is not in {0, 1}.
        """
        assert config_id in (0, 1)
        if self.api_version < (0, 11, 0):
            raise FunctionNotImplementedError(
                f"{PidFunctionID.SET_SECONDARY_PID_PARAMETER_SET.name} is only supported in api version >= 0.11.0"
            )
        try:
            await self.__send_single_request(PidFunctionID.SET_SECONDARY_PID_PARAMETER_SET, int(config_id))
        except InvalidFormatError:
            raise ValueError("Invalid configuration set. Use either 0 or 1.") from None

    async def get_secondary_config(self) -> int:
        """
        Set the configuration id used when running in fallback mode.

        Returns
        -------
        int
            The configuration used, when running in fallback mode. The controller supports two pid parameter sets.
            Either 0 or 1.
        """
        if self.api_version < (0, 11, 0):
            raise FunctionNotImplementedError(
                f"{PidFunctionID.GET_SECONDARY_PID_PARAMETER_SET.name} is only supported in api version >= 0.11.0"
            )
        return await self.get_by_function_id(PidFunctionID.GET_SECONDARY_PID_PARAMETER_SET)

    async def set_secondary_pid_update_interval(self, value: float):
        """
        Set the update interval, when running in fallback mode using the secondary PID settings.
        The Controller will feed a value from the internal sensor to the secondary PID controller every {value} s.

        Parameters
        ----------
        value: int
            The update interval in seconds
        """
        assert value > 0
        try:
            await self.__send_single_request(PidFunctionID.SET_FALLBACK_UPDATE_INTERVAL, int(value * 1000))
        except InvalidFormatError:
            raise ValueError("Invalid calibration offset") from None

    async def get_secondary_pid_update_interval(self) -> float:
        """
        The update interval, which is used when running in fallback mode. The return value is in seconds.

        Returns
        -------
        float:
            The number of seconds between updates with the backup sensor when running in fallback mode.
        """
        return (await self.get_by_function_id(PidFunctionID.GET_FALLBACK_UPDATE_INTERVAL)) / 1000

    async def reset(self) -> None:
        """
        Resets the device. This will trigger a hardware reset.
        """
        await self.__send_single_request(PidFunctionID.RESET)

    async def reset_settings(self) -> None:
        """
        Resets the device to default values.
        """
        await self.__send_single_request(PidFunctionID.RESET_SETTINGS)

    async def set_serial(self, serial: int) -> None:
        """
        Set the serial number of the device
        Parameters
        ----------
        serial: int
            The serial number. Maximum: 4294967295 (32 bit)

        Raises
        ------
        ValueError
            If the serial number is not valid.
        """
        try:
            await self.__send_single_request(PidFunctionID.SET_SERIAL_NUMBER, int(serial))
        except InvalidFormatError:
            raise ValueError("Invalid serial number") from None

    async def get_active_connection_count(self) -> int:
        """
        Get the number of open sockets.
        Returns
        -------
        int
            The number of sockets

        Raises
        ------
        FunctionNotImplementedError
            If the firmware version does not support the request.
        """
        if self.api_version < (0, 11, 0):
            raise FunctionNotImplementedError(
                f"{PidFunctionID.GET_ACTIVE_CONNECTION_COUNT.name} is only supported in api version >= 0.11.0"
            )
        return await self.get_by_function_id(PidFunctionID.GET_ACTIVE_CONNECTION_COUNT)

    async def get_by_function_id(self, function_id: PidFunctionID | int) -> Any:
        """
        Query a value by function id, instead of calling the named function.

        Parameters
        ----------
        function_id: PidFunctionID or int
            The function to query
        Returns
        -------
        Any
            The result of the query.

        Raises
        ------
        InvalidCommandError
            If the function id was given as an integer and is unknown
        """
        try:
            function_id = PidFunctionID(function_id)
        except ValueError:
            raise InvalidCommandError(f"Command {function_id} is invalid.") from None
        assert function_id.value < 0  # all getter have negative ids

        result = await self.__send_single_request(function_id)

        if function_id in self.__raw_to_unit:
            result = self.__raw_to_unit[function_id](result)

        return result
