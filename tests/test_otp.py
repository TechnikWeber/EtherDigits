import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from etherdigits import otp
from etherdigits.__main__ import main


class Checkerboard(unittest.TestCase):
    def test_frequent_letters_take_one_digit(self):
        self.assertEqual(otp.encode("ENISRAT", "de", {}), "0123456")
        self.assertEqual(otp.encode("ETAOINS", "en", {}), "0123456")

    def test_every_letter_roundtrips(self):
        for lang in otp.LAYOUTS:
            text = "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG. WHY? (YES), A-B/C: D"
            self.assertEqual(otp.decode(otp.encode(text, lang, {}), lang, {}), text)

    def test_figures(self):
        self.assertEqual(otp.encode("1830", "de", {}), "98" + "11883300" + "98")
        self.assertEqual(otp.decode(otp.encode("UM 1830 UHR", "de", {}), "de", {}), "UM 1830 UHR")

    def test_codebook_words(self):
        book = {"119": "TREFFEN"}
        self.assertEqual(otp.encode("Treffen", "de", book), "99119")
        self.assertEqual(otp.decode("99119", "de", book), "TREFFEN")
        self.assertEqual(otp.decode("99777", "de", book), "[777]")

    def test_umlauts_and_spaces(self):
        self.assertEqual(otp.normalize("  Größe\n\nÜber  ")[0], "GROESSE UEBER")
        self.assertNotIn("90", otp.encode("A B", "de", {}, spaces=False))

    def test_padding_is_invisible(self):
        for tail in ("", "9", "99", "999", "9999"):
            self.assertEqual(otp.decode("0" + tail, "de", {}), "E")

    def test_codebook_parsing(self):
        book = otp.parse_codebook("# comment\n100 Treffen\n101=Bahnhof\n")
        self.assertEqual(book, {"100": "TREFFEN", "101": "BAHNHOF"})
        for bad in ("1000 X", "100 ZWEI WORTE", "100 A\n101 A"):
            with self.assertRaises(otp.OtpError):
                otp.parse_codebook(bad)


class Arithmetic(unittest.TestCase):
    def test_no_carry(self):
        self.assertEqual(otp.add("7395", "5555"), "2840")
        self.assertEqual(otp.subtract("2840", "5555"), "7395")


class Pads(unittest.TestCase):
    def test_roundtrip(self):
        pad = otp.new_pad(pages=3, groups_per_page=20)
        groups = otp.encrypt("Treffen morgen 18:30 Uhr am Bahnhof", pad)
        self.assertTrue(all(len(g) == 5 and g.isdigit() for g in groups))
        self.assertIn(groups[0], pad.used)
        self.assertEqual(otp.decrypt(groups, pad), "TREFFEN MORGEN 18:30 UHR AM BAHNHOF")

    def test_page_is_never_used_twice(self):
        pad = otp.new_pad(pages=2, groups_per_page=10)
        first = otp.encrypt("eins", pad)
        with self.assertRaises(otp.OtpError):
            otp.encrypt("zwei", pad, first[0])
        otp.encrypt("zwei", pad)
        with self.assertRaises(otp.OtpError):
            otp.encrypt("drei", pad)  # all pages used

    def test_too_long(self):
        pad = otp.new_pad(pages=1, groups_per_page=5)
        with self.assertRaises(otp.OtpError):
            otp.encrypt("x" * 100, pad)
        self.assertEqual(pad.used, [])  # a failed attempt does not burn the page

    def test_random_page_ids(self):
        pad = otp.new_pad(pages=50, groups_per_page=5)
        self.assertEqual(len(set(pad.pages)), 50)
        self.assertEqual(set("".join(pad.pages.values())), set("0123456789"))

    def test_file_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pad.json"
            pad = otp.new_pad(pages=2, groups_per_page=10, language="en")
            otp.encrypt("meet", pad)
            otp.save_pad(pad, path)
            loaded = otp.load_pad(path)
            self.assertEqual(loaded.to_json(), pad.to_json())
            with self.assertRaises(otp.OtpError):
                otp.Pad.from_json({"format": "something-else"})


class CommandLine(unittest.TestCase):
    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(args))
        return code, out.getvalue(), err.getvalue()

    def test_pad_encrypt_decrypt(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "pad.json")
            self.assertEqual(self.run_main("pad", "new", "-o", path, "--pages", "2", "--groups", "20")[0], 0)
            code, _, err = self.run_main("pad", "new", "-o", path)
            self.assertEqual(code, 2)
            self.assertIn("--force", err)
            code, groups, _ = self.run_main("encrypt", "--pad", path, "Heute sofort")
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(Path(path).read_text())["used"], [groups.split()[0]])
            code, text, _ = self.run_main("decrypt", "--pad", path, groups)
            self.assertEqual((code, text.strip()), (0, "HEUTE SOFORT"))


if __name__ == "__main__":
    unittest.main()
