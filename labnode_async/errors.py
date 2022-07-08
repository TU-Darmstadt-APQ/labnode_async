# ##### BEGIN GPL LICENSE BLOCK #####
#
# Copyright (C) 2021  Patrick Baus
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
"""Custom errors raised by Labnodes."""


class LabnodeException(Exception):
    """
    The base exception class for all errors thrown by labnode_async.
    """


class PidNotInitializedError(LabnodeException):
    """
    Raised by the controller if the PID parameters have not been initialized, yet the controller was turned on
    """


class InvalidReplyError(LabnodeException):
    """
    Raised if the Reply from the Labnode matched our request id, yet did not contain a reply to the request made.
    """


class InvalidModeError(LabnodeException):
    """
    Raised if the labnode cannot execute the command, because it is not set to the right operating mode.
    """


class FunctionNotImplementedError(LabnodeException):
    """
    Raised if the Labnode recognises the command, but the function is not supported in this firmware.
    """


class InvalidCommandError(LabnodeException):
    """
    Raised if the Labnode does not recognise the command.
    """


class InvalidFormatError(LabnodeException):
    """
    Raised if the request does not have the correct formatting. Typically, the wrong datatype.
    """
