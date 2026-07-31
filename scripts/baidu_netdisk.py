from __future__ import annotations

import argparse
import io
import json
import os
import posixpath
import secrets
import shutil
import sqlite3
import string
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def emit(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str))


def account_manager():
    from baidupcs_py.app.account import AccountManager
    from baidupcs_py.commands.env import ACCOUNT_DATA_PATH

    data_path = Path(ACCOUNT_DATA_PATH).expanduser()
    return AccountManager.load_data(data_path), data_path


def current_account():
    manager, data_path = account_manager()
    account = manager.who()
    if not account:
        raise RuntimeError("No Baidu account is configured. Run configure-client first.")
    return manager, account, data_path


def account_summary(account) -> dict[str, Any]:
    auth = account.user.auth
    return {
        "account_name": account.account_name,
        "user_name": account.user.user_name,
        "user_id": account.user.user_id,
        "has_bduss": bool(auth and auth.bduss),
        "has_stoken": bool(auth and auth.stoken),
    }


def parse_cookie_header(header: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for part in header.replace("\r", "").replace("\n", "").split(";"):
        if "=" not in part:
            continue
        name, value = part.strip().split("=", 1)
        if name and value:
            cookies[name] = value
    return cookies


def cookies_from_client(cookie_db: Path) -> dict[str, str]:
    if not cookie_db.exists():
        raise RuntimeError(f"Baidu Netdisk cookie database not found: {cookie_db}")

    temp_dir = Path(tempfile.mkdtemp(prefix="baidupcs-cookie-"))
    temp_db = temp_dir / "Cookies"
    try:
        shutil.copy2(cookie_db, temp_db)
        with sqlite3.connect(temp_db) as connection:
            rows = connection.execute(
                "SELECT host_key, name, value FROM cookies WHERE value <> ''"
            ).fetchall()
        cookies: dict[str, str] = {}
        for host, name, value in rows:
            if str(host).endswith("baidu.com") and name and value:
                cookies[str(name)] = str(value)
        return cookies
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def secure_account_file(path: Path) -> None:
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass

    if os.name == "nt":
        try:
            identity = subprocess.run(
                ["whoami"], check=True, capture_output=True, text=True
            ).stdout.strip()
            subprocess.run(
                ["icacls", str(path), "/inheritance:r", "/grant:r", f"{identity}:(F)"],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            pass


def configure(cookies: dict[str, str], account_name: str = "") -> dict[str, Any]:
    from baidupcs_py.app.account import Account

    bduss = cookies.get("BDUSS") or cookies.get("BDUSS_BFESS")
    if not bduss:
        raise RuntimeError("The session does not contain BDUSS or BDUSS_BFESS.")
    if not cookies.get("STOKEN"):
        raise RuntimeError("The session does not contain STOKEN, which is required for sharing.")

    cookies["BDUSS"] = bduss
    cookies.setdefault("BDUSS_BFESS", bduss)
    account = Account.from_bduss(bduss, cookies=cookies, account_name=account_name)
    manager, data_path = account_manager()
    manager.add_account(account)
    manager.su(account.user.user_id)
    manager.save(data_path)
    secure_account_file(data_path)
    return {"ok": True, "configured": account_summary(account), "account_file": str(data_path)}


def normalize_remote(path: str) -> str:
    normalized = posixpath.normpath("/" + path.lstrip("/"))
    return normalized if normalized.startswith("/") else "/" + normalized


def file_payload(item) -> dict[str, Any]:
    data = item._asdict()
    return {
        "path": data.get("path"),
        "is_dir": data.get("is_dir"),
        "size": data.get("size"),
        "md5": data.get("md5"),
        "ctime": data.get("ctime"),
        "mtime": data.get("mtime"),
        "fs_id": data.get("fs_id"),
    }


def share_payload(link, period_days: int) -> dict[str, Any]:
    data = link._asdict()
    url = data.get("url")
    if not url or "pan.baidu.com" not in url:
        raise RuntimeError("Baidu did not return a valid pan.baidu.com share URL.")
    return {
        "ok": True,
        "url": url,
        "password": data.get("password"),
        "paths": data.get("paths"),
        "share_id": data.get("share_id"),
        "period_days": period_days,
    }


def make_password() -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(4))


def ensure_remote_dir(api, remote_dir: str) -> None:
    current = "/"
    for part in [p for p in remote_dir.split("/") if p]:
        current = normalize_remote(posixpath.join(current, part))
        if not api.exists(current):
            api.makedir(current)


def upload_file(api, local_file: Path, remote_path: str, overwrite: bool) -> dict[str, Any]:
    remote_path = normalize_remote(remote_path)
    if api.exists(remote_path) and not overwrite:
        return {
            "local_path": str(local_file.resolve()),
            "remote_path": remote_path,
            "status": "skipped_existing",
            "size": local_file.stat().st_size,
        }

    stat = local_file.stat()
    ondup = "overwrite"
    if stat.st_size <= 4 * 1024 * 1024:
        with local_file.open("rb") as stream:
            api.upload_file(stream, remote_path, ondup=ondup)
    else:
        slice_md5s: list[str] = []
        with local_file.open("rb") as stream:
            while True:
                chunk = stream.read(8 * 1024 * 1024)
                if not chunk:
                    break
                slice_md5s.append(api.upload_slice(io.BytesIO(chunk)))
        api.combine_slices(
            slice_md5s,
            remote_path,
            local_ctime=int(stat.st_ctime),
            local_mtime=int(stat.st_mtime),
            ondup=ondup,
        )

    if not api.exists(remote_path):
        raise RuntimeError(f"Upload was not verified at {remote_path}.")
    return {
        "local_path": str(local_file.resolve()),
        "remote_path": remote_path,
        "status": "uploaded",
        "size": stat.st_size,
    }


def run_upload(local_path: Path, remote_dir: str, max_workers: int, overwrite: bool) -> dict[str, Any]:
    if not local_path.exists():
        raise RuntimeError(f"Local path does not exist: {local_path}")

    _, account, _ = current_account()
    api = account.pcsapi()
    remote_dir = normalize_remote(remote_dir)
    ensure_remote_dir(api, remote_dir)

    uploaded: list[dict[str, Any]] = []
    if local_path.is_file():
        remote_path = normalize_remote(posixpath.join(remote_dir, local_path.name))
        uploaded.append(upload_file(api, local_path, remote_path, overwrite))
    else:
        remote_root = normalize_remote(posixpath.join(remote_dir, local_path.name))
        ensure_remote_dir(api, remote_root)
        for directory, _, filenames in os.walk(local_path):
            directory_path = Path(directory)
            relative_dir = directory_path.relative_to(local_path).as_posix()
            target_dir = remote_root if relative_dir == "." else normalize_remote(posixpath.join(remote_root, relative_dir))
            ensure_remote_dir(api, target_dir)
            for filename in filenames:
                file_path = directory_path / filename
                uploaded.append(
                    upload_file(api, file_path, posixpath.join(target_dir, filename), overwrite)
                )
        remote_path = remote_root

    if not api.exists(remote_path):
        raise RuntimeError(f"Upload root was not verified at {remote_path}.")
    return {
        "ok": True,
        "local_path": str(local_path.resolve()),
        "remote_path": remote_path,
        "max_workers": max_workers,
        "items": uploaded,
    }


def command_doctor(args) -> None:
    manager, data_path = account_manager()
    account = manager.who()
    payload: dict[str, Any] = {
        "ok": bool(account),
        "tool_version": "0.7.6+compat",
        "account_file": str(data_path),
        "configured": bool(account),
    }
    if account:
        payload["account"] = account_summary(account)
        if args.online:
            user = account.pcsapi().user_info()
            payload["online"] = {"ok": True, "user_id": user.user_id, "user_name": user.user_name}
    emit(payload)


def command_configure_client(args) -> None:
    cookie_db = Path(args.cookie_db or (Path(os.environ["APPDATA"]) / "baidunetdisk/Network/Cookies"))
    emit(configure(cookies_from_client(cookie_db), args.account_name))


def command_configure_cookie_file(args) -> None:
    cookie_file = Path(args.cookie_file)
    header = cookie_file.read_text(encoding="utf-8").strip()
    emit(configure(parse_cookie_header(header), args.account_name))


def command_search(args) -> None:
    _, account, _ = current_account()
    remote_dir = normalize_remote(args.remote_dir)
    files = account.pcsapi().search(args.keyword, remote_dir, recursive=args.recursive)
    emit({"ok": True, "keyword": args.keyword, "remote_dir": remote_dir, "count": len(files), "items": [file_payload(f) for f in files]})


def command_upload(args) -> None:
    emit(run_upload(Path(args.local_path), args.remote_dir, args.max_workers, args.overwrite))


def command_share(args) -> None:
    _, account, _ = current_account()
    paths = [normalize_remote(p) for p in args.remote_paths]
    password = args.password or make_password()
    link = account.pcsapi().share(*paths, password=password, period=args.period_days)
    emit(share_payload(link, args.period_days))


def command_upload_share(args) -> None:
    upload = run_upload(Path(args.local_path), args.remote_dir, args.max_workers, args.overwrite)
    _, account, _ = current_account()
    password = args.password or make_password()
    link = account.pcsapi().share(upload["remote_path"], password=password, period=args.period_days)
    emit({"ok": True, "upload": upload, "share": share_payload(link, args.period_days)})


def command_list_shares(args) -> None:
    _, account, _ = current_account()
    api = account.pcsapi()
    links = []
    for page in range(1, 51):
        page_links = api.list_shared(page)
        if not page_links:
            break
        for link in page_links:
            if args.all or link.available():
                links.append(share_payload(link, 0))
    emit({"ok": True, "count": len(links), "items": links})


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Safe BaiduPCS-Py wrapper for Codex")
    commands = root.add_subparsers(dest="command", required=True)

    doctor = commands.add_parser("doctor")
    doctor.add_argument("--online", action="store_true")
    doctor.set_defaults(func=command_doctor)

    client = commands.add_parser("configure-client")
    client.add_argument("--cookie-db")
    client.add_argument("--account-name", default="")
    client.set_defaults(func=command_configure_client)

    cookie_file = commands.add_parser("configure-cookie-file")
    cookie_file.add_argument("cookie_file")
    cookie_file.add_argument("--account-name", default="")
    cookie_file.set_defaults(func=command_configure_cookie_file)

    search = commands.add_parser("search")
    search.add_argument("keyword")
    search.add_argument("--remote-dir", default="/")
    search.add_argument("--recursive", action=argparse.BooleanOptionalAction, default=True)
    search.set_defaults(func=command_search)

    upload = commands.add_parser("upload")
    upload.add_argument("local_path")
    upload.add_argument("remote_dir")
    upload.add_argument("--max-workers", type=int, default=4)
    upload.add_argument("--overwrite", action="store_true")
    upload.set_defaults(func=command_upload)

    share = commands.add_parser("share")
    share.add_argument("remote_paths", nargs="+")
    share.add_argument("--password")
    share.add_argument("--period-days", type=int, choices=[0, 1, 7, 30], default=7)
    share.set_defaults(func=command_share)

    upload_share = commands.add_parser("upload-share")
    upload_share.add_argument("local_path")
    upload_share.add_argument("remote_dir")
    upload_share.add_argument("--password")
    upload_share.add_argument("--period-days", type=int, choices=[0, 1, 7, 30], default=7)
    upload_share.add_argument("--max-workers", type=int, default=4)
    upload_share.add_argument("--overwrite", action="store_true")
    upload_share.set_defaults(func=command_upload_share)

    list_shares = commands.add_parser("list-shares")
    list_shares.add_argument("--all", action="store_true")
    list_shares.set_defaults(func=command_list_shares)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        args.func(args)
        return 0
    except Exception as exc:
        emit({"ok": False, "error": type(exc).__name__, "message": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
