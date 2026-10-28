import json
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from etherdigits.__main__ import main
from etherdigits.render import mp3_encoder, normalize, radio_effect, render, write_audio
from etherdigits.script import Format, Pause, Say, Transmission, build_script
from etherdigits.voicepack import TOKENS, VoicePackError, find_pack, list_packs, load_pack, resample

from .helpers import CLIP_SECONDS, make_pack


class Packs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_shipped_packs_are_complete(self):
        packs = list_packs()
        self.assertGreaterEqual(len(packs), 3)
        for pack in packs:
            self.assertEqual(sorted(pack.clips), sorted(TOKENS), pack.id)
            self.assertTrue(pack.license, pack.id)
            for token in TOKENS:
                self.assertGreater(len(pack.clip(token, 22050)), 2000, f"{pack.id} {token}")

    def test_find_by_language_and_path(self):
        self.assertEqual(find_pack("en").language, "en")
        path = make_pack(self.base)
        self.assertEqual(find_pack(str(path)).id, "test-xx")
        with self.assertRaises(VoicePackError):
            find_pack("klingon")

    def test_missing_digit_is_an_error(self):
        path = make_pack(self.base)
        meta = json.loads((path / "pack.json").read_text())
        del meta["clips"]["7"]
        (path / "pack.json").write_text(json.dumps(meta))
        with self.assertRaises(VoicePackError):
            load_pack(path)

    def test_resample(self):
        audio = np.ones(8000, dtype=np.float32)
        self.assertEqual(len(resample(audio, 8000, 16000)), 16000)


class Render(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.pack = load_pack(make_pack(self.base))

    def tearDown(self):
        self.tmp.cleanup()

    def test_length_follows_script(self):
        audio = render([Say("1"), Pause(1.0), Say("2")], self.pack, rate=8000)
        expected = 2 * CLIP_SECONDS + 1.0 + 0.6  # clips, pause, lead-in and lead-out
        self.assertAlmostEqual(len(audio) / 8000, expected, delta=0.01)
        self.assertAlmostEqual(float(np.max(np.abs(audio))), 10 ** (-1 / 20), places=3)

    def test_missing_words_are_skipped(self):
        pack = load_pack(make_pack(self.base, words=False, pack_id="digits-only"))
        steps = build_script(Transmission(messages=[["12345"]], format=Format(interval="none")))
        self.assertGreater(len(render(steps, pack, rate=8000)), 0)

    def test_radio_effect_keeps_length(self):
        audio = render(build_script(Transmission(format=Format())), self.pack, rate=8000)
        self.assertEqual(len(radio_effect(audio, 8000, seed=1)), len(audio))

    def test_silence_is_not_amplified(self):
        silence = np.zeros(100, dtype=np.float32)
        self.assertEqual(float(np.max(normalize(silence))), 0.0)

    def test_write_wav(self):
        out = self.base / "out.wav"
        write_audio(out, np.zeros(800, dtype=np.float32), 8000)
        with wave.open(str(out)) as w:
            self.assertEqual((w.getframerate(), w.getnframes(), w.getsampwidth()), (8000, 800, 2))

    @unittest.skipUnless(mp3_encoder(), "no MP3 encoder installed")
    def test_write_mp3(self):
        out = self.base / "out.mp3"
        write_audio(out, np.zeros(8000, dtype=np.float32), 8000)
        self.assertGreater(out.stat().st_size, 100)

    def test_unknown_extension(self):
        with self.assertRaises(ValueError):
            write_audio(self.base / "out.ogg", np.zeros(10, dtype=np.float32), 8000)


class CommandLine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.voice = str(make_pack(self.base))

    def tearDown(self):
        self.tmp.cleanup()

    def test_render(self):
        out = self.base / "tx.wav"
        code = main(["render", "-m", "12345 67890", "--voice", self.voice, "--rate", "8000", "-o", str(out)])
        self.assertEqual(code, 0)
        self.assertTrue(out.is_file())

    def test_bad_input_exit_code(self):
        self.assertEqual(main(["render", "-m", "12A45", "--voice", self.voice]), 2)
        self.assertEqual(main(["render", "--voice", self.voice, "--repeats", "0"]), 2)


if __name__ == "__main__":
    unittest.main()
