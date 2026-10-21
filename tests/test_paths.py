"""Path discovery must not create directories or depend on the test host."""

import tempfile
import unittest
from pathlib import Path

from subjector.paths import AppPaths


class AppPathsTests(unittest.TestCase):
    def test_defaults_are_private_to_subjector_without_creating_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            paths = AppPaths.discover({}, home)

            self.assertEqual(paths.data, home / ".local/share/subjector")
            self.assertEqual(paths.config, home / ".config/subjector")
            self.assertEqual(paths.cache, home / ".cache/subjector")
            self.assertEqual(list(home.iterdir()), [])

    def test_absolute_xdg_overrides_are_used(self):
        paths = AppPaths.discover(
            {
                "XDG_DATA_HOME": "/custom data",
                "XDG_CONFIG_HOME": "/custom config",
                "XDG_CACHE_HOME": "/custom cache",
            },
            Path("/home/example"),
        )

        self.assertEqual(paths.data, Path("/custom data/subjector"))
        self.assertEqual(paths.config, Path("/custom config/subjector"))
        self.assertEqual(paths.cache, Path("/custom cache/subjector"))

    def test_empty_and_relative_xdg_values_use_defaults(self):
        for value in ("", "relative", "~/not-expanded"):
            with self.subTest(value=value):
                paths = AppPaths.discover(
                    dict.fromkeys(
                        ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"),
                        value,
                    ),
                    Path("/home/example"),
                )
                self.assertEqual(paths, AppPaths.discover({}, Path("/home/example")))
