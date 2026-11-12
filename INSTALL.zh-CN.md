# INSTALL.zh-CN.md — 写给 AI 的安装说明

你是 AI 助手。用户请你在他的电脑上安装 Space Open。请按顺序做，用大白话，一次只问一个问题，不要跳过同意这一步。（英文版：[INSTALL.md](INSTALL.md)。）

## 第 0 步：拿到文件
把本仓库下载或克隆到一个你能读的临时文件夹（例如用户的“下载”文件夹）。`setup.py`、`tools/`、`templates/` 要放在一起。确认电脑上有 Python 3.9 以上（`python3 --version`，Windows 上是 `python --version`）。没有就告诉用户怎么装，然后停下；需要管理员权限的软件不要自己装。

## 第 1 步：安全声明与同意
用你自己的话对用户说下面的意思，等他明确说「同意」：

> Space Open 会在你的电脑上建文件夹和文本文件，还可能给 Claude Code 加钩子设置。它不会上传任何东西。**你的电脑和数据安全由你自己负责**：请自己做好备份，不要把密码和密钥写进这些文件。这些工具只是减少手滑，不是安全产品。你同意继续吗？

用户没有明确同意就停下。只有他同意之后，才给 `setup.py` 加 `--yes`。

## 第 2 步：问这些问题（一次一个）
1. 我怎么称呼你？（`--name`）
2. 用 Mac 还是 Windows？（`--os mac|windows|linux`）
3. 有没有一台一直开着的电脑，或者云服务器？有／没有（`--always-on yes|no`）。「没有」完全可以，只影响以后的定时任务。
4. 你用哪个 AI？（`--ai`）
5. 想在哪里和助手说话：只在这里，还是也要手机聊天软件（Telegram、iMessage 等）？（`--chat-channel`）
6. 要管哪几块事？建议 `工作,个人`；文件夹名可以用中文（字母、数字、`-`、`_`，不能含斜杠）。（`--modules`，用逗号分隔）
7. 这个文件夹放不放在同步盘里（iCloud、Dropbox、坚果云等）？（`--sync-drive yes|no`）
8. 文件用中文还是英文？（`--language zh-CN|en`）
可选：问他的设备，写成 `"名称|用途"`（`--device`，可重复）；问有没有想让写入检查保护的文件夹（`--protect`，相对文件夹名）。

还要定 Space 放哪：问用户，或者建议放在他主目录下的 `Space` 文件夹（`--target`）。不要挑一个已经放着重要文件的文件夹而不告诉他。

## 第 3 步：安装
运行（Windows 上把 `python3` 换成 `python`；路径有空格要加引号）：

```sh
python3 setup.py --target "<文件夹>" --name "<称呼>" --os <mac|windows|linux> --language <zh-CN|en> \
    --always-on <yes|no> --ai "<AI>" --chat-channel "<渠道>" --modules "<甲,乙>" \
    --sync-drive <yes|no> --yes
```

命令会打印 JSON：建了哪些文件，以及基础卡的**暗号**。已存在的文件不会被悄悄覆盖，会列为「跳过」。用户没要求就别用 `--force`（它会先备份旧文件）。

出错就读错误信息、改参数再跑。不要为了让报错消失而手改已装好的工具。

## 第 4 步：自检
运行 `python3 setup.py --check --target "<文件夹>"`。每一行都要是 `ok: true`。有失败就用大白话告诉用户。

## 第 5 步：异地备份
打开新 Space 里的 `BACKUP.md`，带用户走一遍：至少选一个「丢了这台电脑也还在」的地方（放在别处的外接硬盘、另一个云账号、私有 git 远端、服务器快照）。让他做一次备份，从里面恢复一个文件并对比。对上了才把 `.space/config.json` 里的 `backup.status` 改成 `done`，把办法（不写密码）写进 `backup.method`。他现在不想做，就保持 `pending`，状态检查会继续提醒。

## 第 6 步：让 AI 客户端读到 Space
- Claude Code：请用户**在 Space 根文件夹**打开 Claude Code，这样 `CLAUDE.md` 自动加载，`.claude/settings.json` 里的钩子才生效。（Windows 上的钩子要等项目的自动试装跑过才算验证；你在 Windows 上就如实说明。）
- 其他客户端：请他把 `.space/project-three-rules.md` 里的「通用三条」放到项目说明最前面，保证基础卡会被读到。

## 第 7 步：新会话核对暗号
告诉用户：在 Space 里开一个**新**会话，问「基础卡暗号是什么」。它应该答出第 3 步里的暗号。答不出，说明 `CLAUDE.md` 没被加载，先回头修第 6 步。然后给他看 `PRINCIPLES.md`（故意留空），请他准备好了再写自己的原则。

## 不要做
- 不要发送、上传或公开任何东西。
- 不要把密码、令牌、密钥写进任何已安装的文件。
- 不要装需要管理员权限的软件，不要改网络或代理设置。
