from __future__ import annotations

from datetime import date
import unittest

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "common"))

from ft_common.object_keys import artifact_key, date_prefix, default_artifact_key, job_prefix


class ObjectKeyTests(unittest.TestCase):
    def test_date_prefix(self) -> None:
        self.assertEqual(date_prefix(date(2026, 1, 3)), "26-01-03")

    def test_job_prefix(self) -> None:
        self.assertEqual(job_prefix(date(2026, 1, 3), "12345678", "a8f3k2p9"), "26-01-03/12345678/a8f3k2p9")

    def test_default_artifact_key_matches_required_convention(self) -> None:
        key = default_artifact_key(date(2026, 1, 3), "12345678", "a8f3k2p9", "translate_translated_units")

        self.assertEqual(
            key,
            "26-01-03/12345678/a8f3k2p9/03_translate/translated_units.json",
        )

    def test_artifact_path_must_be_relative(self) -> None:
        with self.assertRaises(ValueError):
            artifact_key(date(2026, 1, 3), "12345678", "a8f3k2p9", "../bad")

    def test_user_and_file_id_must_be_single_segments(self) -> None:
        with self.assertRaises(ValueError):
            job_prefix(date(2026, 1, 3), "12/34", "a8f3k2p9")
        with self.assertRaises(ValueError):
            job_prefix(date(2026, 1, 3), "12345678", "../bad")


if __name__ == "__main__":
    unittest.main()
