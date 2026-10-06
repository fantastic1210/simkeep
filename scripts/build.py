"""Publish only browser assets. Server files, databases and .env are never copied."""
import argparse
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
ASSETS=('index.html','style.css','app.js','api.js','core.js','money.js','countries.js','favicon.svg')
parser=argparse.ArgumentParser()
parser.add_argument('--output',default='dist')
args=parser.parse_args()
target=(ROOT/args.output).resolve()
if target.parent!=ROOT or target.name not in ('dist','preview'):
    parser.error('output must be dist or preview in this project')
for asset in ASSETS:
    if not (ROOT/asset).is_file():
        raise SystemExit(f'Missing asset: {asset}')
target.mkdir(exist_ok=True)
for asset in target.iterdir():
    if asset.is_file() and asset.name not in ASSETS:
        asset.unlink()
for asset in ASSETS:
    temp=target/(asset+'.next')
    shutil.copyfile(ROOT/asset,temp)
    temp.replace(target/asset)
print(f'Published {len(ASSETS)} browser assets to {target}')
