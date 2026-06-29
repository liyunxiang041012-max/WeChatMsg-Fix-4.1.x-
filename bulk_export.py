#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Bulk export all WeChat contacts to TXT

LC044/WeChatMsg (留痕 MemoTrace) 配套工具 | 原作者: SiYuan
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

# Fix encoding for terminal output
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from wxManager import DatabaseConnection
from exporter.config import FileType
from exporter import TxtExporter

# Auto-detect decrypted DB directory (any wxid_* folder)
decrypted_dir = None
for item in os.listdir('.'):
    if item.startswith('wxid_') and os.path.isdir(item):
        candidate = os.path.join(item, 'db_storage')
        if os.path.exists(candidate):
            decrypted_dir = candidate
            break
if not decrypted_dir:
    print('[!] No decrypted DB found. Run auto_extract.py + verify_key.py first.')
    print('    Or set decrypted_dir manually.')
    exit(1)
export_dir = 'export_final/txt'

print(f'[+] Connecting to DB...')
conn = DatabaseConnection(decrypted_dir, 4)
db = conn.get_interface()
contacts = db.get_contacts()
print(f'[+] {len(contacts)} contacts loaded')

os.makedirs(export_dir, exist_ok=True)
ok = 0

for i, c in enumerate(contacts):
    name = c.remark or c.nickname or c.wxid
    if not name or name == 'unknown':
        continue
    try:
        TxtExporter(db, c, output_dir=export_dir, type_=FileType.TXT,
                   message_types=None, time_range=None, group_members=None).start()
        ok += 1
        if ok % 50 == 0:
            print(f'  [{ok}/{len(contacts)}] {name}')
    except Exception as e:
        print(f'  FAIL: {name} - {e}')

print(f'\n[+] DONE! {ok} contacts exported to {export_dir}')
