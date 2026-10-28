"""PTT on a GPIO pin of a Raspberry Pi, through the Linux GPIO character device.

No extra package: the station talks to /dev/gpiochipN with the kernel's
GPIO v2 interface (Linux 5.10 and newer, so every current Raspberry Pi OS).
The line is requested as an output that starts inactive, set active for the
transmission, set inactive again and released.

Wiring: a GPIO pin cannot key a radio directly. Put a transistor or an
optocoupler between the pin and the radio's PTT line. "Active low" is for
circuits that key when the pin goes low.

The user needs access to /dev/gpiochip*; on Raspberry Pi OS that is the
group "gpio", which the first user is in already.

Struct layouts follow <linux/gpio.h>; tests/test_gpio.py pins them down.
"""

from __future__ import annotations

import fcntl
import glob
import os
import struct

GPIO_GET_CHIPINFO_IOCTL = 0x8044B401
GPIO_V2_GET_LINE_IOCTL = 0xC250B407
GPIO_V2_LINE_SET_VALUES_IOCTL = 0xC010B40F
FLAG_ACTIVE_LOW = 1 << 1
FLAG_OUTPUT = 1 << 3
ATTR_OUTPUT_VALUES = 2
REQUEST_SIZE = 592
CONSUMER = b"etherdigits-ptt"

# The chip that drives the 40-pin header, by its label: Pi 1 to 4 (also Zero) and Pi 5.
# On a Pi 5 the header hangs off the RP1 chip, not the SoC's own pinctrl-bcm2712.
PI_LABELS = ("pinctrl-bcm2835", "pinctrl-bcm2711", "pinctrl-rp1")


class GpioError(Exception):
    pass


def chip_info(path: str) -> tuple[str, str, int]:
    """(name, label, number of lines) of a GPIO chip."""
    fd = os.open(path, os.O_RDONLY)
    try:
        buf = bytearray(68)
        fcntl.ioctl(fd, GPIO_GET_CHIPINFO_IOCTL, buf)
    finally:
        os.close(fd)
    name, label, lines = struct.unpack("32s32sI", bytes(buf))
    return name.rstrip(b"\0").decode(), label.rstrip(b"\0").decode(), lines


def list_chips() -> list[dict]:
    chips = []
    for path in sorted(glob.glob("/dev/gpiochip*")):
        try:
            name, label, lines = chip_info(path)
        except OSError as exc:
            chips.append({"path": path, "label": "", "lines": 0, "error": exc.strerror or str(exc)})
            continue
        chips.append({"path": path, "label": label, "lines": lines, "pi": label in PI_LABELS})
    return chips


def find_pi_chip() -> str:
    for chip in list_chips():
        if chip.get("pi"):
            return chip["path"]
    denied = [c for c in list_chips() if c.get("error")]
    if denied:
        raise GpioError(f"no access to {denied[0]['path']} ({denied[0]['error']}); "
                        "add the user to the group gpio and log in again")
    raise GpioError("no Raspberry Pi GPIO chip found; set the chip by hand (e.g. /dev/gpiochip0)")


def line_request(pin: int, active_low: bool) -> bytearray:
    """struct gpio_v2_line_request for one output line, starting inactive."""
    req = bytearray(REQUEST_SIZE)
    struct.pack_into("I", req, 0, pin)                       # offsets[0]
    req[256:256 + len(CONSUMER)] = CONSUMER                  # consumer
    flags = FLAG_OUTPUT | (FLAG_ACTIVE_LOW if active_low else 0)
    struct.pack_into("QI", req, 288, flags, 1)               # config.flags, config.num_attrs
    # config.attrs[0]: output values = 0 (inactive) for line 0
    struct.pack_into("IIQQ", req, 288 + 32, ATTR_OUTPUT_VALUES, 0, 0, 1)
    struct.pack_into("I", req, 560, 1)                       # num_lines
    return req


class GpioPTT:
    """Keys the radio by setting a GPIO line active for the transmission."""

    def __init__(self, pin: int, active_low: bool = False, chip: str = ""):
        self.pin, self.active_low, self.chip = pin, active_low, chip
        self._line_fd: int | None = None

    def _set(self, active: bool) -> None:
        fcntl.ioctl(self._line_fd, GPIO_V2_LINE_SET_VALUES_IOCTL, struct.pack("QQ", 1 if active else 0, 1))

    def __enter__(self):
        from .radio import RadioError
        try:
            chip = self.chip or find_pi_chip()
            fd = os.open(chip, os.O_RDWR)
        except GpioError as exc:
            raise RadioError(str(exc)) from exc
        except OSError as exc:
            raise RadioError(f"GPIO chip {self.chip or '?'}: {exc.strerror or exc}") from exc
        try:
            req = line_request(self.pin, self.active_low)
            try:
                fcntl.ioctl(fd, GPIO_V2_GET_LINE_IOCTL, req)
            except OSError as exc:
                raise RadioError(f"GPIO {self.pin} on {chip}: {exc.strerror or exc} (in use by something else?)") from exc
            self._line_fd = struct.unpack_from("i", req, 588)[0]
        finally:
            os.close(fd)  # the line keeps its own descriptor
        self._set(True)
        return self

    def __exit__(self, *exc):
        if self._line_fd is not None:
            try:
                self._set(False)
            finally:
                os.close(self._line_fd)
                self._line_fd = None
        return False
