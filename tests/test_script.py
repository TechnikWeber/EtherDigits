import unittest

from etherdigits.groups import GroupError
from etherdigits.script import Format, Melody, Say, Tone, Transmission, build_script, transcript


def spoken(steps):
    return [s.token for s in steps if isinstance(s, Say)]


class BuildScript(unittest.TestCase):
    def test_classic_order(self):
        fmt = Format(callsign="47", interval="none", callsign_repeats=2, message_repeats=2)
        steps = build_script(Transmission(messages=[["12345", "67890"]], format=fmt))
        self.assertEqual(
            spoken(steps),
            ["attention", "4", "7", "4", "7",
             "groups", "2", "2",
             *"1234567890",
             "repeat", *"1234567890",
             "end"],
        )

    def test_no_message(self):
        steps = build_script(Transmission(messages=[], format=Format(interval="none")))
        words = spoken(steps)
        self.assertIn("no_message", words)
        self.assertNotIn("groups", words)
        self.assertEqual(words[-1], "end")

    def test_several_messages_are_separated(self):
        fmt = Format(interval="none", message_repeats=1)
        words = spoken(build_script(Transmission(messages=[["11111"], ["22222"]], format=fmt)))
        self.assertEqual(words.count("separator"), 1)
        self.assertEqual(words.count("groups"), 2)

    def test_group_twice(self):
        fmt = Format(interval="none", message_repeats=1, callsign_repeats=0, announce_group_count=False,
                     group_twice=True)
        words = spoken(build_script(Transmission(messages=[["12345"]], format=fmt)))
        self.assertEqual(words, [*"1234512345", "end"])

    def test_interval_signal(self):
        steps = build_script(Transmission(format=Format(interval="melody", interval_repeats=3)))
        self.assertEqual(sum(isinstance(s, Melody) for s in steps), 3)
        steps = build_script(Transmission(format=Format(interval="beeps", interval_repeats=1, end_tone=False)))
        self.assertEqual(sum(isinstance(s, Tone) for s in steps), 3)


class FormatSettings(unittest.TestCase):
    def test_from_dict(self):
        fmt = Format.from_dict({"callsign": "123", "message_repeats": 3})
        self.assertEqual(fmt.message_repeats, 3)

    def test_unknown_key(self):
        with self.assertRaises(GroupError):
            Format.from_dict({"callsing": "123"})

    def test_bad_values(self):
        for data in ({"message_repeats": 0}, {"interval": "siren"}, {"group_gap": -1}, {"callsign": "x"}):
            with self.assertRaises(GroupError, msg=data):
                Format.from_dict(data)


class Transcript(unittest.TestCase):
    def test_readable(self):
        fmt = Format(callsign="472", interval="none", message_repeats=2, end_tone=False)
        text = transcript(build_script(Transmission(messages=[["12345", "67890"]], format=fmt)), fmt)
        self.assertEqual(
            text.splitlines(),
            ["ATTENTION 472 472 472", "GROUPS 2 2", "12345 67890", "REPEAT 12345 67890", "END"],
        )


if __name__ == "__main__":
    unittest.main()
