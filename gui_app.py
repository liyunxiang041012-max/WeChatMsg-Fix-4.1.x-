#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WeChatMsg - 微信聊天记录导出工具 (GUI版)

基于 LC044/WeChatMsg (留痕 MemoTrace) 修改
原作者: SiYuan (https://github.com/LC044)
官网: https://memotrace.cn/

修改内容: 重写 GUI 为 tkinter 卡片式布局，增加微信 4.1.x 密钥手动输入及 wx_key 自动加载支持
"""
# ⚠️ 多进程支持必须在所有 import 之前！否则 PyInstaller 打包后会弹多个窗口
import multiprocessing
multiprocessing.freeze_support()

import ctypes
import json
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from wxManager import Me, DatabaseConnection
from wxManager.model.contact import Contact

# ==================== 主题配色 ====================
WECHAT_GREEN = '#07C160'
WECHAT_GREEN_DARK = '#06AD56'
WECHAT_GREEN_LIGHT = '#E8F8EF'
BLUE = '#1989FA'
BLUE_DARK = '#1677D9'
ORANGE = '#FF9800'
RED = '#F44336'
DARK_BG = '#1E1E1E'
DARK_LOG_BG = '#2D2D30'
WHITE = '#FFFFFF'
LIGHT_GRAY = '#F5F5F5'
MID_GRAY = '#E0E0E0'
TEXT_DARK = '#1A1A1A'
TEXT_GRAY = '#888888'
TEXT_LIGHT = '#B0B0B0'

STATUS_COLORS = {
    'success': '#07C160',
    'warning': '#FF9800',
    'error': '#F44336',
    'info': '#1989FA',
}

FONT_TITLE = ('Microsoft YaHei UI', 16, 'bold')
FONT_HEADING = ('Microsoft YaHei UI', 12, 'bold')
FONT_BODY = ('Microsoft YaHei UI', 10)
FONT_SMALL = ('Microsoft YaHei UI', 9)
FONT_MONO = ('Cascadia Code', 9)

# ---------- 工具函数 ----------
def get_wechat_info():
    """检测微信并获取信息"""
    try:
        from wxManager.decrypt import get_info_v4, get_info_v3
        from wxManager.decrypt.decrypt_dat import get_decode_code_v4
    except ImportError as e:
        return [], str(e)

    results = []
    errors = []

    # 检测微信 4.0 (Weixin.exe) —— 只取第一个结果，避免遍历多个进程导致弹窗
    try:
        r4 = get_info_v4()
        for wx_info in r4:
            me = Me()
            me.wx_dir = wx_info.wx_dir
            me.wxid = wx_info.wxid
            me.name = wx_info.nick_name
            me.xor_key = get_decode_code_v4(wx_info.wx_dir) if wx_info.wx_dir else None
            results.append({
                'version': 4,
                'wxid': wx_info.wxid,
                'name': wx_info.nick_name,
                'wx_dir': wx_info.wx_dir,
                'key': wx_info.key,
                'me': me,
                'has_key': wx_info.errcode == 200 and bool(wx_info.key),
                'errcode': wx_info.errcode,
                'errmsg': wx_info.errmsg,
            })
            if not wx_info.key:
                msg = wx_info.errmsg or '未知错误'
                errors.append(f'微信4.0密钥提取失败 (errcode={wx_info.errcode}): {msg}')
            break  # 只取第一个账号
    except Exception as e:
        errors.append(f'检测微信4.0失败: {e}')

    # 检测微信 3.x (WeChat.exe)
    try:
        version_list_path = os.path.join(os.path.dirname(__file__), 'wxManager', 'decrypt', 'version_list.json')
        with open(version_list_path, "r", encoding="utf-8") as f:
            version_list = json.loads(f.read())
        r3 = get_info_v3(version_list)
        for wx_info in r3:
            me = Me()
            me.wx_dir = wx_info.wx_dir
            me.wxid = wx_info.wxid
            me.name = wx_info.nick_name
            results.append({
                'version': 3,
                'wxid': wx_info.wxid,
                'name': wx_info.nick_name,
                'wx_dir': wx_info.wx_dir,
                'key': wx_info.key,
                'me': me,
                'has_key': wx_info.errcode == 200 and bool(wx_info.key),
                'errcode': wx_info.errcode,
                'errmsg': wx_info.errmsg,
            })
            if not wx_info.key:
                msg = wx_info.errmsg or '未知错误'
                errors.append(f'微信3.x密钥提取失败 (errcode={wx_info.errcode}): {msg}')
    except Exception as e:
        errors.append(f'检测微信3.x失败: {e}')

    # ---- Fallback: load key from wx_key capture file if yara failed ----
    if results and not results[0].get('has_key'):
        key_file = os.path.join(os.path.dirname(__file__), 'wechat_db_key.txt')
        if os.path.exists(key_file):
            try:
                with open(key_file, 'r') as f:
                    saved_key = f.read().strip()
                if saved_key and len(saved_key) == 64:
                    results[0]['key'] = saved_key
                    results[0]['has_key'] = True
                    results[0]['errcode'] = 200
                    print("[+] Loaded key from wechat_db_key.txt (wx_key capture)")
                    errors.clear()
            except Exception:
                pass

    return results, errors


def decrypt_database(wx_info):
    """解密微信数据库"""
    from wxManager.decrypt import decrypt_v4, decrypt_v3

    output_dir = wx_info['wxid']
    key = wx_info['key']
    wx_dir = wx_info['wx_dir']

    if wx_info['version'] == 4:
        decrypt_v4.decrypt_db_files(key, src_dir=wx_dir, dest_dir=output_dir)
        db_path = output_dir  # decrypt_v4 mirrors wx_dir structure into output_dir directly
    else:
        decrypt_v3.decrypt_db_files(key, src_dir=wx_dir, dest_dir=output_dir)
        db_path = output_dir

    # 保存 info.json
    info_data = wx_info['me'].to_json()
    with open(os.path.join(db_path, 'info.json'), 'w', encoding='utf-8') as f:
        json.dump(info_data, f, ensure_ascii=False, indent=4)

    return db_path


# ---------- GUI ----------
class WeChatMsgApp:
    def __init__(self, root):
        self.root = root
        self.root.title("留痕 - 微信聊天记录导出工具")
        self.root.geometry("820x680")
        self.root.minsize(720, 560)
        self.root.configure(bg=LIGHT_GRAY)

        self._setup_ttk_style()

        self.wx_accounts = []
        self.selected_account = None
        self.db_path = None
        self.db_version = None
        self.database = None
        self.contacts = []
        self.selected_contacts = set()

        self._build_ui()

    def _setup_ttk_style(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('.', font=FONT_BODY)
        style.configure('TNotebook', background=LIGHT_GRAY, borderwidth=0)
        style.configure('TNotebook.Tab', font=FONT_HEADING, padding=[20, 8],
                        background=WHITE, borderwidth=0)
        style.map('TNotebook.Tab',
                  background=[('selected', WECHAT_GREEN), ('active', WECHAT_GREEN_LIGHT)],
                  foreground=[('selected', WHITE)],
                  expand=[('selected', [0, 0, 0, 0])])
        style.configure('Card.TFrame', background=WHITE, relief='solid', borderwidth=1)
        style.configure('Treeview', font=FONT_BODY, rowheight=32, borderwidth=0)
        style.configure('Treeview.Heading', font=FONT_HEADING, background=WHITE,
                        foreground=TEXT_DARK, borderwidth=0, padding=[8, 6])
        style.map('Treeview', background=[('selected', WECHAT_GREEN_LIGHT)],
                  foreground=[('selected', TEXT_DARK)])
        style.configure('Green.Horizontal.TProgressbar',
                        troughcolor=MID_GRAY, background=WECHAT_GREEN,
                        thickness=12, borderwidth=0)
        style.configure('TScrollbar', background=WHITE, arrowcolor=TEXT_GRAY,
                        troughcolor=LIGHT_GRAY, borderwidth=0)

    def _build_ui(self):
        # ========== 头部 ==========
        self.header_frame = tk.Frame(self.root, bg=WECHAT_GREEN, height=56)
        self.header_frame.pack(fill=tk.X)
        self.header_frame.pack_propagate(False)

        header_inner = tk.Frame(self.header_frame, bg=WECHAT_GREEN)
        header_inner.pack(expand=True)

        tk.Label(header_inner, text="💬", font=('Segoe UI Emoji', 16), bg=WECHAT_GREEN,
                 fg=WHITE).pack(side=tk.LEFT, padx=(0, 6))
        tk.Label(header_inner, text="留痕 · WeChatMsg", font=FONT_TITLE,
                 bg=WECHAT_GREEN, fg=WHITE).pack(side=tk.LEFT)
        tk.Label(header_inner, text="微信聊天记录导出工具",
                 font=('Microsoft YaHei UI', 9), bg=WECHAT_GREEN,
                 fg='#D4F5E4').pack(side=tk.LEFT, padx=(10, 0))

        # ========== 主内容 ==========
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        self.step1_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.step1_frame, text="  🔍  检测微信 & 解密  ")
        self._build_step1()

        self.step2_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.step2_frame, text="  👥  选择联系人  ")
        self._build_step2()

        self.step3_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.step3_frame, text="  📦  导出聊天记录  ")
        self._build_step3()

        # ========== 底部日志 ==========
        log_outer = tk.Frame(self.root, bg=DARK_LOG_BG, padx=2, pady=2)
        log_outer.pack(fill=tk.BOTH, padx=12, pady=(0, 12))

        log_header = tk.Frame(log_outer, bg=DARK_LOG_BG)
        log_header.pack(fill=tk.X, padx=10, pady=(6, 0))
        tk.Label(log_header, text="📋  运行日志", font=FONT_SMALL,
                 bg=DARK_LOG_BG, fg=TEXT_LIGHT).pack(side=tk.LEFT)
        self.log_status = tk.Label(log_header, text="●  就绪", font=FONT_SMALL,
                                    bg=DARK_LOG_BG, fg=WECHAT_GREEN)
        self.log_status.pack(side=tk.RIGHT)

        self.log_text = tk.Text(log_outer, height=7, wrap=tk.WORD, state=tk.DISABLED,
                                bg=DARK_LOG_BG, fg='#CCCCCC', insertbackground=WHITE,
                                font=('Cascadia Code', 9), relief='flat',
                                padx=10, pady=8, borderwidth=0,
                                selectbackground='#3A3D41', selectforeground=WHITE)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(self.log_text, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def log(self, msg):
        self.log_text.configure(state=tk.NORMAL)
        ts = time.strftime('%H:%M:%S')
        self.log_text.insert(tk.END, f"[{ts}] {msg}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)
        self.root.update_idletasks()

    def _set_log_status(self, text, color=WECHAT_GREEN):
        self.log_status.config(text=text, fg=color)

    def _new_card(self, parent):
        """创建卡片容器"""
        outer = tk.Frame(parent, bg=MID_GRAY, padx=1, pady=1)
        inner = tk.Frame(outer, bg=WHITE)
        inner.pack(fill=tk.BOTH, expand=True)
        return outer, inner

    def _flat_button(self, parent, text, color, command, font=FONT_BODY):
        """扁平日志风格按钮"""
        btn = tk.Button(parent, text=text, font=font, bg=color, fg=WHITE,
                        activebackground=color, activeforeground=WHITE,
                        relief='flat', cursor='hand2', padx=18, pady=8,
                        borderwidth=0, command=command)
        dark_color = self._darken(color, 0.85)
        btn.bind('<Enter>', lambda e: btn.configure(bg=dark_color))
        btn.bind('<Leave>', lambda e: btn.configure(bg=color))
        return btn

    def _darken(self, hex_color, factor=0.85):
        r, g, b = int(hex_color[1:3],16), int(hex_color[3:5],16), int(hex_color[5:7],16)
        return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"

    # ===== 第一步 =====
    def _build_step1(self):
        frame = self.step1_frame

        card_outer, card = self._new_card(frame)
        card_outer.pack(fill=tk.X, padx=12, pady=(12, 8))

        tk.Label(card, text="步骤一：检测电脑上的微信并解密数据库",
                 font=FONT_HEADING, bg=WHITE, fg=TEXT_DARK).pack(anchor=tk.W, padx=16, pady=(14, 2))
        tk.Label(card, text="请先登录电脑微信（Weixin.exe），然后点击下方按钮检测",
                 font=FONT_SMALL, bg=WHITE, fg=TEXT_GRAY).pack(anchor=tk.W, padx=16, pady=(0, 12))

        btn_row = tk.Frame(card, bg=WHITE)
        btn_row.pack(fill=tk.X, padx=16, pady=(0, 14))

        self.detect_btn = self._flat_button(btn_row, "🔍  检测微信", WECHAT_GREEN,
                                             self._detect_wechat, FONT_HEADING)
        self.detect_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.decrypt_btn = self._flat_button(btn_row, "🔓  解密数据库", BLUE,
                                              self._decrypt_db, FONT_HEADING)
        self.decrypt_btn.pack(side=tk.LEFT)
        self.decrypt_btn.config(state=tk.DISABLED, bg='#CCCCCC')

        self.detect_status = tk.Label(btn_row, text="", font=FONT_SMALL, bg=WHITE, fg=TEXT_GRAY)
        self.detect_status.pack(side=tk.RIGHT)

        # 账号列表卡片
        list_card_outer, list_card = self._new_card(frame)
        list_card_outer.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        tk.Label(list_card, text="📱  检测到的微信账号", font=FONT_HEADING,
                 bg=WHITE, fg=TEXT_DARK).pack(anchor=tk.W, padx=16, pady=(14, 6))

        columns = ('wxid', 'name', 'version', 'status')
        self.account_tree = ttk.Treeview(list_card, columns=columns, show='headings', height=5)
        self.account_tree.heading('wxid', text='微信ID')
        self.account_tree.heading('name', text='昵称')
        self.account_tree.heading('version', text='版本')
        self.account_tree.heading('status', text='密钥状态')
        self.account_tree.column('wxid', width=200, anchor='w')
        self.account_tree.column('name', width=160, anchor='w')
        self.account_tree.column('version', width=80, anchor='center')
        self.account_tree.column('status', width=120, anchor='center')
        self.account_tree.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))
        self.account_tree.bind('<<TreeviewSelect>>', self._on_account_select)

        self.account_empty_label = tk.Label(list_card,
            text="点击「检测微信」开始", font=FONT_SMALL, bg=WHITE, fg=TEXT_GRAY)
        self.account_empty_label.pack(pady=(4, 12))

        # 手动密钥卡片
        key_card_outer, key_card = self._new_card(frame)
        key_card_outer.pack(fill=tk.X, padx=12, pady=4)

        key_header = tk.Frame(key_card, bg=WHITE)
        key_header.pack(fill=tk.X, padx=16, pady=(14, 4))
        tk.Label(key_header, text="🔑  手动输入密钥", font=FONT_HEADING,
                 bg=WHITE, fg=TEXT_DARK).pack(side=tk.LEFT)
        tk.Label(key_header, text="微信 4.x yara 提取失败时使用", font=FONT_SMALL,
                 bg=WHITE, fg=TEXT_GRAY).pack(side=tk.LEFT, padx=(8, 0))

        key_row = tk.Frame(key_card, bg=WHITE)
        key_row.pack(fill=tk.X, padx=16, pady=(0, 8))
        tk.Label(key_row, text="64位密钥：", font=FONT_BODY, bg=WHITE,
                 fg=TEXT_DARK).pack(side=tk.LEFT)
        self.key_entry = tk.Entry(key_row, font=FONT_MONO, width=55,
                                  relief='solid', borderwidth=1, bg=WHITE,
                                  fg=TEXT_DARK, insertbackground=WECHAT_GREEN)
        self.key_entry.pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)
        self._flat_button(key_row, "使用此密钥", ORANGE,
                         self._use_manual_key, FONT_BODY).pack(side=tk.LEFT)

        tk.Label(key_card, text="💡  密钥也可保存为 wechat_db_key.txt 放在程序同目录，检测微信时自动加载",
                 font=FONT_SMALL, bg=WHITE, fg=TEXT_GRAY).pack(anchor=tk.W, padx=16, pady=(0, 12))

        # 手动选择
        manual_row = tk.Frame(frame, bg=LIGHT_GRAY)
        manual_row.pack(fill=tk.X, padx=12, pady=2)
        tk.Label(manual_row, text="或手动指定已解密的数据库路径：", font=FONT_SMALL,
                 bg=LIGHT_GRAY, fg=TEXT_GRAY).pack(side=tk.LEFT)
        self._flat_button(manual_row, "选择文件夹", BLUE,
                         self._manual_select_db, FONT_SMALL).pack(side=tk.LEFT, padx=8)

    def _detect_wechat(self):
        self.detect_btn.config(state=tk.DISABLED, text="⏳  检测中...", bg='#CCCCCC')
        self._set_log_status("●  检测中...", STATUS_COLORS['info'])
        self.detect_status.config(text="正在扫描微信进程...", fg=BLUE)
        self.log("正在检测微信...")

        def _run():
            results, errors = get_wechat_info()
            self.root.after(0, lambda: self._on_detect_done(results, errors))

        threading.Thread(target=_run, daemon=True).start()

    def _on_detect_done(self, results, errors):
        self.detect_btn.config(state=tk.NORMAL, text="🔍  检测微信", bg=WECHAT_GREEN)
        self.wx_accounts = results

        for item in self.account_tree.get_children():
            self.account_tree.delete(item)

        if results:
            self.account_empty_label.pack_forget()
            has_any_key = False
            for acc in results:
                name_text = acc['name'] or '(未知)'
                if acc.get('has_key'):
                    status = '✅ 已获取'
                    has_any_key = True
                else:
                    status = '⚠️ 未获取'
                ver_text = "4.0" if acc['version'] == 4 else "3.x"
                self.account_tree.insert('', tk.END,
                    values=(acc['wxid'], name_text, ver_text, status))

            if has_any_key:
                self.decrypt_btn.config(state=tk.NORMAL, bg=BLUE, text="🔓  解密数据库")
                self._set_log_status("●  就绪", WECHAT_GREEN)
                self.detect_status.config(text=f"✅ 检测到 {len(results)} 个账号，已获取密钥", fg=WECHAT_GREEN)
                self.log(f"检测到 {len(results)} 个微信账号，密钥已获取")
            else:
                self.decrypt_btn.config(state=tk.DISABLED, bg='#CCCCCC')
                self._set_log_status("●  密钥缺失", STATUS_COLORS['warning'])
                self.detect_status.config(text="⚠️ 密钥未提取到，请手动输入", fg=ORANGE)
                self.log("⚠️ yara 和暴力扫描均未找到密钥")
                for err in errors:
                    self.log(f"  详情: {err}")
                messagebox.showwarning("密钥提取失败",
                    "已检测到微信账号，但无法从内存中提取密钥。\n\n"
                    "💡 解决方法：\n\n"
                    "  1. 退出微信 → 重新登录 → 再点检测（推荐）\n"
                    "  2. 手动输入 64 位十六进制密钥\n"
                    "  3. 将密钥保存为 wechat_db_key.txt 自动加载")
        else:
            self.account_empty_label.config(text="未检测到微信，请确保微信已登录后重试")
            self._set_log_status("●  未检测到微信", STATUS_COLORS['error'])
            self.detect_status.config(text="❌ 未检测到微信进程", fg=RED)
            self.log("未检测到任何微信进程！请确保微信已登录")
            for err in errors:
                self.log(f"  错误: {err}")
            messagebox.showwarning("未检测到微信",
                "请先登录电脑微信再试！\n\n"
                "如果微信已登录但仍检测不到，请以管理员身份运行本程序。")

    def _on_account_select(self, event):
        selection = self.account_tree.selection()
        if selection:
            idx = self.account_tree.index(selection[0])
            if idx < len(self.wx_accounts):
                self.selected_account = self.wx_accounts[idx]

    def _use_manual_key(self):
        key = self.key_entry.get().strip()
        if len(key) != 64:
            self.log("⚠️ 密钥长度不正确，需要64位十六进制字符串（32字节）")
            self._set_log_status("●  密钥格式错误", STATUS_COLORS['error'])
            messagebox.showwarning("密钥格式错误",
                "密钥必须为64位十六进制字符串\n"
                "例如：a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0")
            return
        try:
            bytes.fromhex(key)
        except ValueError:
            self.log("⚠️ 密钥格式错误，包含非十六进制字符")
            return

        if not self.wx_accounts:
            self.log("⚠️ 请先点击【检测微信】获取账号信息")
            return
        if not self.selected_account:
            self.selected_account = self.wx_accounts[0]
            self.log("已自动选择第一个微信账号")

        self.selected_account['key'] = key
        self.selected_account['has_key'] = True
        self.selected_account['errcode'] = 200
        self.decrypt_btn.config(state=tk.NORMAL, bg=BLUE, text="🔓  解密数据库")
        self._set_log_status("●  密钥已设置", WECHAT_GREEN)
        self.detect_status.config(text="✅ 手动密钥已生效", fg=WECHAT_GREEN)
        self.log(f"✅ 手动密钥已设置（{key[:8]}...{key[-8:]}），可点击【解密数据库】")

    def _decrypt_db(self):
        if not self.selected_account:
            messagebox.showwarning("提示", "请先在列表中选择一个微信账号")
            return
        if not self.selected_account.get('has_key'):
            messagebox.showwarning("无法解密",
                "该账号未提取到解密密钥，无法解密数据库。\n\n"
                "请退出微信 → 重新登录 → 再点击【检测微信】。")
            return

        self.decrypt_btn.config(state=tk.DISABLED, text="⏳  解密中...", bg='#CCCCCC')
        self._set_log_status("●  解密中...", STATUS_COLORS['info'])
        acc = self.selected_account
        self.log(f"正在解密 {acc['name']} 的数据库...")

        def _run():
            try:
                db_path = decrypt_database(acc)
                self.root.after(0, lambda: self._on_decrypt_done(db_path, acc))
            except Exception as e:
                self.root.after(0, lambda: self._on_decrypt_error(str(e)))

        threading.Thread(target=_run, daemon=True).start()

    def _on_decrypt_done(self, db_path, acc):
        self.decrypt_btn.config(state=tk.NORMAL, text="🔓  解密数据库", bg=BLUE)
        self.db_path = db_path
        self.db_version = acc['version']
        self._set_log_status("●  解密成功", WECHAT_GREEN)
        self.detect_status.config(text="✅ 解密完成", fg=WECHAT_GREEN)
        self.log(f"✅ 解密成功！数据库路径: {db_path}")
        self._load_contacts()
        self.notebook.select(self.step2_frame)

    def _on_decrypt_error(self, error_msg):
        self.decrypt_btn.config(state=tk.NORMAL, text="🔓  解密数据库", bg=BLUE)
        self._set_log_status("●  解密失败", STATUS_COLORS['error'])
        self.detect_status.config(text="❌ 解密失败", fg=RED)
        self.log(f"❌ 解密失败: {error_msg}")
        messagebox.showerror("解密失败", f"解密数据库时出错：\n{error_msg}")

    def _manual_select_db(self):
        path = filedialog.askdirectory(title="选择解密后的数据库文件夹（如 db_storage 或 Msg）")
        if not path:
            return
        if os.path.exists(os.path.join(path, 'message.db')):
            self.db_version = 4
        elif os.path.exists(os.path.join(path, 'MSG0.db')):
            self.db_version = 3
        else:
            messagebox.showerror("错误",
                "所选文件夹中未找到微信数据库文件！\n请选择 db_storage（微信4.0）或 Msg（微信3.x）文件夹")
            return
        self.db_path = path
        self.log(f"📁 手动加载数据库: {path} (微信 {self.db_version}.0)")
        self._load_contacts()
        self.notebook.select(self.step2_frame)

    # ===== 第二步 =====
    def _build_step2(self):
        frame = self.step2_frame

        card_outer, card = self._new_card(frame)
        card_outer.pack(fill=tk.X, padx=12, pady=(12, 8))

        tk.Label(card, text="步骤二：选择要导出的联系人/群聊",
                 font=FONT_HEADING, bg=WHITE, fg=TEXT_DARK).pack(anchor=tk.W, padx=16, pady=(14, 2))
        tk.Label(card, text="使用搜索框快速筛选",
                 font=FONT_SMALL, bg=WHITE, fg=TEXT_GRAY).pack(anchor=tk.W, padx=16, pady=(0, 12))

        # 搜索栏
        search_frame = tk.Frame(card, bg=WHITE)
        search_frame.pack(fill=tk.X, padx=16, pady=(0, 12))

        search_inner = tk.Frame(search_frame, bg=LIGHT_GRAY, padx=2, pady=2)
        search_inner.pack(side=tk.LEFT)
        tk.Label(search_inner, text="🔍", font=FONT_BODY, bg=LIGHT_GRAY).pack(side=tk.LEFT, padx=(8, 2))
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *args: self._filter_contacts())
        search_entry = tk.Entry(search_inner, textvariable=self.search_var, width=28,
                                font=FONT_BODY, relief='flat', bg=LIGHT_GRAY, fg=TEXT_DARK,
                                insertbackground=WECHAT_GREEN)
        search_entry.pack(side=tk.LEFT, padx=(2, 8), pady=4)

        tk.Label(search_frame, text="按昵称 / 备注搜索", font=FONT_SMALL,
                 bg=WHITE, fg=TEXT_GRAY).pack(side=tk.LEFT, padx=(4, 0))

        self.contact_count_label = tk.Label(search_frame, text="", font=FONT_SMALL, bg=WHITE, fg=TEXT_GRAY)
        self.contact_count_label.pack(side=tk.RIGHT)

        # 联系人列表
        list_card_outer, list_card = self._new_card(frame)
        list_card_outer.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        columns = ('wxid', 'remark', 'nickname', 'type')
        self.contact_tree = ttk.Treeview(list_card, columns=columns, show='headings', height=14)
        self.contact_tree.heading('wxid', text='微信ID')
        self.contact_tree.heading('remark', text='备注')
        self.contact_tree.heading('nickname', text='昵称')
        self.contact_tree.heading('type', text='类型')
        self.contact_tree.column('wxid', width=180, anchor='w')
        self.contact_tree.column('remark', width=140, anchor='w')
        self.contact_tree.column('nickname', width=170, anchor='w')
        self.contact_tree.column('type', width=70, anchor='center')
        self.contact_tree.pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 8))

        # 按钮
        btn_row = tk.Frame(frame, bg=LIGHT_GRAY)
        btn_row.pack(fill=tk.X, padx=12, pady=(4, 4))
        self._flat_button(btn_row, "全选", MID_GRAY, self._select_all_contacts,
                         FONT_BODY).pack(side=tk.LEFT, padx=(0, 6))
        self._flat_button(btn_row, "取消全选", MID_GRAY, self._deselect_all_contacts,
                         FONT_BODY).pack(side=tk.LEFT)
        self._flat_button(btn_row, "下一步：导出  →", WECHAT_GREEN,
                         self._goto_export, FONT_HEADING).pack(side=tk.RIGHT)

    def _load_contacts(self):
        if not self.db_path:
            return
        try:
            conn = DatabaseConnection(self.db_path, self.db_version)
            self.database = conn.get_interface()
            if not self.database:
                self.log("数据库初始化失败")
                return
            self.contacts = self.database.get_contacts()
            self._refresh_contact_list(self.contacts)
            count = len(self.contacts)
            self.contact_count_label.config(text=f"共 {count} 个联系人")
            self.log(f"✅ 加载了 {count} 个联系人/群聊")
        except Exception as e:
            self.log(f"❌ 加载联系人失败: {e}")
            messagebox.showerror("错误", f"加载联系人失败：\n{e}")

    def _refresh_contact_list(self, contacts):
        for item in self.contact_tree.get_children():
            self.contact_tree.delete(item)
        for c in contacts:
            ctype = "👥 群聊" if c.is_chatroom else "👤 好友" if c.is_friend else "📌 其他"
            self.contact_tree.insert('', tk.END,
                values=(c.wxid, c.remark or '', c.nickname or '', ctype))
        self.contact_count_label.config(text=f"显示 {len(contacts)} 个联系人")

    def _filter_contacts(self):
        keyword = self.search_var.get().strip().lower()
        if not keyword:
            self._refresh_contact_list(self.contacts)
            self.contact_count_label.config(text=f"共 {len(self.contacts)} 个联系人")
            return
        filtered = [c for c in self.contacts
                    if keyword in (c.remark or '').lower()
                    or keyword in (c.nickname or '').lower()
                    or keyword in (c.wxid or '').lower()]
        self._refresh_contact_list(filtered)

    def _select_all_contacts(self):
        for item in self.contact_tree.get_children():
            self.contact_tree.selection_add(item)
        self.log(f"已全选 {len(self.contact_tree.get_children())} 个联系人")

    def _deselect_all_contacts(self):
        for item in self.contact_tree.selection():
            self.contact_tree.selection_remove(item)
        self.log("已取消全选")

    def _goto_export(self):
        selection = self.contact_tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请至少选择一个联系人")
            return
        self.selected_contact_indices = []
        for item in selection:
            values = self.contact_tree.item(item, 'values')
            wxid = values[0]
            for i, c in enumerate(self.contacts):
                if c.wxid == wxid:
                    self.selected_contact_indices.append(i)
                    break
        self.log(f"已选择 {len(self.selected_contact_indices)} 个联系人")
        self.notebook.select(self.step3_frame)

    # ===== 第三步 =====
    def _build_step3(self):
        frame = self.step3_frame

        card_outer, card = self._new_card(frame)
        card_outer.pack(fill=tk.X, padx=12, pady=(12, 8))

        tk.Label(card, text="步骤三：导出聊天记录",
                 font=FONT_HEADING, bg=WHITE, fg=TEXT_DARK).pack(anchor=tk.W, padx=16, pady=(14, 2))
        tk.Label(card, text="选择导出格式和输出目录",
                 font=FONT_SMALL, bg=WHITE, fg=TEXT_GRAY).pack(anchor=tk.W, padx=16, pady=(0, 12))

        # 格式选择
        fmt_card_outer, fmt_card = self._new_card(frame)
        fmt_card_outer.pack(fill=tk.X, padx=12, pady=4)

        tk.Label(fmt_card, text="📄  导出格式", font=FONT_HEADING,
                 bg=WHITE, fg=TEXT_DARK).pack(anchor=tk.W, padx=16, pady=(14, 8))

        self.export_format = tk.StringVar(value='html')
        formats = [
            ('🌐  HTML（推荐）— 可离线查看图片/视频/表情，浏览器打开', 'html'),
            ('📝  TXT — 纯文本格式', 'txt'),
            ('📋  Word (.docx) — 可排版打印', 'docx'),
            ('📊  Excel (.xlsx) — 适合数据分析', 'xlsx'),
            ('📖  Markdown — 适合笔记软件', 'md'),
            ('📑  CSV — 通用表格格式', 'csv'),
        ]

        for text, value in formats:
            rb = tk.Radiobutton(fmt_card, text=text, variable=self.export_format, value=value,
                                font=FONT_BODY, bg=WHITE, fg=TEXT_DARK,
                                activebackground=WECHAT_GREEN_LIGHT, activeforeground=TEXT_DARK,
                                selectcolor=WHITE, padx=12, pady=4,
                                indicatoron=True, cursor='hand2')
            rb.pack(anchor=tk.W, padx=16)

        # 分隔
        sep = tk.Frame(fmt_card, bg=MID_GRAY, height=1)
        sep.pack(fill=tk.X, padx=16, pady=(8, 4))

        # 输出目录
        dir_row = tk.Frame(fmt_card, bg=WHITE)
        dir_row.pack(fill=tk.X, padx=16, pady=(8, 14))
        tk.Label(dir_row, text="💾  输出目录：", font=FONT_BODY, bg=WHITE,
                 fg=TEXT_DARK).pack(side=tk.LEFT)
        self.output_dir_var = tk.StringVar(value=os.path.join(os.getcwd(), 'output'))
        dir_entry = tk.Entry(dir_row, textvariable=self.output_dir_var, width=40,
                             font=FONT_BODY, relief='solid', borderwidth=1,
                             bg=WHITE, fg=TEXT_DARK, insertbackground=WECHAT_GREEN)
        dir_entry.pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)
        self._flat_button(dir_row, "浏览...", BLUE,
                         self._browse_output, FONT_BODY).pack(side=tk.LEFT)

        # 导出按钮
        action_card_outer, action_card = self._new_card(frame)
        action_card_outer.pack(fill=tk.X, padx=12, pady=4)

        self.export_btn = self._flat_button(action_card, "🚀  开始导出", WECHAT_GREEN,
                                             self._start_export, FONT_HEADING)
        self.export_btn.pack(pady=14)

        self.progress = ttk.Progressbar(action_card, length=400, mode='determinate',
                                        style='Green.Horizontal.TProgressbar')
        self.progress.pack(fill=tk.X, padx=16, pady=(0, 8))
        self.progress_label = tk.Label(action_card, text="等待开始...",
                                        font=FONT_SMALL, bg=WHITE, fg=TEXT_GRAY)
        self.progress_label.pack(pady=(0, 14))

    def _browse_output(self):
        path = filedialog.askdirectory(title="选择导出目录")
        if path:
            self.output_dir_var.set(path)

    def _start_export(self):
        if not hasattr(self, 'selected_contact_indices') or not self.selected_contact_indices:
            messagebox.showwarning("提示", "请先选择联系人")
            self.notebook.select(self.step2_frame)
            return

        output_dir = self.output_dir_var.get()
        fmt = self.export_format.get()

        self.export_btn.config(state=tk.DISABLED, text="⏳  导出中...", bg='#CCCCCC')
        self._set_log_status("●  导出中...", STATUS_COLORS['info'])
        self.progress['value'] = 0
        self.progress['maximum'] = len(self.selected_contact_indices)

        self.log(f"📦 开始导出，共 {len(self.selected_contact_indices)} 个联系人，格式: {fmt}")

        def _run():
            try:
                from exporter.config import FileType
                from exporter import (HtmlExporter, TxtExporter, DocxExporter,
                                      ExcelExporter, MarkdownExporter, CSVExporter)

                exporter_map = {
                    'html': (HtmlExporter, FileType.HTML),
                    'txt': (TxtExporter, FileType.TXT),
                    'docx': (DocxExporter, FileType.DOCX),
                    'xlsx': (ExcelExporter, FileType.XLSX),
                    'md': (MarkdownExporter, FileType.MARKDOWN),
                    'csv': (CSVExporter, FileType.CSV),
                }

                exporter_cls, file_type = exporter_map[fmt]

                for i, idx in enumerate(self.selected_contact_indices):
                    contact = self.contacts[idx]
                    name = contact.remark or contact.nickname or contact.wxid
                    self.root.after(0, lambda n=name, p=i: self._update_progress(n, p))

                    exporter = exporter_cls(
                        self.database, contact,
                        output_dir=output_dir, type_=file_type,
                        message_types=None,
                        time_range=['2010-01-01 00:00:00', '2035-12-31 23:59:59'],
                        group_members=None
                    )
                    exporter.start()

                self.root.after(0, self._on_export_done)
            except Exception as e:
                self.root.after(0, lambda: self._on_export_error(str(e)))

        threading.Thread(target=_run, daemon=True).start()

    def _update_progress(self, name, idx):
        self.progress['value'] = idx + 1
        current = idx + 1
        total = self.progress['maximum']
        pct = current / total * 100
        self.progress_label.config(
            text=f"正在导出: {name}  ({current}/{total}  ·  {pct:.0f}%)")
        self.root.update_idletasks()

    def _on_export_done(self):
        self.export_btn.config(state=tk.NORMAL, text="✅  导出完成，再来一次", bg=WECHAT_GREEN)
        self._set_log_status("●  导出完成", WECHAT_GREEN)
        self.progress_label.config(text="🎉 全部导出完成！")
        self.log(f"🎉 导出完成！文件保存在: {self.output_dir_var.get()}")
        messagebox.showinfo("导出完成",
            f"✅ 聊天记录已导出到：\n{self.output_dir_var.get()}\n\n"
            f"💡 HTML 格式可直接用浏览器打开查看。")

    def _on_export_error(self, error_msg):
        self.export_btn.config(state=tk.NORMAL, text="🚀  开始导出", bg=WECHAT_GREEN)
        self._set_log_status("●  导出失败", STATUS_COLORS['error'])
        self.log(f"❌ 导出失败: {error_msg}")
        messagebox.showerror("导出失败", f"导出时出错：\n{error_msg}")


def main():
    root = tk.Tk()
    app = WeChatMsgApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
