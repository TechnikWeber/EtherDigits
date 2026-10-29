"""Regression checks for cutting a short token out of synthesized context."""
import unittest

import numpy as np

from scripts.build_voicepack import extract_aligned_word


class AlignedVoiceClips(unittest.TestCase):
    def test_context_is_removed_and_word_is_complete(self):
        # Spoken prefix/suffix, separated from the word by silent delimiters.
        widths = np.array([100, 100, 100, 80, 90, 100, 100])
        audio = np.concatenate([
            np.full(200, -0.8), np.zeros(100),
            np.full(80, 0.2), np.full(90, 0.4),
            np.zeros(100), np.full(100, -0.6),
        ])
        clip = extract_aligned_word(audio, widths, 3, 5, 1000, 16)
        np.testing.assert_array_equal(clip, audio[280:510])
        self.assertFalse((clip < 0).any(), "Context speech leaked into the word")

    def test_margins_do_not_reach_past_short_delimiters(self):
        widths = np.array([100, 5, 80, 90, 6, 100])
        audio = np.arange(widths.sum())
        clip = extract_aligned_word(audio, widths, 2, 4, 1000, 16)
        np.testing.assert_array_equal(clip, audio[100:281])

    def test_collapsed_durations_are_rejected(self):
        # The original Kerstin failure: every ID has only one 16 ms frame.
        widths = np.full(20, 256)
        with self.assertRaisesRegex(ValueError, "Collapsed"):
            extract_aligned_word(np.zeros(widths.sum()), widths, 5, 15, 16000, 256)

    def test_invalid_alignment_cannot_produce_a_clip(self):
        for widths, start, end in [
            ([40, 80, 40], 0, 2),
            ([40, 80, 40], 1, 3),
            ([40, 80, 40], 2, 1),
            ([40, 80, 39], 1, 2),
            ([40, -80, 200], 1, 2),
            ([40, float("nan"), 40], 1, 2),
            ([40.5, 79.5, 40], 1, 2),
        ]:
            with self.subTest(widths=widths, start=start, end=end):
                with self.assertRaisesRegex(ValueError, "Invalid"):
                    extract_aligned_word(np.zeros(160), np.array(widths), start, end, 1000, 16)


if __name__ == "__main__":
    unittest.main()
