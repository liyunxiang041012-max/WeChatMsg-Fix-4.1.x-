#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
微信密钥自动提取 - 杀微信 -> 重启 -> 注入Hook -> 等你登录 -> 捕获密钥

LC044/WeChatMsg (留痕 MemoTrace) 配套工具 | 原作者: SiYuan
依赖: wx_key.dll (https://github.com/ycccccccy/wx_key)

用法:
    1. 以管理员身份运行本脚本
    2. 脚本自动杀微信、重启、注入Hook
    3. 看到 "Hook就绪" 提示后，在微信登录窗口扫码/点登录
    4. 密钥自动保存到 wechat_db_key.txt
"""
import ctypes, time, os, sys, subprocess, psutil

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except:
    pass

DLL = r'C:\wx_key_extracted\data\flutter_assets\assets\dll\wx_key.dll'
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def log(msg):
    print(msg, flush=True)

# ========== Step 1: Kill WeChat ==========
log('=' * 60)
log(' [1/5] 关闭微信...')
log('=' * 60)
os.system('taskkill /f /im Weixin.exe 2>nul')
for _ in range(30):
    alive = [p for p in psutil.process_iter(['name']) if p.info['name'] and p.info['name'].lower() == 'weixin.exe']
    if not alive:
        log(' [+] 微信已关闭')
        break
    time.sleep(1)
else:
    log(' [!] 无法关闭微信，请手动退出后重试')
    sys.exit(1)
time.sleep(3)

# ========== Step 2: Start WeChat ==========
log('\n[2/5] 启动微信...')
wechat_exe = None
candidates = [
    r'D:\sofa\Weixin\Weixin.exe',
    os.path.expandvars(r'%ProgramFiles%\Tencent\Weixin\Weixin.exe'),
    os.path.expandvars(r'%ProgramFiles(x86)%\Tencent\Weixin\Weixin.exe'),
    os.path.expandvars(r'%LOCALAPPDATA%\Programs\Weixin\Weixin.exe'),
]
for p in candidates:
    if os.path.exists(p):
        wechat_exe = p
        break
if not wechat_exe:
    log(' [!] 找不到 Weixin.exe！请手动输入路径')
    wechat_exe = input(' 微信路径: ').strip()
    if not os.path.exists(wechat_exe):
        log(' [!] 路径不存在，退出')
        sys.exit(1)

log(f' [+] 启动: {wechat_exe}')
subprocess.Popen([wechat_exe], shell=True)
time.sleep(5)  # 等一会让进程启动

# ========== Step 3: Find PID & Install Hook ==========
log('\n[3/5] 查找微信主进程并注入Hook...')
pid = None
for attempt in range(60):
    for p in psutil.process_iter(['pid', 'name']):
        if p.info['name'] and p.info['name'].lower() == 'weixin.exe':
            try:
                proc = psutil.Process(p.info['pid'])
                for m in proc.memory_maps():
                    if 'weixin.dll' in m.path.lower():
                        pid = p.info['pid']
                        break
            except:
                pass
            if pid:
                break
    if pid:
        break
    time.sleep(2)

if not pid:
    # 回退
    for p in psutil.process_iter(['pid', 'name']):
        if p.info['name'] and p.info['name'].lower() == 'weixin.exe':
            pid = p.info['pid']
            break
if not pid:
    log(' [!] 找不到微信进程')
    sys.exit(1)

log(f' [+] 目标 PID: {pid}')

# Load DLL
os.chdir(os.path.dirname(DLL))
wxkey = ctypes.CDLL(DLL)
wxkey.InitializeHook.argtypes = [ctypes.c_ulong]
wxkey.InitializeHook.restype = ctypes.c_bool
wxkey.PollKeyData.argtypes = [ctypes.c_char_p, ctypes.c_int]
wxkey.PollKeyData.restype = ctypes.c_bool
wxkey.GetStatusMessage.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
wxkey.GetStatusMessage.restype = ctypes.c_bool
wxkey.CleanupHook.argtypes = []
wxkey.CleanupHook.restype = ctypes.c_bool

# Install hook
result = wxkey.InitializeHook(pid)
if not result:
    log(' [!] Hook 注入失败')
    wxkey.CleanupHook()
    sys.exit(1)
log(' [+] Hook 注入成功')

# ========== Step 4: Wait for hook to be ready ==========
log('\n[4/5] 等待Hook就绪（不要登录！）...')
last_status = ''
for attempt in range(180):
    buf = ctypes.create_string_buffer(512)
    lvl = ctypes.c_int()
    wxkey.GetStatusMessage(buf, 512, ctypes.byref(lvl))
    status = buf.value.decode('utf-8', errors='replace').strip()

    if status != last_status and status:
        print(f'  [{attempt}s] {status}')
        last_status = status

    # Check for "ready" or "installed" keywords
    if any(kw in status for kw in ['Hook安装成功', 'hook installed', 'ready', '就绪', '登录微信', '等待登录']):
        log('\n' + '=' * 60)
        log(' ⭐ Hook就绪！现在去微信登录窗口扫码/点登录！')
        log('=' * 60)
        break

    time.sleep(1)
else:
    log('\n [!] Hook 初始化超时')

# ========== Step 5: Poll for key ==========
log('\n[5/5] 等待密钥（正在登录微信中...）\n')
key_found = False
key_hex = ''
for attempt in range(120):
    buf = ctypes.create_string_buffer(256)
    ok = wxkey.PollKeyData(buf, 256)

    if attempt % 5 == 0:
        s = ctypes.create_string_buffer(512)
        lvl = ctypes.c_int()
        wxkey.GetStatusMessage(s, 512, ctypes.byref(lvl))
        st = s.value.decode('utf-8', errors='replace').strip()
        if st and st != last_status:
            print(f'  [{attempt}s] {st}')
            last_status = st

    if ok and buf.value:
        data = buf.value.decode('utf-8', errors='replace').strip()
        if len(data) >= 64:
            key_hex = data
            key_found = True
            log(f'\n [+] ✅ 密钥捕获！{key_hex[:16]}...{key_hex[-16:]}')
            break

    time.sleep(1)

# ========== Save ==========
if key_found:
    with open(os.path.join(SCRIPT_DIR, 'wechat_db_key.txt'), 'w') as f:
        f.write(key_hex)
    log(f' [+] 密钥已保存到 wechat_db_key.txt')
else:
    log('\n [!] 未捕获到密钥')
    log('    请重试，或在微信登录窗口出现后再运行本脚本')

wxkey.CleanupHook()
log('\n [+] 完成！')
