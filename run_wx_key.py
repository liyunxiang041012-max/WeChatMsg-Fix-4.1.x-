#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
一键提取微信数据库密钥 — 自动注入 wx_key.dll，保存到 wechat_db_key.txt

LC044/WeChatMsg (留痕 MemoTrace) 配套工具 | 原作者: SiYuan
依赖: wx_key.dll (https://github.com/ycccccccy/wx_key)

用法:
    1. 登录微信 (Weixin.exe)
    2. 以管理员身份运行本脚本
    3. 密钥自动保存到同目录 wechat_db_key.txt
    4. 打开 GUI 点击「检测微信」→ 自动加载密钥
"""
import ctypes
import time
import os
import sys
import psutil

# === PowerShell 编码修复 ===
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except:
    pass

# === 查找 wx_key.dll ===
DLL_CANDIDATES = [
    r'C:\wx_key_extracted\data\flutter_assets\assets\dll\wx_key.dll',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wx_key.dll'),
]
dll_path = None
for p in DLL_CANDIDATES:
    if os.path.exists(p):
        dll_path = p
        break

if not dll_path:
    print('[X] 未找到 wx_key.dll！')
    print('    请将 wx_key.dll 放到本脚本同目录')
    print('    或从 https://github.com/ycccccccy/wx_key 下载')
    input('按回车退出...')
    sys.exit(1)

print('=' * 60)
print(' 微信数据库密钥提取工具')
print('=' * 60)
print(f' DLL: {dll_path}')

# === 查找微信主进程（必须加载了 Weixin.dll） ===
print('\n[1/4] 查找微信主进程...')
pid = None
found_pids = []
for p in psutil.process_iter(['pid', 'name']):
    if p.info['name'] and p.info['name'].lower() == 'weixin.exe':
        try:
            proc = psutil.Process(p.info['pid'])
            has_dll = any('weixin.dll' in m.path.lower() for m in proc.memory_maps())
            found_pids.append((p.info['pid'], has_dll))
            if has_dll and pid is None:
                pid = p.info['pid']
        except:
            found_pids.append((p.info['pid'], False))

pid_labels = []
for p, d in found_pids:
    label = f"PID {p}(主进程)" if d else f"PID {p}"
    pid_labels.append(label)
print(f' 微信进程: {", ".join(pid_labels)}')

if not pid:
    print('[X] 未找到微信主进程（无 Weixin.dll）！请确认微信已登录')
    input('按回车退出...')
    sys.exit(1)

print(f' [+] 目标: PID {pid} (Weixin.dll 已加载)')

# === 加载 DLL ===
print('\n[2/4] 加载 wx_key.dll...')
try:
    os.chdir(os.path.dirname(dll_path))
    wxkey = ctypes.CDLL(dll_path)
except Exception as e:
    print(f'[X] 加载失败: {e}')
    input('按回车退出...')
    sys.exit(1)

wxkey.InitializeHook.argtypes = [ctypes.c_ulong]
wxkey.InitializeHook.restype = ctypes.c_bool
wxkey.PollKeyData.argtypes = [ctypes.c_char_p, ctypes.c_int]
wxkey.PollKeyData.restype = ctypes.c_bool
wxkey.GetStatusMessage.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
wxkey.GetStatusMessage.restype = ctypes.c_bool
wxkey.CleanupHook.argtypes = []
wxkey.CleanupHook.restype = ctypes.c_bool
wxkey.GetLastErrorMsg.argtypes = []
wxkey.GetLastErrorMsg.restype = ctypes.c_char_p

# === 注入 Hook ===
print('\n[3/4] 注入 Hook...')
result = wxkey.InitializeHook(pid)
if not result:
    err = wxkey.GetLastErrorMsg()
    err_str = err.decode('utf-8', errors='replace') if err else '未知错误'
    print(f'[X] Hook 失败: {err_str}')
    print('    请确保以管理员身份运行本脚本')
    wxkey.CleanupHook()
    input('按回车退出...')
    sys.exit(1)

print(' [+] Hook 注入成功！')

# === 等待密钥 ===
print('\n[4/4] 等待密钥（请在微信中打开任意聊天窗口触发数据库访问）...')
print('-' * 40)

key_hex = ''
last_status = ''
for attempt in range(120):  # 最多等 2 分钟
    buf = ctypes.create_string_buffer(256)
    ok = wxkey.PollKeyData(buf, 256)

    if attempt % 10 == 0:
        sbuf = ctypes.create_string_buffer(512)
        lvl = ctypes.c_int()
        wxkey.GetStatusMessage(sbuf, 512, ctypes.byref(lvl))
        status = sbuf.value.decode('utf-8', errors='replace').strip()
        if status != last_status:
            print(f'  [{attempt:3d}s] {status}')
            last_status = status

    if ok and buf.value:
        data = buf.value.decode('utf-8', errors='replace').strip()
        if data and len(data) == 64:
            key_hex = data
            break

    time.sleep(1)

wxkey.CleanupHook()

if not key_hex:
    print('\n[X] 超时：未捕获到密钥')
    print('    请确保在 Hook 注入后打开了微信聊天窗口或收藏夹')
    input('按回车退出...')
    sys.exit(1)

# === 保存密钥 ===
print('-' * 40)
print(f'\n [+] 密钥: {key_hex}')

out_dir = os.path.dirname(os.path.abspath(__file__))
key_file = os.path.join(out_dir, 'wechat_db_key.txt')
with open(key_file, 'w') as f:
    f.write(key_hex)
print(f' [+] 已保存: {key_file}')

print('\n' + '=' * 60)
print(' 完成！现在打开 GUI 点击「检测微信」即可自动加载密钥')
print('=' * 60)

# 自动打开 GUI
gui_path = os.path.join(out_dir, 'gui_app.py')
if os.path.exists(gui_path):
    try:
        input('\n按回车打开 GUI...')
        os.startfile(gui_path)
    except:
        pass
else:
    input('\n按回车退出...')
