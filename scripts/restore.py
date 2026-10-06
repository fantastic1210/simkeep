"""Restore a consistent SIMKEEP backup from stdin while the application is stopped."""
import argparse
import os
import shutil
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

TABLES={'users','sessions','cards','events','bindings','notification_jobs','system_state'}


def restore_database(destination,stream,replace=False):
    destination=Path(destination).resolve()
    if destination.exists() and not replace:
        raise ValueError('数据库已存在；先备份并停止应用，确认替换后使用 --replace')
    staged=None
    try:
        with tempfile.TemporaryDirectory(prefix='simkeep-import-') as directory:
            incoming=Path(directory)/'backup.db'
            with incoming.open('wb') as target:
                shutil.copyfileobj(stream,target)
            if incoming.stat().st_size==0:
                raise ValueError('备份为空，数据库未修改')
            with closing(sqlite3.connect(f'{incoming.as_uri()}?mode=ro',uri=True)) as source:
                if source.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                    raise ValueError('备份完整性检查失败，数据库未修改')
                tables={row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if not TABLES.issubset(tables):
                    raise ValueError('请选择完整的 SIMKEEP 数据库备份，数据库未修改')
                destination.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                with tempfile.NamedTemporaryFile(prefix='.simkeep-restore-',suffix='.db',dir=destination.parent,delete=False) as target:
                    staged=Path(target.name)
                with closing(sqlite3.connect(staged)) as target:
                    source.backup(target)
                    if target.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                        raise ValueError('恢复文件完整性检查失败，数据库未修改')
            staged.chmod(0o600)
            for suffix in ('-wal','-shm'):
                Path(str(destination)+suffix).unlink(missing_ok=True)
            staged.replace(destination)
    except sqlite3.DatabaseError:
        raise ValueError('备份格式无效或已损坏，数据库未修改') from None
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replace',action='store_true',help='明确替换现有数据库；须先备份并停止应用')
    args=parser.parse_args()
    root=Path(__file__).resolve().parent.parent
    destination=os.getenv('SIMKEEP_DB',str(root/'data'/'simkeep.db'))
    try:
        restore_database(destination,sys.stdin.buffer,args.replace)
    except (ValueError,OSError) as error:
        parser.exit(1,f'恢复失败：{error}\n')
    print('数据库恢复完成')
