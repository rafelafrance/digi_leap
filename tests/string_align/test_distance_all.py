"""Test the distance function in the string_align module."""
import unittest

import cppimport.import_hook  # noqa: F401

from digi_leap.pylib import string_align_py as sa


class TestDistanceAll(unittest.TestCase):
    def test_distance_all_01(self):
        self.assertEqual(sa.levenshtein_all(["aa", "bb"]), [(2, 0, 1)])

    def test_distance_all_02(self):
        self.assertEqual(
            sa.levenshtein_all(["aa", "bb", "ab"]), [(1, 0, 2), (1, 1, 2), (2, 0, 1)]
        )

    def test_distance_all_03(self):
        self.assertEqual(
            sa.levenshtein_all(
                [
                    "MOJAVE DESERT, PROVIDENCE MTS.: canyon above",
                    "E. MOJAVE DESERT , PROVIDENCE MTS . : canyon above",
                    "E MOJAVE DESERT PROVTDENCE MTS. # canyon above",
                    "Be ‘MOJAVE DESERT, PROVIDENCE canyon “above",
                ]
            ),
            [(6, 0, 1), (6, 0, 2), (6, 1, 2), (11, 0, 3), (13, 1, 3), (13, 2, 3)],
        )
