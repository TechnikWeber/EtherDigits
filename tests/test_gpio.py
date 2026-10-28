"""GPIO PTT without a Raspberry Pi: the kernel calls are recorded instead of made.

The offsets below were taken from <linux/gpio.h> with sizeof/offsetof:
request 592 bytes, consumer at 256, config at 288 (flags 288, num_attrs 296,
attrs 320, an attribute is 24 bytes with its mask at +16), num_lines at 560, fd at 588.
"""

import struct
import sys
import unittest
from unittest import mock

if not sys.platform.startswith("linux"):
    raise unittest.SkipTest("GPIO is Linux only")

from etherdigits import gpio  # noqa: E402
from etherdigits.radio import RadioError, make_ptt, validate_output  # noqa: E402


class Layout(unittest.TestCase):
    def test_request_for_one_output_line(self):
        req = gpio.line_request(17, active_low=False)
        self.assertEqual(len(req), 592)
        self.assertEqual(struct.unpack_from("I", req, 0)[0], 17)
        self.assertEqual(bytes(req[256:256 + 15]), b"etherdigits-ptt")
        flags, num_attrs = struct.unpack_from("QI", req, 288)
        self.assertEqual((flags, num_attrs), (gpio.FLAG_OUTPUT, 1))
        attr_id, _pad, values, mask = struct.unpack_from("IIQQ", req, 320)
        self.assertEqual((attr_id, values, mask), (gpio.ATTR_OUTPUT_VALUES, 0, 1))  # starts inactive
        self.assertEqual(struct.unpack_from("I", req, 560)[0], 1)

    def test_active_low(self):
        flags = struct.unpack_from("Q", gpio.line_request(4, active_low=True), 288)[0]
        self.assertEqual(flags, gpio.FLAG_OUTPUT | gpio.FLAG_ACTIVE_LOW)

    def test_ioctl_numbers(self):
        # _IOWR(0xB4, 0x07, 592), _IOWR(0xB4, 0x0F, 16), _IOR(0xB4, 0x01, 68)
        self.assertEqual(gpio.GPIO_V2_GET_LINE_IOCTL, (3 << 30) | (592 << 16) | (0xB4 << 8) | 0x07)
        self.assertEqual(gpio.GPIO_V2_LINE_SET_VALUES_IOCTL, (3 << 30) | (16 << 16) | (0xB4 << 8) | 0x0F)
        self.assertEqual(gpio.GPIO_GET_CHIPINFO_IOCTL, (2 << 30) | (68 << 16) | (0xB4 << 8) | 0x01)


class FakeKernel:
    """Plays the GPIO character device: chips with labels, lines that remember their value."""

    def __init__(self, chips):
        self.chips = chips          # path -> label
        self.calls, self.closed = [], []
        self.value = None
        self._next = 100
        self.fds = {}

    def open(self, path, flags):
        if path not in self.chips:
            raise FileNotFoundError(2, "No such file or directory")
        self._next += 1
        self.fds[self._next] = path
        return self._next

    def close(self, fd):
        self.closed.append(fd)

    def ioctl(self, fd, request, arg):
        self.calls.append(request)
        if request == gpio.GPIO_GET_CHIPINFO_IOCTL:
            label = self.chips[self.fds[fd]].encode()
            arg[:] = struct.pack("32s32sI", b"gpiochip", label, 54)
            return 0
        if request == gpio.GPIO_V2_GET_LINE_IOCTL:
            struct.pack_into("i", arg, 588, 555)
            self.value = 0
            return 0
        if request == gpio.GPIO_V2_LINE_SET_VALUES_IOCTL:
            assert fd == 555
            bits, mask = struct.unpack("QQ", arg)
            self.value = bits & mask
            return 0
        raise OSError(22, "Invalid argument")


class Ptt(unittest.TestCase):
    def kernel(self, chips):
        k = FakeKernel(chips)
        patches = [mock.patch("etherdigits.gpio.os.open", k.open), mock.patch("etherdigits.gpio.os.close", k.close),
                   mock.patch("etherdigits.gpio.fcntl.ioctl", k.ioctl),
                   mock.patch("etherdigits.gpio.glob.glob", lambda pattern: sorted(chips))]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return k

    def test_keys_and_releases(self):
        k = self.kernel({"/dev/gpiochip0": "pinctrl-bcm2711"})
        seen = []
        with gpio.GpioPTT(17):
            seen.append(k.value)
        self.assertEqual((seen, k.value), ([1], 0))
        self.assertIn(555, k.closed)  # the line is released

    def test_released_on_error(self):
        k = self.kernel({"/dev/gpiochip0": "pinctrl-bcm2835"})
        with self.assertRaises(ZeroDivisionError):
            with gpio.GpioPTT(27):
                1 / 0
        self.assertEqual(k.value, 0)
        self.assertIn(555, k.closed)

    def test_finds_the_header_chip_on_a_pi5(self):
        # Older Pi 5 kernels: the SoC's chip first, the header (RP1) as gpiochip4.
        self.kernel({"/dev/gpiochip0": "gpio-brcmstb@107d508500", "/dev/gpiochip4": "pinctrl-rp1"})
        self.assertEqual(gpio.find_pi_chip(), "/dev/gpiochip4")

    def test_no_pi(self):
        self.kernel({"/dev/gpiochip0": "INT34C5:00"})
        with self.assertRaises(RadioError):
            with gpio.GpioPTT(17):
                pass

    def test_from_settings(self):
        ptt = make_ptt(validate_output({"ptt": "gpio", "gpio_pin": 22, "gpio_active_low": True}))
        self.assertIsInstance(ptt, gpio.GpioPTT)
        self.assertEqual((ptt.pin, ptt.active_low), (22, True))
        for bad in ({"ptt": "gpio", "gpio_pin": 99}, {"gpio_chip": "/etc/passwd"}):
            with self.assertRaises(RadioError):
                validate_output(bad)


if __name__ == "__main__":
    unittest.main()
