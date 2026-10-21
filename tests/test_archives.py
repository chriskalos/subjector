"""Runtime archives must not write outside a newly owned staging directory."""

import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from subjector.archives import ExtractionError, ExtractionLimits, extract_runtime


def make_archive(path, entries):
    with tarfile.open(path, "w:gz") as archive:
        for name, kind, payload in entries:
            member = tarfile.TarInfo(name)
            member.type = kind
            member.mode = 0o7777
            if kind == tarfile.REGTYPE:
                member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))
            else:
                member.linkname = payload
                archive.addfile(member)


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.archive = self.root / "runtime.tar.gz"
        self.destination = self.root / "staging"

    def test_extracts_files_and_internal_python_symlinks_with_private_permissions(self):
        make_archive(self.archive, [
            ("python/bin/python3.13", tarfile.REGTYPE, b"executable"),
            ("python/bin/python3", tarfile.SYMTYPE, "python3.13"),
            ("python/current", tarfile.SYMTYPE, "bin/python3"),
        ])
        extract_runtime(self.archive, self.destination)
        executable = self.destination / "python/bin/python3.13"
        self.assertEqual((self.destination / "python/current").read_bytes(), b"executable")
        self.assertEqual(executable.stat().st_mode & 0o7777, 0o700)
        self.assertEqual(self.destination.stat().st_mode & 0o777, 0o700)

    def test_rejects_unsafe_entries_and_removes_partial_staging(self):
        for name, kind, payload in (
            ("../outside", tarfile.REGTYPE, b"bad"),
            ("/absolute", tarfile.REGTYPE, b"bad"),
            ("python/../../outside", tarfile.REGTYPE, b"bad"),
            ("python/device", tarfile.CHRTYPE, ""),
            ("python/fifo", tarfile.FIFOTYPE, ""),
            ("python/hardlink", tarfile.LNKTYPE, "../outside"),
            ("python/escape", tarfile.SYMTYPE, "../../outside"),
            ("python/absolute", tarfile.SYMTYPE, "/etc/passwd"),
        ):
            with self.subTest(name=name, kind=kind):
                make_archive(self.archive, [
                    ("python/valid", tarfile.REGTYPE, b"valid"),
                    (name, kind, payload),
                ])
                with self.assertRaises(ExtractionError):
                    extract_runtime(self.archive, self.destination)
                self.assertFalse(self.destination.exists())
                self.assertFalse((self.root / "outside").exists())

    def test_rejects_link_ancestors_duplicates_and_cyclic_links(self):
        cases = [
            [("link", tarfile.SYMTYPE, "."), ("link/file", tarfile.REGTYPE, b"bad")],
            [("same", tarfile.REGTYPE, b"first"), ("same", tarfile.REGTYPE, b"second")],
            [("a", tarfile.SYMTYPE, "b"), ("b", tarfile.SYMTYPE, "a")],
            [("a", tarfile.SYMTYPE, "."), ("b", tarfile.SYMTYPE, "a/../outside")],
        ]
        for entries in cases:
            with self.subTest(entries=entries):
                make_archive(self.archive, entries)
                with self.assertRaises(ExtractionError):
                    extract_runtime(self.archive, self.destination)
                self.assertFalse(self.destination.exists())

    def test_existing_destination_is_never_modified(self):
        self.destination.mkdir()
        sentinel = self.destination / "keep"
        sentinel.write_bytes(b"existing")
        make_archive(self.archive, [("new", tarfile.REGTYPE, b"new")])
        with self.assertRaises(FileExistsError):
            extract_runtime(self.archive, self.destination)
        self.assertEqual(list(self.destination.iterdir()), [sentinel])
        self.assertEqual(sentinel.read_bytes(), b"existing")

    def test_expansion_and_member_limits_remove_staging(self):
        make_archive(self.archive, [
            ("one", tarfile.REGTYPE, b"1234"), ("two", tarfile.REGTYPE, b"5678"),
        ])
        for limits in (
            ExtractionLimits(members=1), ExtractionLimits(file_bytes=3),
            ExtractionLimits(total_bytes=7),
        ):
            with self.subTest(limits=limits), self.assertRaises(ExtractionError):
                extract_runtime(self.archive, self.destination, limits)
            self.assertFalse(self.destination.exists())

    def test_corrupt_archive_leaves_no_staging(self):
        self.archive.write_bytes(b"not a gzip archive")
        with self.assertRaises(ExtractionError):
            extract_runtime(self.archive, self.destination)
        self.assertFalse(self.destination.exists())
