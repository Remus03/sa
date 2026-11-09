#!/usr/bin/env python3
"""Read and display the BNO055 telemetry stream from the firmware."""

import argparse
from collections import deque
import math
import struct
import sys
import time

PACKET_SIZE = 6 * 4
MAX_ACCEL_MPS2 = 160.0


def decode_packet(packet: bytes) -> tuple[float, float, float, float, float, float]:
    return struct.unpack("<6f", packet)


def is_plausible(packet: bytes) -> bool:
    values = decode_packet(packet)
    ax, ay, az, heading, roll, pitch = values
    return (
        all(math.isfinite(value) for value in values)
        and all(abs(value) <= MAX_ACCEL_MPS2 for value in (ax, ay, az))
        and 0.0 <= heading <= 360.0
        and -180.0 <= roll <= 180.0
        and -180.0 <= pitch <= 180.0
    )


class PacketReader:
    """Reassemble 24-byte packets and heuristically find stream alignment."""

    def __init__(self) -> None:
        self.buffer = bytearray()
        self.synchronized = False

    def feed(self, data: bytes) -> list[tuple[float, float, float, float, float, float]]:
        self.buffer.extend(data)
        packets = []

        while True:
            if self.synchronized:
                if len(self.buffer) < PACKET_SIZE:
                    break
                packet = bytes(self.buffer[:PACKET_SIZE])
                if is_plausible(packet):
                    del self.buffer[:PACKET_SIZE]
                    packets.append(decode_packet(packet))
                else:
                    self.synchronized = False
                    del self.buffer[0]
                continue

            sync_offset = None
            for offset in range(len(self.buffer) - 2 * PACKET_SIZE + 1):
                first = self.buffer[offset : offset + PACKET_SIZE]
                second = self.buffer[offset + PACKET_SIZE : offset + 2 * PACKET_SIZE]
                if is_plausible(first) and is_plausible(second):
                    sync_offset = offset
                    break

            if sync_offset is None:
                # Keep enough trailing bytes to test a two-packet candidate later.
                excess = len(self.buffer) - (2 * PACKET_SIZE - 1)
                if excess > 0:
                    del self.buffer[:excess]
                break

            del self.buffer[:sync_offset]
            self.synchronized = True

        return packets


def ellipsoid(center: tuple[float, float, float],
              radii: tuple[float, float, float]) -> tuple:
    import numpy as np

    u = np.linspace(0, 2 * np.pi, 20)
    v = np.linspace(0, np.pi, 14)
    x = center[0] + radii[0] * np.outer(np.cos(u), np.sin(v))
    y = center[1] + radii[1] * np.outer(np.sin(u), np.sin(v))
    z = center[2] + radii[2] * np.outer(np.ones_like(u), np.cos(v))
    return x, y, z


def rotation_matrix(heading: float, roll: float, pitch: float):
    import numpy as np

    yaw, bank, tilt = np.radians([heading, roll, pitch])
    rz = np.array([
        [np.cos(yaw), -np.sin(yaw), 0],
        [np.sin(yaw), np.cos(yaw), 0],
        [0, 0, 1],
    ])
    rx = np.array([
        [1, 0, 0],
        [0, np.cos(bank), -np.sin(bank)],
        [0, np.sin(bank), np.cos(bank)],
    ])
    ry = np.array([
        [np.cos(tilt), 0, np.sin(tilt)],
        [0, 1, 0],
        [-np.sin(tilt), 0, np.cos(tilt)],
    ])
    return rz @ ry @ rx


def run_plot(port: str, baud: int) -> int:
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        import serial
        from matplotlib.animation import FuncAnimation
    except (ImportError, AttributeError) as exc:
        print(
            f"Could not load a plotting dependency: {exc}. Install or update "
            "compatible packages with 'python -m pip install --upgrade "
            "pyserial matplotlib numpy'.",
            file=sys.stderr,
        )
        return 2

    history = deque(maxlen=600)
    reader = PacketReader()
    start_time = time.monotonic()
    first_euler = None
    previous_heading = None
    unwrapped_heading = 0.0

    figure = plt.figure(figsize=(12, 7))
    figure.suptitle("BNO055 live orientation")
    layout = figure.add_gridspec(1, 2, width_ratios=(1.15, 1))

    angle_axes = figure.add_subplot(layout[0, 0])
    angle_axes.set_title("Angle change from first sample")
    angle_axes.set_xlabel("Time (s)")
    angle_axes.set_ylabel("Change (degrees)")
    angle_axes.grid(True, alpha=0.3)
    heading_line, = angle_axes.plot([], [], label="Heading")
    roll_line, = angle_axes.plot([], [], label="Roll")
    pitch_line, = angle_axes.plot([], [], label="Pitch")
    angle_axes.legend(loc="upper left")

    bunny_axes = figure.add_subplot(layout[0, 1], projection="3d")
    bunny_axes.set_title("Bunny orientation (absolute Euler angles)")
    bunny_axes.set_xlabel("X")
    bunny_axes.set_ylabel("Y")
    bunny_axes.set_zlabel("Z")
    bunny_axes.set_xlim(-0.9, 1.05)
    bunny_axes.set_ylim(-0.9, 0.9)
    bunny_axes.set_zlim(-0.85, 1.55)
    bunny_axes.set_box_aspect((1, 1, 1.2))
    bunny_axes.view_init(elev=22, azim=-55)

    bunny_parts = [
        (ellipsoid((-0.02, 0, -0.02), (0.50, 0.39, 0.48)), "#c99bdf"),
        (ellipsoid((0.28, 0, 0.49), (0.31, 0.27, 0.29)), "#e2c9ef"),
        (ellipsoid((0.55, 0, 0.45), (0.075, 0.09, 0.065)), "#f28cae"),
        (ellipsoid((0.49, -0.17, 0.56), (0.035, 0.035, 0.045)), "#49384f"),
        (ellipsoid((0.49, 0.17, 0.56), (0.035, 0.035, 0.045)), "#49384f"),
        (ellipsoid((0.19, -0.24, -0.43), (0.25, 0.17, 0.14)), "#d8b8e8"),
        (ellipsoid((0.19, 0.24, -0.43), (0.25, 0.17, 0.14)), "#d8b8e8"),
        (ellipsoid((-0.49, 0, -0.10), (0.16, 0.16, 0.16)), "#f7eefa"),
        (ellipsoid((0.17, -0.13, 1.00), (0.105, 0.09, 0.39)), "#e2c9ef"),
        (ellipsoid((0.17, 0.13, 1.00), (0.105, 0.09, 0.39)), "#e2c9ef"),
        (ellipsoid((0.225, -0.184, 1.00), (0.025, 0.018, 0.29)), "#f4a8c3"),
        (ellipsoid((0.225, 0.076, 1.00), (0.025, 0.018, 0.29)), "#f4a8c3"),
    ]
    surfaces = []
    for (x, y, z), color in bunny_parts:
        surface = bunny_axes.plot_surface(x, y, z, color=color,
                                          linewidth=0, shade=True)
        surfaces.append((surface, np.stack((x, y, z), axis=0), color))

    try:
        uart = serial.Serial(port, baud, timeout=0)
    except serial.SerialException as exc:
        print(f"Could not open serial port {port}: {exc}", file=sys.stderr)
        return 1

    print(f"Reading {port} at {baud} baud; close the plot or press Ctrl+C to stop.")

    def update(_frame):
        nonlocal first_euler, previous_heading, unwrapped_heading

        data = uart.read(max(uart.in_waiting, 1))
        for values in reader.feed(data):
            _, _, _, heading, roll, pitch = values
            now = time.monotonic() - start_time
            if first_euler is None:
                first_euler = (heading, roll, pitch)
                previous_heading = heading
            else:
                heading_step = (heading - previous_heading + 180.0) % 360.0 - 180.0
                unwrapped_heading += heading_step
                previous_heading = heading

            heading_change = unwrapped_heading
            roll_change = roll - first_euler[1]
            pitch_change = pitch - first_euler[2]
            history.append((now, heading_change, roll_change, pitch_change, *values))

            matrix = rotation_matrix(heading, roll, pitch)
            for index, (surface, original, color) in enumerate(surfaces):
                rotated = matrix @ original.reshape(3, -1)
                rotated = rotated.reshape(original.shape)
                surface.remove()
                x, y, z = rotated
                replacement = bunny_axes.plot_surface(
                    x, y, z, color=color, linewidth=0, shade=True
                )
                surfaces[index] = (replacement, original, color)

        if history:
            samples = list(history)
            times = [sample[0] for sample in samples]
            heading_changes = [sample[1] for sample in samples]
            roll_changes = [sample[2] for sample in samples]
            pitch_changes = [sample[3] for sample in samples]
            heading_line.set_data(times, heading_changes)
            roll_line.set_data(times, roll_changes)
            pitch_line.set_data(times, pitch_changes)

            angle_axes.set_xlim(max(0, times[-1] - 30), max(30, times[-1]))
            min_angle = min(heading_changes + roll_changes + pitch_changes)
            max_angle = max(heading_changes + roll_changes + pitch_changes)
            margin = max(5.0, (max_angle - min_angle) * 0.1)
            angle_axes.set_ylim(min_angle - margin, max_angle + margin)

            latest = samples[-1]
            figure.suptitle(
                f"Accel: X={latest[4]:.2f}, Y={latest[5]:.2f}, "
                f"Z={latest[6]:.2f} m/s²"
            )

        return heading_line, roll_line, pitch_line

    animation = FuncAnimation(figure, update, interval=50, blit=False,
                              cache_frame_data=False)
    try:
        plt.show()
    finally:
        uart.close()
    del animation
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plot live BNO055 orientation and acceleration from the STM32 UART."
    )
    parser.add_argument("port", help="serial port, e.g. COM3 or /dev/ttyACM0")
    parser.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args()
    return run_plot(args.port, args.baud)


if __name__ == "__main__":
    raise SystemExit(main())
