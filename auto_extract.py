#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WeChat DB Key Auto-Extractor (wx_key DLL injection)

Kill WeChat -> Install Hook -> Restart WeChat -> Capture DB key

这是 LC044/WeChatMsg (留痕 MemoTrace) 项目的配套工具。
原作者: SiYuan (https://github.com/LC044)

依赖: wx_key.dll (https://github.com/ycccccccy/wx_key)
"""
import ctypes
import time
import os
import sys
import subprocess
import psutil

dll_path = r'C:\wx_key_extracted\data\flutter_assets\assets\dll\wx_key.dll'

print('=' * 60)
print(' WeChat DB Key Auto-Extractor')
print('=' * 60)

# 1. Kill existing WeChat
print('\n[1/6] Killing WeChat...')
os.system('taskkill /f /im Weixin.exe 2>nul')
for i in range(30):
    alive = any(p.name().lower() == 'weixin.exe' for p in psutil.process_iter(['name']))
    if not alive:
        print(f'[+] WeChat closed')
        break
    time.sleep(1)
else:
    print('[!] Failed to kill WeChat')
    sys.exit(1)

# 2. Start WeChat
print('\n[2/6] Starting WeChat...')
wechat_paths = [r'D:\sofa\Weixin\Weixin.exe']
wechat_exe = None
for p in wechat_paths:
    if os.path.exists(p):
        wechat_exe = p
        break
if not wechat_exe:
    print('[!] Cannot find Weixin.exe')
    sys.exit(1)

print(f'[+] Launching: {wechat_exe}')
subprocess.Popen([wechat_exe], shell=True)

# 3. Wait for WeChat to fully initialize with Weixin.dll loaded
print('\n[3/6] Waiting for WeChat to stabilize (Weixin.dll loaded)...')
pid = None

# Wait for WeChat process that HAS Weixin.dll loaded
for attempt in range(60):
    wechat_pids = []
    for p in psutil.process_iter(['pid', 'name']):
        if p.info['name'] and p.info['name'].lower() == 'weixin.exe':
            try:
                proc = psutil.Process(p.info['pid'])
                # Check if this process has Weixin.dll loaded
                for m in proc.memory_maps():
                    if 'weixin.dll' in m.path.lower():
                        # This is the REAL WeChat process
                        wechat_pids.append((p.info['pid'], True))
                        break
                else:
                    wechat_pids.append((p.info['pid'], False))
            except:
                pass
    
    real_pids = [p for p, has_dll in wechat_pids if has_dll]
    if real_pids:
        pid = real_pids[-1]
        print(f'[+] Found WeChat with Weixin.dll: PID {pid}')
        time.sleep(3)
        if psutil.pid_exists(pid):
            print(f'[+] PID {pid} confirmed stable')
            break
        else:
            pid = None
    
    if attempt % 5 == 0:
        all_pids = [str(p) for p, _ in wechat_pids]
        print(f'  [{attempt}s] WeChat PIDs: {all_pids}' + (f', with DLL: {real_pids}' if real_pids else ', no Weixin.dll yet'))
    time.sleep(2)

if not pid:
    print('[!] Could not find stable WeChat process with Weixin.dll')
    print('[!] Trying to hook ALL WeChat processes anyway...')
    # Fallback: find any WeChat process
    for p in psutil.process_iter(['pid', 'name']):
        if p.info['name'] and p.info['name'].lower() == 'weixin.exe':
            pid = p.info['pid']
            if psutil.pid_exists(pid):
                break

if not pid:
    print('[!] No WeChat process found')
    sys.exit(1)

# 4. Load DLL
print('\n[4/6] Loading wx_key.dll...')
os.chdir(os.path.dirname(dll_path))
wxkey = ctypes.CDLL(dll_path)

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

# Try hooking ALL WeChat processes (WeChat spawns multiple)
all_wechat_pids = []
for p in psutil.process_iter(['pid', 'name']):
    if p.info['name'] and p.info['name'].lower() == 'weixin.exe':
        try:
            if psutil.pid_exists(p.info['pid']):
                all_wechat_pids.append(p.info['pid'])
        except:
            pass

print(f'[+] All WeChat PIDs: {all_wechat_pids}')

# Try each PID until one succeeds
result = False
for target_pid in all_wechat_pids:
    for retry in range(2):
        print(f'[+] Trying PID {target_pid} (attempt {retry+1})...')
        result = wxkey.InitializeHook(target_pid)
        print(f'[+] InitializeHook = {result}')
        if result:
            pid = target_pid
            break
        err = wxkey.GetLastErrorMsg()
        err_str = err.decode('utf-8', errors='replace') if err else 'unknown'
        print(f'[!] Error: {err_str}')
        if retry < 1:
            time.sleep(3)
    if result:
        break

if not result:
    print('[!] InitializeHook failed for all PIDs')
    sys.exit(1)

# Show initial status
def get_status():
    buf = ctypes.create_string_buffer(512)
    lvl = ctypes.c_int()
    wxkey.GetStatusMessage(buf, 512, ctypes.byref(lvl))
    return buf.value.decode('utf-8', errors='replace').strip()

print(f'[+] Initial status: {get_status()}')

# 5. Wait for WeChat to auto-login and open DBs
print('\n[5/6] Waiting for WeChat login...')
print('[+] The hook will capture the key when WeChat opens databases during login')
print('[+] If auto-login fails, please manually click Login/scan QR code')

key_found = False
key_hex = ''
last_status = ''

# Wait a bit for hook installation to complete in remote process
time.sleep(5)

for attempt in range(300):  # Up to 5 minutes
    buf = ctypes.create_string_buffer(256)
    ok = wxkey.PollKeyData(buf, 256)
    
    if attempt % 10 == 0:
        s = get_status()
        if s != last_status:
            print(f'  [{attempt}s] {s}')
            last_status = s
    
    if ok and buf.value:
        data = buf.value.decode('utf-8', errors='replace').strip()
        if data:
            key_hex = data
            key_found = True
            print(f'\n[+] *** KEY CAPTURED at {attempt}s! ***')
            print(f'[+] Key (hex): {key_hex}')
            break
    
    time.sleep(1)

# 6. Save and cleanup
print('\n[6/6] Saving...')

if key_found:
    base = r'd:\浏览器下载\WeChatMsg-master'
    with open(os.path.join(base, 'wechat_db_key.txt'), 'w') as f:
        f.write(key_hex)
    print(f'[+] Key saved to wechat_db_key.txt')
    
    try:
        key_bytes = bytes.fromhex(key_hex)
        print(f'[+] Key ({len(key_bytes)} bytes): {key_bytes.hex()}')
        with open(os.path.join(base, 'wechat_db_key.bin'), 'wb') as f:
            f.write(key_bytes)
    except:
        print('[!] Could not decode key as hex')
else:
    print('[!] Key not captured')
    print(f'[!] Final status: {get_status()}')

wxkey.CleanupHook()
print('[+] Done!')
