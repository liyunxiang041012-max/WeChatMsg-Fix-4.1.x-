#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
wx_key.dll Python wrapper - Extract WeChat DB key via DLL injection

LC044/WeChatMsg (留痕 MemoTrace) 配套工具 | 原作者: SiYuan
依赖: wx_key.dll (https://github.com/ycccccccy/wx_key)
"""
import ctypes
import time
import os
import sys
import psutil

dll_path = r'C:\wx_key_extracted\data\flutter_assets\assets\dll\wx_key.dll'

print('=' * 60)
print(' WeChat DB Key Extractor (wx_key.dll v2.1.8)')
print('=' * 60)

# Step 1: Find WeChat PID (must be the one with Weixin.dll loaded)
print('\n[1] Finding WeChat process...')
pid = None
for p in psutil.process_iter(['pid', 'name']):
    if p.info['name'] and p.info['name'].lower() == 'weixin.exe':
        try:
            proc = psutil.Process(p.info['pid'])
            if any('weixin.dll' in m.path.lower() for m in proc.memory_maps()):
                pid = p.info['pid']
                break
        except:
            pass

if not pid:
    print('[!] WeChat (Weixin.exe) is not running!')
    print('[!] Please start WeChat first.')
    sys.exit(1)

print(f'[+] WeChat PID: {pid}')

# Step 2: Load DLL (use CDLL for __cdecl calling convention)
print('\n[2] Loading wx_key.dll...')
os.chdir(os.path.dirname(dll_path))
wxkey = ctypes.CDLL(dll_path)  # CDLL for __cdecl

# Define function signatures exactly as documented
wxkey.InitializeHook.argtypes = [ctypes.c_ulong]  # DWORD targetPid
wxkey.InitializeHook.restype = ctypes.c_bool

wxkey.PollKeyData.argtypes = [ctypes.c_char_p, ctypes.c_int]  # char* keyBuffer, int bufferSize
wxkey.PollKeyData.restype = ctypes.c_bool

wxkey.GetStatusMessage.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]  # buffer, size, outLevel
wxkey.GetStatusMessage.restype = ctypes.c_bool

wxkey.CleanupHook.argtypes = []
wxkey.CleanupHook.restype = ctypes.c_bool

wxkey.GetLastErrorMsg.argtypes = []
wxkey.GetLastErrorMsg.restype = ctypes.c_char_p

# Step 3: Initialize hook
print('\n[3] Initializing hook...')
result = wxkey.InitializeHook(pid)
print(f'[+] InitializeHook({pid}) = {result}')

if not result:
    err = wxkey.GetLastErrorMsg()
    if err:
        print(f'[!] Error: {err.decode("utf-8", errors="replace")}')
    else:
        print('[!] Unknown error - check admin privileges')
    sys.exit(1)

# Also check status
status_buf = ctypes.create_string_buffer(512)
out_level = ctypes.c_int()
wxkey.GetStatusMessage(status_buf, 512, ctypes.byref(out_level))
print(f'[+] Status: {status_buf.value.decode("utf-8", errors="replace").strip()}')

# Step 4: Poll for key
print('\n[4] Polling for key (navigate WeChat to trigger DB access)...')
print('[+] This may take a moment - try opening a chat or Favorites in WeChat...')

key_found = False
key_hex = ''

for attempt in range(60):
    buf = ctypes.create_string_buffer(256)
    ok = wxkey.PollKeyData(buf, 256)
    
    # Get status every 5 attempts
    if attempt % 5 == 0:
        status_buf = ctypes.create_string_buffer(512)
        out_level = ctypes.c_int()
        wxkey.GetStatusMessage(status_buf, 512, ctypes.byref(out_level))
        status = status_buf.value.decode('utf-8', errors='replace').strip()
        print(f'  [{attempt}s] Status: {status}')
    
    if ok and buf.value:
        data = buf.value.decode('utf-8', errors='replace').strip()
        if data:
            key_hex = data
            key_found = True
            print(f'\n[+] KEY CAPTURED at {attempt}s!')
            print(f'[+] Key: {key_hex}')
            break
    
    time.sleep(1)

# Step 5: Save key and cleanup
print('\n[5] Saving results...')

if key_found:
    # Save to file
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wechat_db_key.txt')
    with open(out_path, 'w') as f:
        f.write(key_hex)
    print(f'[+] Key saved to: {out_path}')
    
    # Convert to binary
    try:
        key_bytes = bytes.fromhex(key_hex)
        print(f'[+] Key length: {len(key_bytes)} bytes')
        print(f'[+] Key (hex): {key_bytes.hex()}')
        
        bin_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wechat_db_key.bin')
        with open(bin_path, 'wb') as f:
            f.write(key_bytes)
        print(f'[+] Binary key saved to: {bin_path}')
    except Exception as e:
        print(f'[!] Hex conversion error: {e}')
else:
    print('[!] Key not captured within 60 seconds.')
    status_buf = ctypes.create_string_buffer(512)
    out_level = ctypes.c_int()
    wxkey.GetStatusMessage(status_buf, 512, ctypes.byref(out_level))
    print(f'[!] Final status: {status_buf.value.decode("utf-8", errors="replace").strip()}')

# Step 6: Cleanup
print('\n[6] Cleaning up hook...')
wxkey.CleanupHook()
print('[+] Done!')
