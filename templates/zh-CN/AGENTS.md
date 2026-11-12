# AGENTS.md — {{user}}的 Space 总规则

这份是细则。每个会话必须守的精简版在 [CLAUDE.md](CLAUDE.md)。用到哪章查哪章。规则要改，只改这里，别处不再抄。

## 1. 每个会话开头
1. 读 `CLAUDE.md` 里的基础卡。能答出「暗号是什么」，说明卡已带上。
2. 读本项目 README 的「当前状态」（或模块 `STATE.md`），弄清做到哪了。
3. 要写文件之前，查下面两张表：这个文件夹归谁写、这类事先读哪份规则。
4. 定方向、做取舍时，读一次 `PRINCIPLES.md`。

## 2. 模块写入方表
每个模块（顶层文件夹）默认只有一个写入方。其他人只读，要改就请写入方办，或在写入方 `STATE.md` 的「未决」里留一句。

{{modules_table}}

- 默认是约定，不是锁。{{user}}现场说「在这个会话做」就照办。
- 共用文件（根 `STATE.md`、`AGENTS.md`、`CLAUDE.md`、模块 `STATE.md`）用 `{{py}} .space/shared_write.py` 写（按 SHA-256 比对再替换），不拿旧版本整文件覆盖。

## 3. 业务必读入口表
| 做什么事 | 先读 |
|---|---|
| 任何工作 | `CLAUDE.md`、本文第 1–2 章 |
| 定方向、做取舍 | `PRINCIPLES.md` |
| 改某模块的状态 | 该模块 `STATE.md` 和 `.space/state-maintenance.md` |
| 新建或停掉项目 | `.space/project-three-rules.md` |
| 给别人搭助手 | `.space/agent-customization.md` |
| 备份与恢复 | `BACKUP.md` |

新增一类有专门规则的事，就加一行。`{{py}} .space/read_rules.py manifest` 会列出必读文件的大小和 SHA-256，看有没有缺。

## 4. 状态与历史
- 三层：根 `STATE.md`（导航，每轮读，最多 {{root_limit}} 字符）→ 模块 `STATE.md`（每事项一条当前状态，最多 {{module_limit}} 字符）→ 带日期的记录和 `.space/history/`（过程、证据、旧正文，按需查）。
- 一事一条。新状态替换旧条目；旧正文存进带日期的记录，不堆在条目里。
- 每条写：现状（来源日期）／未决／下一步／依据。模板见 `.space/state-maintenance.md`。
- 有决定或进展，当场写进 README「当前状态」或 `STATE.md`；收工前核对这次定的事是否都写进去了。
- 没验证过的不说「已完成」；写清验证了什么、哪天、来源是什么。事实、推断、待确认分开写。
- 检查：`{{py}} .space/state_check.py`（只读）。到上限 80% 先整理，不硬截断。

## 5. 文件：备份、回收、冲突
- 改设置或程序之前：`{{py}} .space/backup.py <文件>`（存到 `.space/history/write-backups/`）。正本旁不放 `.bak`。
- 清理不直接删：`{{py}} .space/recycle.py <路径> --reason "为什么" --who <谁>` 挪进 `.space/recycle-bin/`（留 {{keep_days}} 天，`--restore` 可捞回）。永久删除要先问{{user}}。
- 同步冲突副本是证据：先比对、保全双方再合并，不拿一份覆盖另一份。
- 写文件前重读目标文件。同一个文件同一时间只由一个会话写。

## 6. 底线
- 下列事先问{{user}}：花钱、给别人发消息、永久删除、改外部原件、改网络或代理设置、登录账号。
- 密码、令牌、密钥不进普通文件，放在密码管理器里。
- 只做这次要求的事。
- 用大白话汇报：先结论，再依据、限制和下一步。

## 7. 保险丝（哪些强制、哪些不强制）
在 Space 根目录用 Claude Code 时，`.claude/settings.json` 登记了两个钩子：写入前检查（`.space/hooks/pre_write_guard.py`）拦明显的手滑，每轮检查（`.space/hooks/turn_check.py`）在每轮开头报问题。它们是防手滑的减速带，不是安全边界。别的 AI 客户端可能不执行它们；上面的规则照样适用。
