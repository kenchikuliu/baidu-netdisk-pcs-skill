---
name: baidu-netdisk-pcs
description: Search a user's Baidu Netdisk, upload local files or folders, create password-protected Baidu share links, list existing shares, and configure BaiduPCS-Py from an authenticated Baidu Netdisk desktop session. Use when Codex needs to find content in the user's Baidu cloud drive, transfer local content to Baidu Netdisk, or generate a pan.baidu.com sharing link.
---

# Baidu Netdisk PCS

Use the pinned `PeterDing/BaiduPCS-Py` integration through the bundled dispatcher. Do not invoke a random system installation of `BaiduPCS-Py`.

## Entry Point

Set the skill directory, then invoke the dispatcher:

```powershell
$skill = "$env:USERPROFILE\.codex\skills\baidu-netdisk-pcs"
& "$skill\scripts\baidu-netdisk.ps1" doctor
```

The dispatcher bootstraps the pinned tool on first use. Run `configure-client` if `doctor` reports no account:

```powershell
& "$skill\scripts\baidu-netdisk.ps1" configure-client
```

This reads the authenticated Baidu Netdisk desktop client's local cookie database without printing secrets. If the desktop session cannot provide a valid token, export the complete `Cookie` request header from a logged-in `pan.baidu.com` session to a temporary local text file and run:

```powershell
& "$skill\scripts\baidu-netdisk.ps1" configure-cookie-file C:\path\to\cookie.txt
```

Delete that temporary cookie file after configuration.

## Workflows

Search recursively from the drive root unless the user names a narrower folder:

```powershell
& "$skill\scripts\baidu-netdisk.ps1" search "keyword" --remote-dir / --recursive
```

Upload one local file or folder to a remote directory:

```powershell
& "$skill\scripts\baidu-netdisk.ps1" upload "C:\local\item" "/Codex Uploads"
```

Create a share link for an existing remote path. Default to a seven-day link and a generated four-character extraction code:

```powershell
& "$skill\scripts\baidu-netdisk.ps1" share "/Codex Uploads/item" --period-days 7
```

Upload one item, verify the remote path, and then share it:

```powershell
& "$skill\scripts\baidu-netdisk.ps1" upload-share "C:\local\item" "/Codex Uploads" --period-days 7
```

List existing valid shares:

```powershell
& "$skill\scripts\baidu-netdisk.ps1" list-shares
```

## Safety And Reporting

- Treat `search`, `doctor`, and `list-shares` as read-only.
- Upload only after the user explicitly identifies the local content and asks for an upload.
- Create a share only after the user explicitly asks for a link. A share exposes the selected content to anyone with the URL and extraction code.
- Default to seven days and an auto-generated extraction code. Use permanent or code-free shares only when explicitly requested.
- Never print, log, paste, or summarize `BDUSS`, `BDUSS_BFESS`, `STOKEN`, or the full Cookie header.
- Report the verified remote path, share URL, extraction code, and expiration period. Do not claim success when verification or share creation fails.
- If authentication expires, rerun `configure-client`. If upload/share fails after one fresh-auth retry, use the installed Baidu Netdisk desktop client as the fallback and state that the API path was unavailable.

Read [references/repository-notes.md](references/repository-notes.md) when diagnosing installation, authentication, upload, or share failures.
