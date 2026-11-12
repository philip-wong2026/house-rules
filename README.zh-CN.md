# Space Open

**给你的 AI 助手一个共用的工作区：用带规则的普通文件，让每个 AI 会话都能接着上一个会话往下做。**

[English](README.md) · 许可证：MIT · Python 3.9+ · 只用标准库 · macOS / Windows / Linux

Space Open 是一套交接约定（总规则、基础卡、状态文件），加十个小工具（备份、回收站、状态检查、安全的共用写入、写入前检查等），由你和 AI 聊几句话就装好。不会上传任何东西，全部在你电脑上的一个文件夹里。

## 作者自己怎么用
作者的设备：一台常开的 Mac mini（跑定时任务、让手机能呼叫 AI 助手）、一台 MacBook 日常用、手机上的聊天软件（Telegram）用来和助手说话、一块外接硬盘放大文件。这些你一样都不需要就能开始。

## 你需要准备什么
**必备（最低配置）：**
- 一台电脑（不用一直开着）
- 一个 AI 订阅或账号，能读写你电脑上的文件（例如带文件权限的 Claude Code 或 Claude Desktop，或其他同样能力的 AI 客户端）
- 一份异地备份（放在别处的外接硬盘，或另一个云账号）；安装时会带你设置，装完看 `BACKUP.md`

**进阶（以后再加，可选）：**
- 一台常开的电脑或云服务器：跑定时任务，让手机能呼叫助手
- 同步盘：Space 跟着你在几台电脑间走（工具也就能留意同步冲突副本）
- 手机聊天渠道（Telegram、iMessage 等）：出门在外也能和助手说话

电脑上要有 Python 3.9 或更新版本（安装程序和工具都是普通 Python，不用装任何包）。

## 安装（和你的 AI 聊几句）
打开你的 AI 客户端，说：

> 读 `<本仓库链接>/INSTALL.md`，帮我装上。

AI 会先说明安全声明并征得你的同意，再问几个问题（怎么称呼你、Mac 还是 Windows、有没有常开电脑、用哪个 AI、在哪里和它说话、要管哪几块事），然后调用 `setup.py`，带你设置异地备份，最后请你开一个新会话，核对暗号。详见 [INSTALL.zh-CN.md](INSTALL.zh-CN.md)。

也可以自己动手：
```sh
python3 setup.py --target ~/Space --name 小明 --os mac --language zh-CN --always-on no \
    --ai "Claude" --chat-channel 暂无 --modules 工作,个人 --yes
python3 setup.py --check --target ~/Space
```
（Windows 上把 `python3` 换成 `python`。）

## 会装进去什么
| 路径 | 是什么 |
|---|---|
| `AGENTS.md` | 总规则：模块写入方表、业务必读入口表、状态与历史维护 |
| `CLAUDE.md` | 基础卡，带校验暗号 |
| `PRINCIPLES.md` | 留给你自己写原则的空模板 |
| `STATE.md`、`<模块>/STATE.md` | 状态文件（根导航，每事项一条当前状态） |
| `BACKUP.md` | 异地备份方案和验证办法 |
| `.space/*.py` | 十个工具，读取 `.space/config.json` |
| `.space/hooks/` | 给 Claude Code 用的写入前检查和每轮检查（登记在 `.claude/settings.json`） |
| `.space/*.md` | 状态维护、项目说明的「通用三条」、十阶段 Agent 定制方法 |

## 十个工具
`backup`（改之前先备份）· `recycle`（回收站代替删除）· `read_rules`（必读文件加校验）· `redact`（敏感词不进共用区）· `record_check`（项目有改动但状态没跟上）· `state_check`（大小、链接、冲突副本）· `shared_write`（比对后再写）· `date_copy_check`（关键日期只写一处）· `pre_write_guard`（钩子）· `turn_check`（钩子）

## 安全与实话
- 你的电脑和数据安全由你自己负责。这些工具减少手滑，不是安全产品。
- 钩子是减速带，不是访问控制；Bash 检查是启发式的。
- Windows：代码避开了 macOS 专有命令，设计上能在 Windows 上跑，但只有 GitHub 自动试装（`.github/workflows/install-test.yml`）才算在 Windows 上验证过，作者本人没有亲手验过。
- 密码和密钥不要写进这些文件。每次发布前都会跑隐私扫描（`scripts/privacy_scan.py`）。

## 开发
```sh
python3 -m unittest discover -s tests -v
python3 scripts/privacy_scan.py            # 通用检查；设置 SPACE_OPEN_DENYLIST 可加入你自己的词表
```
