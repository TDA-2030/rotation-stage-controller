from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Final

import serial


class RotationStageError(Exception):
    pass


class RotationStageTimeout(RotationStageError):
    pass


@dataclass(slots=True)
class _StageConfig:
    axis: str = "X"
    min_angle: float = 0.0
    max_angle: float = 360.0
    default_feed: float = 1200.0


class RotationStage:
    _WAKEUP_DELAY: Final[float] = 8.0
    _STATUS_POLL_INTERVAL: Final[float] = 0.1
    _REALTIME_STATUS: Final[bytes] = b"?"
    _REALTIME_FEED_HOLD: Final[bytes] = b"!"

    def __init__(
        self,
        connection: serial.Serial,
        *,
        timeout: float = 2.0,
        config: _StageConfig | None = None,
    ) -> None:
        self._serial = connection
        self._timeout = timeout
        self._config = config or _StageConfig()

    @classmethod
    def connect(
        cls,
        port: str,
        baudrate: int = 115200,
        timeout: float = 2.0,
    ) -> "RotationStage":
        connection = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=timeout,
            write_timeout=timeout,
        )
        stage = cls(connection, timeout=timeout)
        try:
            stage._wake_controller()
            return stage
        except Exception:
            stage.disconnect()
            raise

    def home(self) -> None:
        self.send("$H")

    def move_to(self, angle_deg: float, feed: float | None = None) -> None:
        self._validate_angle(angle_deg)
        self.send("G90")
        self.send(self._format_move(angle_deg, feed))

    def rotate(self, delta_deg: float, feed: float | None = None) -> None:
        target = self.position() + delta_deg
        self._validate_angle(target)
        self.send("G91")
        self.send(self._format_move(delta_deg, feed))
        self.send("G90")

    def position(self) -> float:
        status = self._query_status()
        return self._parse_position(status)

    def wait(self, timeout: float | None = None) -> None:
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            state = self._parse_state(self._query_status())
            if state == "Idle":
                return
            if deadline is not None and time.monotonic() >= deadline:
                raise RotationStageTimeout("Timed out while waiting for the stage to become idle.")
            time.sleep(self._STATUS_POLL_INTERVAL)

    def stop(self) -> None:
        self._write_bytes(self._REALTIME_FEED_HOLD)

    def send(self, line: str) -> str:
        if not isinstance(line, str):
            raise TypeError("send() expects a string G-code or controller command.")

        command = line.strip()
        if not command:
            raise RotationStageError("Command line must not be empty.")

        self._write_line(command)
        response_lines: list[str] = []
        deadline = time.monotonic() + self._timeout

        for message in self._iter_messages_until(deadline):
            if message == "ok":
                return "\n".join(response_lines)
            if message.startswith("error"):
                raise RotationStageError(f"Controller rejected command '{command}': {message}")
            response_lines.append(message)

        raise RotationStageTimeout(f"Timed out waiting for response to '{command}'.")

    def disconnect(self) -> None:
        if self._serial.is_open:
            self._serial.close()

    def _wake_controller(self) -> None:
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()
        self._write_bytes(b"\r\n\r\n")
        deadline = time.monotonic() + max(self._timeout, self._WAKEUP_DELAY)

        for message in self._iter_messages_until(deadline):
            if message == "ok" or message.startswith("Grbl "):
                self._serial.reset_input_buffer()
                return
            if message.startswith("error"):
                raise RotationStageError(f"Controller rejected wake-up handshake: {message}")

        raise RotationStageTimeout("Timed out waiting for wake-up handshake from controller.")

    def _write_line(self, line: str) -> None:
        self._write_bytes(f"{line}\n".encode("ascii"))

    def _write_bytes(self, data: bytes) -> None:
        written = self._serial.write(data)
        if written != len(data):
            raise RotationStageError("Failed to write the full command to the serial port.")
        self._serial.flush()

    def _query_status(self) -> str:
        deadline = time.monotonic() + self._timeout
        self._serial.reset_input_buffer()
        self._write_bytes(self._REALTIME_STATUS)

        for message in self._iter_messages_until(deadline):
            if message.startswith("<") and message.endswith(">"):
                return message

        raise RotationStageTimeout("Timed out waiting for controller status.")

    def _iter_messages_until(self, deadline: float):
        while time.monotonic() < deadline:
            raw = self._serial.readline()
            if not raw:
                continue
            message = raw.decode("utf-8", errors="replace").strip()
            if message:
                yield message

    def _parse_position(self, status: str) -> float:
        fields = status.strip("<>").split("|")
        axis_index = self._axis_index()
        for field in fields:
            if field.startswith("MPos:") or field.startswith("WPos:"):
                values = field.split(":", maxsplit=1)[1].split(",")
                try:
                    return float(values[axis_index])
                except (IndexError, ValueError) as exc:
                    raise RotationStageError(f"Failed to parse position from status: {status}") from exc
        raise RotationStageError(f"Status did not include a position field: {status}")

    def _parse_state(self, status: str) -> str:
        try:
            return status.strip("<>").split("|", maxsplit=1)[0]
        except IndexError as exc:
            raise RotationStageError(f"Failed to parse controller state from status: {status}") from exc

    def _format_move(self, distance: float, feed: float | None) -> str:
        axis = self._config.axis
        selected_feed = self._config.default_feed if feed is None else feed
        return f"G1 {axis}{distance:.3f} F{selected_feed:.3f}"

    def _validate_angle(self, angle_deg: float) -> None:
        if not self._config.min_angle <= angle_deg <= self._config.max_angle:
            raise RotationStageError(
                f"Angle {angle_deg} is outside the allowed range "
                f"{self._config.min_angle} to {self._config.max_angle} degrees."
            )

    def _axis_index(self) -> int:
        axis = self._config.axis.upper()
        mapping = {"X": 0, "Y": 1, "Z": 2, "A": 3, "B": 4, "C": 5}
        try:
            return mapping[axis]
        except KeyError as exc:
            raise RotationStageError(f"Unsupported axis '{self._config.axis}'.") from exc
