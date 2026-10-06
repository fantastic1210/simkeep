import io
import sqlite3
import tempfile
import unittest
from pathlib import Path

from server.db import Database

try:
    from scripts.restore import restore_database
except ImportError:
    restore_database=None


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(restore_database,'Container restore must work as the application user')
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        original=self.root/'backup.db'
        db=Database(original)
        with db.connect(write=True) as conn:
            conn.execute('INSERT INTO system_state VALUES(?,?)',('restore-fixture','preserved'))
        self.incoming=original.read_bytes()
        self.destination=self.root/'data'/'simkeep.db'

    def test_stream_import_preserves_database_contents_and_private_mode(self):
        restore_database(self.destination,io.BytesIO(self.incoming))
        with sqlite3.connect(self.destination) as conn:
            self.assertEqual(conn.execute('SELECT value FROM system_state WHERE key=?',('restore-fixture',)).fetchone()[0],'preserved')
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        self.assertEqual(self.destination.stat().st_mode&0o777,0o600)

    def test_existing_database_requires_explicit_replace(self):
        restore_database(self.destination,io.BytesIO(self.incoming))
        before=self.destination.read_bytes()
        with self.assertRaises(ValueError):
            restore_database(self.destination,io.BytesIO(self.incoming))
        self.assertEqual(self.destination.read_bytes(),before)

    def test_invalid_or_unrelated_backup_preserves_existing_database(self):
        restore_database(self.destination,io.BytesIO(self.incoming))
        before=self.destination.read_bytes()
        other=self.root/'other.db'
        with sqlite3.connect(other) as conn:
            conn.execute('CREATE TABLE unrelated(value TEXT)')
        for incoming in (b'not a database',b'',other.read_bytes()):
            with self.subTest(incoming_size=len(incoming)),self.assertRaises(ValueError):
                restore_database(self.destination,io.BytesIO(incoming),replace=True)
            self.assertEqual(self.destination.read_bytes(),before)

    def test_explicit_restore_removes_old_sidecars_and_replaces_contents(self):
        restore_database(self.destination,io.BytesIO(self.incoming))
        with sqlite3.connect(self.destination) as conn:
            conn.execute('DELETE FROM system_state')
        for suffix in ('-wal','-shm'):
            Path(str(self.destination)+suffix).write_bytes(b'old stopped database sidecar')
        restore_database(self.destination,io.BytesIO(self.incoming),replace=True)
        for suffix in ('-wal','-shm'):
            self.assertFalse(Path(str(self.destination)+suffix).exists())
        with sqlite3.connect(self.destination) as conn:
            self.assertEqual(conn.execute('SELECT value FROM system_state').fetchone()[0],'preserved')
