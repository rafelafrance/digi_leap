import unittest

from tests.setup import test


class TestLocality(unittest.TestCase):
    def test_locality_01(self):
        self.assertEqual(
            test("""5 miles North of Mason off Hwy 386."""),
            [
                {
                    "locality": "5 miles North of Mason off Hwy 386.",
                    "trait": "locality",
                    "start": 0,
                    "end": 35,
                }
            ],
        )

    def test_locality_02(self):
        self.assertEqual(
            test(
                """
                Tunkhannock Twp. Pocono Pines Quadrangle. Mud Run, Stonecrest Park,.16
                miles SSW of Long Pond, PA. Headwaters wetland of Indiana Mountains
                Lake.
                """
            ),
            [
                {
                    "locality": "Tunkhannock Twp.",
                    "trait": "locality",
                    "start": 0,
                    "end": 16,
                },
                {
                    "locality": "Pocono Pines Quadrangle.",
                    "trait": "locality",
                    "start": 17,
                    "end": 41,
                },
                {
                    "locality": "Mud Run, Stonecrest Park,"
                    ".16 miles SSW of Long Pond, PA.",
                    "trait": "locality",
                    "start": 42,
                    "end": 98,
                },
                {
                    "locality": "Headwaters wetland of Indiana Mountains Lake.",
                    "trait": "locality",
                    "start": 99,
                    "end": 144,
                },
            ],
        )

    def test_locality_03(self):
        self.assertEqual(
            test("""; files. purple."""),
            [],
        )

    def test_locality_04(self):
        self.assertEqual(
            test("""(Florida's Turnpike)"""),
            [
                {
                    "locality": "Florida's Turnpike",
                    "trait": "locality",
                    "start": 0,
                    "end": 19,
                }
            ],
        )

    def test_locality_05(self):
        self.assertEqual(
            test(
                """
                Wallowa-Whitman National Forest, Forest Service Road 7312.
                """
            ),
            [
                {
                    "locality": "Wallowa-Whitman National Forest, Forest Service "
                    "Road 7312.",
                    "trait": "locality",
                    "start": 0,
                    "end": 58,
                },
            ],
        )

    def test_locality_06(self):
        self.assertEqual(
            test("""Sonoran Desert scrub, disturbed trail side. Occasional annual."""),
            [
                {
                    "habitat": "sonoran desert scrub",
                    "trait": "habitat",
                    "start": 0,
                    "end": 20,
                },
                {
                    "locality": "disturbed trail side.",
                    "trait": "locality",
                    "start": 22,
                    "end": 43,
                },
                {
                    "plant_duration": "annual",
                    "trait": "plant_duration",
                    "start": 55,
                    "end": 61,
                },
            ],
        )

    def test_locality_07(self):
        self.assertEqual(
            test(
                """
                Arizona Uppland Sonoran Desert desert scrub, flats.
                Sandy soil Local erecta annual,
                """
            ),
            [
                {
                    "locality": "Arizona Uppland Sonoran Desert desert scrub, flats.",
                    "trait": "locality",
                    "start": 0,
                    "end": 51,
                },
                {"habitat": "sandy soil", "trait": "habitat", "start": 52, "end": 62},
                {
                    "plant_duration": "annual",
                    "trait": "plant_duration",
                    "start": 76,
                    "end": 82,
                },
            ],
        )

    def test_locality_08(self):
        self.assertEqual(
            test("""Scattered on edge of forest;"""),
            [{"end": 27, "habitat": "edge of forest", "start": 13, "trait": "habitat"}],
        )

    def test_locality_09(self):
        self.assertEqual(
            test("""lobes turned out or black."""),
            [
                {"trait": "subpart", "subpart": "lobe", "start": 0, "end": 5},
                {
                    "color": "black",
                    "trait": "color",
                    "start": 20,
                    "end": 25,
                    "subpart": "lobe",
                },
            ],
        )
