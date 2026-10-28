"""The browser tool and the Python module must agree digit for digit.

The engine script is cut out of pad_tool.html and run with Node.js on the
same inputs as etherdigits.otp. Skipped when Node.js is not installed.
"""

import json
import random
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from etherdigits import otp

ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")

RUNNER = r"""
const fs = require("fs");
const Engine = require(process.argv[2]);
const cases = JSON.parse(fs.readFileSync(0, "utf8"));
const out = {};
const attempt = f => { try { return {ok: f()}; } catch (e) { return {error: e.constructor.name + ": " + e.message}; } };
out.normalize = cases.texts.map(t => Engine.normalize(t));
out.encode = cases.encode.map(([t, l, spaces]) => attempt(() => Engine.encode(t, l, Engine.DEFAULT_CODEBOOKS[l], spaces)));
out.decode = cases.decode.map(([d, l]) => Engine.decode(d, l, Engine.DEFAULT_CODEBOOKS[l]));
out.codebooks = cases.codebooks.map(t => attempt(() => Engine.parseCodebook(t)));
const pad = Engine.padFromJson(cases.pad);
out.encrypt = cases.messages.map(m => attempt(() => Engine.encrypt(m, pad)));
out.reuse = attempt(() => Engine.encrypt("again", pad, cases.pad.pages[0].id));
out.decrypt = cases.ciphers.map(c => attempt(() => Engine.decrypt(c, Engine.padFromJson(cases.pad))));
out.roundtrip = Engine.padToJson(Engine.padFromJson(cases.pad));
const fresh = Engine.newPad({pages: 3, groupsPerPage: 40, language: "en"});
out.fresh = Engine.padToJson(fresh);
process.stdout.write(JSON.stringify(out));
"""

TEXTS = [
    "Treffen morgen 18:30 Uhr am Bahnhof.",
    "Größe, Maße, Öl, Übergang; STRAẞE!",
    "Café crème à la carte — naïve façade",
    "  viele    Leerzeichen \n neue Zeile\tTab  ",
    "Emoji 🛰 and symbols @#$%&*\"'<>",
    "Zahlen 0 1 2 3 4 5 6 7 8 9 und 1945/46",
    "Klammern (wichtig) und Fragen? Ja - nein.",
    "Arabic digits ١٢٣ and fullwidth ＡＢＣ",
    "İstanbul ıi Ǆ ﬁ",
    "",
]

MESSAGES = [
    "Treffen morgen 18:30 Uhr am Bahnhof",
    "Abbrechen. Gefahr! Sofort Kontakt über Telefon 0171 2345678",
    "x",
    "Größe? Café.",
    "",
    "A" * 300,  # longer than a page
]

CODEBOOKS = [
    "100 TREFFEN\n101 Bahnhof  # comment\n\n102=Größe",
    "100 A\n100 B",       # a repeated code replaces the word
    "100 A\n101 A",       # a repeated word is an error
    "12 KURZ",            # code not three digits
    "100 ZWEI WORTE",     # not a single word
    "nur ein feld",
]


def fixed_pad() -> dict:
    rnd = random.Random(1945)
    pages = [{"id": f"{rnd.randrange(100000):05d}", "key": "".join(rnd.choice("0123456789") for _ in range(250))}
             for _ in range(6)]
    pad = otp.Pad(pages={p["id"]: p["key"] for p in pages}, language="de",
                  codebook=otp.normalize_codebook(otp.DEFAULT_CODEBOOKS["de"]), created="2026-01-01T00:00:00Z",
                  name="test")
    return pad.to_json()


def outcome(fn):
    try:
        return {"ok": fn()}
    except otp.OtpError as exc:
        return {"error": str(exc)}


@unittest.skipUnless(NODE, "Node.js not installed")
class Interop(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        html = (ROOT / "pad_tool.html").read_text(encoding="utf-8")
        engine = re.search(r'<script id="engine">(.*?)</script>', html, re.S).group(1)
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        (tmp / "engine.js").write_text(engine, encoding="utf-8")
        (tmp / "runner.js").write_text(RUNNER, encoding="utf-8")

        rnd = random.Random(7)
        cls.pad = fixed_pad()
        encode_cases = [[t, lang, spaces] for t in TEXTS + MESSAGES for lang in ("de", "en") for spaces in (True, False)]
        decode_cases = [["".join(rnd.choice("0123456789") for _ in range(rnd.randrange(1, 80))), rnd.choice(["de", "en"])]
                        for _ in range(400)]
        decode_cases += [[otp.encode(t, "de", otp.DEFAULT_CODEBOOKS["de"]), "de"] for t in TEXTS]
        py_pad = otp.Pad.from_json(cls.pad)
        ciphers = [" ".join(otp.encrypt(m, py_pad)) for m in MESSAGES if m and len(m) < 100]
        ciphers.append("99999 12345")  # unknown page
        cls.cases = {
            "texts": TEXTS, "encode": encode_cases, "decode": decode_cases, "codebooks": CODEBOOKS,
            "pad": cls.pad, "messages": MESSAGES, "ciphers": ciphers,
        }
        result = subprocess.run([NODE, str(tmp / "runner.js"), str(tmp / "engine.js")],
                                input=json.dumps(cls.cases), capture_output=True, text=True, encoding="utf-8")
        if result.returncode != 0:
            raise RuntimeError(result.stderr)
        cls.js = json.loads(result.stdout)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_normalize(self):
        for text, js in zip(TEXTS, self.js["normalize"]):
            norm, dropped = otp.normalize(text)
            self.assertEqual([norm, dropped], js, text)

    def test_encode(self):
        for (text, lang, spaces), js in zip(self.cases["encode"], self.js["encode"]):
            py = outcome(lambda: otp.encode(text, lang, otp.DEFAULT_CODEBOOKS[lang], spaces))
            self.assertEqual(py.get("ok"), js.get("ok"), (text, lang, spaces))

    def test_decode_any_digits(self):
        for (digits, lang), js in zip(self.cases["decode"], self.js["decode"]):
            self.assertEqual(otp.decode(digits, lang, otp.DEFAULT_CODEBOOKS[lang]), js, digits)

    def test_codebooks(self):
        for text, js in zip(CODEBOOKS, self.js["codebooks"]):
            py = outcome(lambda: [[c, w] for c, w in otp.parse_codebook(text).items()])
            self.assertEqual("ok" in py, "ok" in js, text)
            self.assertEqual(py.get("ok"), js.get("ok"), text)

    def test_encrypt_same_groups(self):
        py_pad = otp.Pad.from_json(self.pad)
        for message, js in zip(MESSAGES, self.js["encrypt"]):
            py = outcome(lambda: otp.encrypt(message, py_pad))
            self.assertEqual("ok" in py, "ok" in js, message)
            self.assertEqual(py.get("ok"), js.get("ok"), message)
        self.assertIn("error", self.js["reuse"])
        self.assertIn("never be used twice", self.js["reuse"]["error"])

    def test_decrypt_python_ciphers(self):
        for cipher, js in zip(self.cases["ciphers"], self.js["decrypt"]):
            py = outcome(lambda: otp.decrypt(cipher, otp.Pad.from_json(self.pad)))
            self.assertEqual(py.get("ok"), js.get("ok"), cipher)
        self.assertIn("error", self.js["decrypt"][-1])

    def test_pad_file_roundtrip(self):
        self.assertEqual(self.js["roundtrip"], otp.Pad.from_json(self.pad).to_json())

    def test_browser_pad_loads_in_python(self):
        pad = otp.Pad.from_json(self.js["fresh"])
        self.assertEqual(len(pad.pages), 3)
        self.assertEqual(pad.language, "en")
        keys = "".join(pad.pages.values())
        self.assertEqual(len(keys), 3 * 40 * 5)
        self.assertEqual(set(keys), set("0123456789"))
        groups = otp.encrypt("Meet tomorrow", pad)
        self.assertEqual(otp.decrypt(groups, pad), "MEET TOMORROW")


if __name__ == "__main__":
    unittest.main()
