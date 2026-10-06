import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

root=Path(__file__).resolve().parent.parent
source=Path(os.getenv('SIMKEEP_DB',str(root/'data'/'simkeep.db'))).resolve()
if not source.is_file():
    raise SystemExit('数据库尚未创建')
directory=source.parent/'backups'
directory.mkdir(mode=0o700,exist_ok=True)
target=directory/f"simkeep-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')}.db"
fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
os.close(fd)
with sqlite3.connect(f'{source.as_uri()}?mode=ro',uri=True) as original,sqlite3.connect(target) as backup:
    original.backup(backup)
print(f'备份完成：{target}')
