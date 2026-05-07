#!/usr/bin/env python3
"""
PySkyWiFi launcher - one command to rule them all.

Usage:
    python start.py

Sets HTTPS_PROXY and HTTP_PROXY so Claude Code routes through PySkyWiFi.
Also launches Chrome with proxy settings if Chrome is installed.
"""
import sys
import os
import subprocess
import time
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

PORT = 9090
CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]


def check_deps():
    missing = []
    for pkg, imp in [("httpx", "httpx"), ("github", "github"), ("yaml", "yaml"), ("werkzeug", "werkzeug")]:
        try:
            __import__(imp)
        except ImportError:
            missing.append(pkg)
    if missing:
        pkgs = {"github": "PyGithub", "yaml": "PyYAML"}.get
        install = [{"github": "PyGithub", "yaml": "PyYAML"}.get(p, p) for p in missing]
        print(f"Installing: {install}")
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + install, stdout=subprocess.DEVNULL)


def set_windows_proxy(port):
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                             0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, f"127.0.0.1:{port}")
        winreg.CloseKey(key)
        print(f"[*] Windows system proxy set to 127.0.0.1:{port} (used by Chrome, Edge, IE)")
    except Exception as e:
        print(f"[!] Could not set Windows proxy: {e}")


def unset_windows_proxy():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                             0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
        winreg.CloseKey(key)
        print("\n[*] Windows system proxy restored (disabled)")
    except Exception:
        pass


def launch_chrome(port):
    for path in CHROME_PATHS:
        if os.path.exists(path):
            subprocess.Popen([
                path,
                f"--proxy-server=http://127.0.0.1:{port}",
                "--no-first-run",
                "--new-window",
            ])
            print(f"[*] Chrome launched with proxy settings")
            return
    print("[!] Chrome not found - open it manually, proxy is already set system-wide")


def run_proxy(protocol):
    from PySkyWiFi.http.local_proxy import run
    run(protocol, port=PORT)


if __name__ == "__main__":
    print("=" * 50)
    print("  PySkyWiFi - In-flight internet tunnel")
    print("=" * 50)

    check_deps()

    # Always clear proxy settings on startup in case previous run didn't clean up
    unset_windows_proxy()
    for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "NO_PROXY", "no_proxy"]:
        os.environ.pop(k, None)

    # Import and init transports BEFORE setting any proxy env vars
    # so PyGithub connects directly to api.github.com
    from PySkyWiFi import Protocol
    from PySkyWiFi.transports.github import GithubTransport

    print(f"[*] Connecting to GitHub gists...")
    protocol = Protocol(
        send_pipe=GithubTransport.from_conf(1),
        rcv_pipe=GithubTransport.from_conf(2),
    )
    print(f"[*] Connected. Starting tunnel on port {PORT}...")
    print(f"[*] Make sure ground daemon is running on your desktop")
    print(f"[*] Press Ctrl+C to stop\n")

    # Start proxy in background thread
    proxy_thread = threading.Thread(target=run_proxy, args=(protocol,), daemon=True)
    proxy_thread.start()
    time.sleep(1)

    # Now safe to set proxy env vars — GitHub clients already initialised
    no_proxy = "api.github.com,localhost,127.0.0.1"
    os.environ["HTTP_PROXY"] = f"http://127.0.0.1:{PORT}"
    os.environ["HTTPS_PROXY"] = f"http://127.0.0.1:{PORT}"
    os.environ["http_proxy"] = f"http://127.0.0.1:{PORT}"
    os.environ["https_proxy"] = f"http://127.0.0.1:{PORT}"
    os.environ["NO_PROXY"] = no_proxy
    os.environ["no_proxy"] = no_proxy
    print(f"[*] HTTP_PROXY / HTTPS_PROXY -> http://127.0.0.1:{PORT}")
    print(f"[*] NO_PROXY -> {no_proxy}")

    set_windows_proxy(PORT)
    launch_chrome(PORT)

    print(f"[*] Ready. Tunnel is live.\n")

    try:
        proxy_thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        unset_windows_proxy()
        print("[*] Done.")
