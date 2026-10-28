import unittest

from etherdigits.groups import GroupError, parse_groups, random_groups, validate_callsign


class ParseGroups(unittest.TestCase):
    def test_separators_are_ignored(self):
        self.assertEqual(parse_groups("12345 67890"), ["12345", "67890"])
        self.assertEqual(parse_groups("12345-67890\n11111"), ["12345", "67890", "11111"])
        self.assertEqual(parse_groups("1234567890"), ["12345", "67890"])

    def test_other_group_size(self):
        self.assertEqual(parse_groups("1234 5678", group_size=4), ["1234", "5678"])

    def test_letters_are_rejected(self):
        with self.assertRaises(GroupError):
            parse_groups("12345 6789O")

    def test_non_ascii_digits_are_rejected(self):
        with self.assertRaises(GroupError):
            parse_groups("12345 ١٢٣٤٥")  # Arabic-Indic digits

    def test_empty_is_rejected(self):
        with self.assertRaises(GroupError):
            parse_groups("  - ")

    def test_short_last_group_needs_padding(self):
        with self.assertRaises(GroupError):
            parse_groups("12345 678")
        self.assertEqual(parse_groups("12345 678", pad="zero"), ["12345", "67800"])
        padded = parse_groups("12345 678", pad="random")
        self.assertEqual(len(padded), 2)
        self.assertTrue(padded[1].startswith("678") and padded[1].isdigit() and len(padded[1]) == 5)


class RandomGroups(unittest.TestCase):
    def test_shape(self):
        groups = random_groups(20)
        self.assertEqual(len(groups), 20)
        self.assertTrue(all(len(g) == 5 and g.isdigit() for g in groups))

    def test_not_constant(self):
        self.assertGreater(len(set("".join(random_groups(50)))), 5)


class Callsign(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate_callsign("4 7 2"), "472")

    def test_invalid(self):
        for bad in ("", "ABC", "12345678901"):
            with self.assertRaises(GroupError):
                validate_callsign(bad)


if __name__ == "__main__":
    unittest.main()
