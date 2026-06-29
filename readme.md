<h1 align="center">WeChatMsg-Fix-4.1.x</h1>
<p align="center"><strong>修复微信 4.1.x 版本密钥提取 · 保留「留痕」初心</strong></p>

---

> ⚠️ **本项目是 [LC044/WeChatMsg](https://github.com/LC044/WeChatMsg)（留痕 MemoTrace）的社区修复分支。**
>
> 原作者 **SiYuan** 的理念——"我的数据我做主"——是这一切的起点。本项目仅针对微信 4.1.x 版本（`Weixin.exe`）的密钥提取做了适配修复，所有核心代码、导出功能、数据库解析逻辑均来自原项目。
>
> 🙏 **请先给原项目点个 Star：[github.com/LC044/WeChatMsg](https://github.com/LC044/WeChatMsg)**
>
> 官网：[memotrace.cn](https://memotrace.cn/) | 原作者博客：[blog.lc044.love](https://blog.lc044.love/)

---

## 🔧 本分支做了什么

微信 4.1.x (`Weixin.exe`) 改变了内存数据结构，原项目的 yara 规则无法定位到密钥地址（`errcode=404`），导致密钥提取失败。

本分支新增了 **wx_key DLL 注入方案** 来替代失效的 yara 内存扫描：

| 功能 | 原项目 (WeChatMsg) | 本分支 (Fix-4.1.x) |
|------|-------------------|---------------------|
| 微信 3.x 密钥提取 | ✅ | ✅ |
| 微信 4.0 密钥提取 | ✅ | ✅ |
| **微信 4.1.x 密钥提取** | ❌ errcode=404 | ✅ DLL 注入 |
| SQLCipher 解密 | ✅ | ✅ |
| 聊天记录导出 | ✅ (HTML/TXT/CSV/DOCX/MD/XLSX) | ✅ 同 |
| 联系人管理 | ✅ | ✅ |
| 可视化年报 | ✅ | ✅ |

---

## 🚀 快速使用

### 对于微信 4.1.x 用户

```bash
# 1. 确保微信已登录
# 2. 以管理员身份运行密钥提取
python auto_extract.py

# 3. 密钥会自动保存到 wechat_db_key.txt
# 4. 启动 GUI 导出聊天记录
python gui_app.py
#    → 点击「检测微信」→ 密钥自动加载 → 「解密数据库」→ 选择联系人 → 导出
```

### 对于微信 3.x / 4.0 用户

直接使用原项目即可，不需要本分支。👉 [github.com/LC044/WeChatMsg](https://github.com/LC044/WeChatMsg)

---

## 📦 新增工具说明

| 文件 | 用途 |
|------|------|
| `auto_extract.py` | 一键自动：杀微信 → 注入 Hook → 启动微信 → 捕获密钥（需要管理员权限） |
| `run_wx_key.py` | 对已运行的微信手动 Hook 捕获密钥 |
| `verify_key.py` | 验证捕获的密钥是否能解密数据库 |
| `bulk_export.py` | CLI 批量导出所有联系人聊天记录 |
| `wechat_db_key.txt` | 密钥本地存储文件（已被 .gitignore，不会提交） |

**注意：** `auto_extract.py` 依赖 `wx_key.dll`——这是一个独立的 DLL 注入工具，不包含在本仓库中。请从 [wx_key](https://github.com/ycccccccy/wx_key) 项目获取。

---

## 📋 依赖安装

```bash
pip install -r requirements.txt
pip install psutil pycryptodome
```

---

## ⚠️ 免责声明

> 本项目继承了原项目 [LC044/WeChatMsg](https://github.com/LC044/WeChatMsg) 的全部声明：
>
> - 该项目有且仅有一个目的：**"留痕"——我的数据我做主**
> - 禁止任何人以任何形式将其用于任何非法用途
> - 对于使用该程序所造成的任何后果，所有创作者不承担任何责任
> - 该软件不能找回删除的聊天记录
> - 如果该项目侵犯了您或您产品的任何权益，请联系删除

---

## 📜 License

MIT License · Copyright © 2022-2024 by **SiYuan** (原作者)

本分支同样遵循 MIT 协议开源。二次开发请务必遵守开源协议并保留原作者版权声明。

---

## ❤️ 致谢

- **[LC044 (SiYuan)](https://github.com/LC044)** — 原项目「留痕 WeChatMsg」作者，创造了这一切
- **[xaoyaoo/PyWxDump](https://github.com/xaoyaoo/PyWxDump)** — PC 微信数据库解密工具
- **[ycccccccy/wx_key](https://github.com/ycccccccy/wx_key)** — 微信 4.1.x DLL 注入密钥提取工具

---

<p align="center"><em>"我深信有意义的不是微信，而是隐藏在对话框背后的一个个深刻故事。" —— SiYuan</em></p>
