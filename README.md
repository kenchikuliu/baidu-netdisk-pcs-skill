# Baidu Netdisk PCS Skill

一个面向 Codex 的开源百度网盘 Skill。它基于
[`PeterDing/BaiduPCS-Py`](https://github.com/PeterDing/BaiduPCS-Py)，支持：

- 搜索自己百度网盘中的文件和文件夹；
- 上传本地文件或目录，并验证远端路径；
- 为网盘文件生成带提取码的分享链接；
- 查看已有分享；
- 从已登录的 Windows 百度网盘客户端安全导入会话。

> 这是非官方项目，与百度无隶属关系。仅操作你有权访问的账号和内容，并遵守百度网盘服务条款及当地法律。

## 支持范围

- Windows 10/11；
- Codex 全局 Skills；
- PowerShell 5.1 或更高版本；
- Git；
- Python 3.9、3.10、3.11 或 3.12；
- 百度网盘 Windows 客户端，或者已登录 `pan.baidu.com` 的浏览器会话。

目前不支持账号密码直接登录。认证需要 `BDUSS` 和 Cookie；创建分享还需要 `STOKEN`。

## 1. 安装到全局 Skills

打开 PowerShell：

```powershell
$skill = "$env:USERPROFILE\.codex\skills\baidu-netdisk-pcs"
git clone https://github.com/kenchikuliu/baidu-netdisk-pcs-skill.git $skill
```

重新启动 Codex，让全局 Skill 列表刷新。

首次运行时，启动脚本会：

1. 在 `~/.codex/tools/baidupcs-py` 克隆固定版本的 `BaiduPCS-Py`；
2. 应用已知的百度接口兼容补丁；
3. 自动选择 Python 3.9–3.12；
4. 只安装运行所需的最小 Python 依赖。

先检查环境：

```powershell
& "$skill\scripts\baidu-netdisk.ps1" doctor
```

## 2. 配置账号

### 方法 A：从百度网盘客户端导入（推荐）

1. 在 Windows 百度网盘客户端登录自己的账号；
2. 保持客户端登录；
3. 执行：

```powershell
& "$skill\scripts\baidu-netdisk.ps1" configure-client
& "$skill\scripts\baidu-netdisk.ps1" doctor --online
```

脚本读取当前 Windows 用户自己的
`%APPDATA%\baidunetdisk\Network\Cookies`，不会在终端打印 Cookie。

部分百度网盘客户端版本会加密 Cookie。若提示缺少 `BDUSS` 或 `STOKEN`，使用方法 B。

### 方法 B：从浏览器导入 Cookie

1. 登录 <https://pan.baidu.com>；
2. 按 `F12` 打开开发者工具，选择 **Network / 网络**；
3. 在网盘中打开任意文件夹；
4. 选择名称类似 `list?...` 的请求；
5. 在 **Request Headers / 请求标头** 中找到完整的 `Cookie`；
6. 只把 `Cookie:` 后面的值保存到一个临时 UTF-8 文本文件；
7. 执行：

```powershell
& "$skill\scripts\baidu-netdisk.ps1" configure-cookie-file "C:\Temp\baidu-cookie.txt"
& "$skill\scripts\baidu-netdisk.ps1" doctor --online
```

配置成功后立即删除临时 Cookie 文件。不要把 Cookie 放进聊天、Issue、截图、Git 提交或命令行参数。

认证信息保存在 `~/.baidupcs-py/accounts.pk`，脚本会限制为当前 Windows 用户访问。该文件绝不能提交到 Git。

## 3. 使用

### 在 Codex 中直接说

- “在我的百度网盘搜索录屏软件”；
- “在 `/项目资料` 下搜索预算表”；
- “把 `C:\Work\report.zip` 上传到百度网盘 `/Codex Uploads`”；
- “上传这个文件并生成 7 天有效的百度网盘链接”；
- “查看我当前有效的百度网盘分享”。

### PowerShell 命令

搜索：

```powershell
& "$skill\scripts\baidu-netdisk.ps1" search "关键词" --remote-dir / --recursive
```

上传文件或目录：

```powershell
& "$skill\scripts\baidu-netdisk.ps1" upload "C:\local\item" "/Codex Uploads"
```

分享已有网盘文件：

```powershell
& "$skill\scripts\baidu-netdisk.ps1" share "/Codex Uploads/item" --period-days 7
```

上传、验证并分享：

```powershell
& "$skill\scripts\baidu-netdisk.ps1" upload-share "C:\local\item" "/Codex Uploads" --period-days 7
```

查看分享：

```powershell
& "$skill\scripts\baidu-netdisk.ps1" list-shares
```

分享默认有效期为 7 天，并自动生成四位提取码。只有明确指定时才应创建永久或无提取码分享。

## 4. 更新

```powershell
git -C "$env:USERPROFILE\.codex\skills\baidu-netdisk-pcs" pull
& "$env:USERPROFILE\.codex\skills\baidu-netdisk-pcs\scripts\bootstrap.ps1"
```

## 5. 卸载

删除 Skill：

```powershell
Remove-Item "$env:USERPROFILE\.codex\skills\baidu-netdisk-pcs" -Recurse
```

可选：同时删除运行依赖和本地账号配置：

```powershell
Remove-Item "$env:USERPROFILE\.codex\tools\baidupcs-py" -Recurse
Remove-Item "$env:USERPROFILE\.baidupcs-py" -Recurse
```

第二条会删除本地保存的百度登录会话，执行前请确认路径。

## 安全设计

- 搜索、环境检查和查看分享是只读操作；
- 上传前验证本地路径，上传后验证远端路径；
- 只有明确要求时才上传或创建分享；
- 不输出 `BDUSS`、`BDUSS_BFESS`、`STOKEN` 或完整 Cookie；
- 分享接口必须返回有效的 `pan.baidu.com` URL 才报告成功；
- 已知 API 失败会停止，不会伪报上传或分享成功。

## 已知限制

百度网盘的非官方接口可能随时变化。仓库固定了经过验证的上游提交，并修复了 GitHub issue `#143` 中的 `31023` 参数问题。上传或分享仍可能受到百度账号风控、配额和服务端变更影响。

## English Quick Start

This is an unofficial Windows Codex Skill for searching, uploading, and sharing files in the user's own Baidu Netdisk account.

```powershell
$skill = "$env:USERPROFILE\.codex\skills\baidu-netdisk-pcs"
git clone https://github.com/kenchikuliu/baidu-netdisk-pcs-skill.git $skill
& "$skill\scripts\baidu-netdisk.ps1" doctor
& "$skill\scripts\baidu-netdisk.ps1" configure-client
& "$skill\scripts\baidu-netdisk.ps1" doctor --online
```

Never publish the Cookie header or `~/.baidupcs-py/accounts.pk`.

## License

本项目使用 [MIT License](LICENSE)。上游 `PeterDing/BaiduPCS-Py` 也使用 MIT License。
