# Repository Notes

## Pinned Source

- Repository: `https://github.com/PeterDing/BaiduPCS-Py`
- Commit: `e81e9b65c4b35fc8f7f2993a81e25e0bc24608db`
- Declared version: `0.7.6`
- License: MIT
- Last code commit on the default branch: 2024-05-10

## Authentication

The project does not support username/password login. It requires a current `BDUSS` and Cookie set. Share creation also requires `STOKEN`.

The Windows Baidu Netdisk desktop client commonly stores a Chromium Cookies database at `%APPDATA%\baidunetdisk\Network\Cookies`. On compatible client versions the relevant values are locally readable by the signed-in Windows user. `configure-client` imports them without displaying the values.

Re-run configuration when the Baidu session expires. Never include Cookie values in prompts, logs, command-line arguments, or reports.

## Compatibility Patch

GitHub issue `#143` documents Baidu API error `31023` caused by the historical list parameter `limit=0-2147483647`. The bootstrap removes that parameter before installation.

## Current Risks

- Issue `#139` reports uploads hanging or failing for some files in 2025.
- Issues `#124` and `#131` report share failures. A fresh `STOKEN` may help, but Baidu can also impose account-side share restrictions.
- The repository has no current release artifacts and the latest default-branch code is from 2024.
- Treat every upload as successful only after the remote path exists.
- Treat every share as successful only when the API returns a non-empty `pan.baidu.com` URL.
- Retry once after refreshing authentication. Then fall back to the installed Baidu Netdisk desktop client.
