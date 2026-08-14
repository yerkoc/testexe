from pathlib import Path
from datetime import datetime
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


APP_NAME = "Test EXE"
VERSION_FILE = Path(__file__).with_name("version.txt")
LATEST_RELEASE_URL = "https://github.com/yerkoc/testexe/releases/latest"
DOWNLOAD_URL_TEMPLATE = "https://github.com/yerkoc/testexe/releases/download/v{version}/{asset_name}"
VERSIONED_EXE_PATTERN = re.compile(r"^TestEXE-(\d+\.\d+\.\d+)\.exe$", re.IGNORECASE)
COLORS = {
    "bg": "#e8eef5",
    "panel": "#f8fafc",
    "panel_alt": "#eef4f8",
    "text": "#17212f",
    "muted": "#526173",
    "accent": "#176b87",
    "accent_dark": "#0f4f63",
    "border": "#cbd7e3",
}
CHANGELOG = [
    (
        "v1.0.4",
        [
            "PC Durum Paneli'ne tarih ve saat bilgisi eklendi.",
            "Sistem raporuna rapor olu\u015fturma zaman\u0131 eklendi.",
        ],
    ),
    (
        "v1.0.3",
        [
            "Uygulama a\u00e7\u0131l\u0131\u015f\u0131nda yeni s\u00fcr\u00fcm kontrol\u00fc eklendi.",
            "Yeni s\u00fcr\u00fcm varsa kullan\u0131c\u0131ya k\u00fc\u00e7\u00fck kurulum uyar\u0131s\u0131 g\u00f6steriliyor.",
        ],
    ),
    (
        "v1.0.2",
        [
            "PC Durum Paneli arka plan ve panel renkleri yenilendi.",
            "Ba\u015fl\u0131k, durum \u00e7ubu\u011fu ve rapor alanlar\u0131 daha okunur hale getirildi.",
        ],
    ),
    (
        "v1.0.1",
        [
            "Uygulama PC Durum Paneli olarak yeniden tasarland\u0131.",
            "Windows, cihaz, CPU, RAM, disk ve IP bilgileri eklendi.",
            "Raporu yenileme ve panoya kopyalama kontrolleri eklendi.",
        ],
    ),
    (
        "v1.0.0",
        [
            "Installer tabanl\u0131 ilk temiz s\u00fcr\u00fcm yay\u0131nland\u0131.",
            "G\u00fcncelleme ve \u00f6nceki s\u00fcr\u00fcme d\u00f6n\u00fc\u015f altyap\u0131s\u0131 haz\u0131rland\u0131.",
        ],
    ),
]


def read_version() -> str:
    try:
        from build_version import VERSION

        return VERSION
    except ImportError:
        pass

    if VERSION_FILE.exists():
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    return "0.0.0"


def parse_version(version: str) -> tuple[int, int, int]:
    parts = version.strip().lstrip("v").split(".")
    return tuple(int(part) for part in parts[:3])


def version_from_exe_name(path: Path) -> str | None:
    match = VERSIONED_EXE_PATTERN.match(path.name)
    if not match:
        return None
    return match.group(1)


def http_request(url: str) -> Request:
    return Request(url, headers={"User-Agent": "TestEXE-Updater"})


def fetch_latest_version() -> str:
    with urlopen(http_request(LATEST_RELEASE_URL), timeout=10) as response:
        latest_url = response.url.rstrip("/")
    return latest_url.rsplit("/", 1)[-1].lstrip("v")


def build_asset_url(version: str, setup: bool = True) -> tuple[str, str]:
    if setup:
        asset_name = f"TestEXE-Setup-{version}.exe"
    else:
        asset_name = f"TestEXE-{version}.exe"
    return asset_name, DOWNLOAD_URL_TEMPLATE.format(version=version, asset_name=asset_name)


def find_previous_release_version() -> str | None:
    current_version = parse_version(read_version())
    if current_version[2] <= 0:
        return None
    return f"{current_version[0]}.{current_version[1]}.{current_version[2] - 1}"


def download_file(url: str, target_path: Path) -> None:
    with urlopen(http_request(url), timeout=60) as response:
        target_path.write_bytes(response.read())


def clean_pyinstaller_env() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("_PYI") and key != "_MEIPASS"
    }


def launch_exe_and_exit(exe_path: Path) -> None:
    env = clean_pyinstaller_env()
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    subprocess.Popen(
        [str(exe_path)],
        cwd=str(exe_path.parent),
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    os._exit(0)


def launch_installer_and_exit(installer_path: Path) -> None:
    env = clean_pyinstaller_env()
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    subprocess.Popen(
        [str(installer_path)],
        cwd=str(installer_path.parent),
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    os._exit(0)


def find_previous_version_exe() -> tuple[Path, str] | None:
    current_version = parse_version(read_version())
    current_exe = Path(sys.executable).resolve()
    candidates: list[tuple[tuple[int, int, int], Path, str]] = []

    for exe_path in current_exe.parent.glob("TestEXE-*.exe"):
        if exe_path.resolve() == current_exe:
            continue

        version = version_from_exe_name(exe_path)
        if not version:
            continue

        parsed_version = parse_version(version)
        if parsed_version < current_version:
            candidates.append((parsed_version, exe_path, version))

    if not candidates:
        return None

    _, exe_path, version = max(candidates, key=lambda item: item[0])
    return exe_path, version


def rollback_to_previous_version(root: tk.Tk, status_label: ttk.Label) -> None:
    previous = find_previous_version_exe()
    try:
        if previous:
            exe_path, version = previous
            answer = messagebox.askyesno(
                APP_NAME,
                f"{version} s\u00fcr\u00fcm\u00fcne d\u00f6nmek ister misin?",
            )
            if not answer:
                status_label.config(text="\u00d6nceki s\u00fcr\u00fcme d\u00f6n\u00fc\u015f iptal edildi.")
                return

            status_label.config(text=f"{version} s\u00fcr\u00fcm\u00fc ba\u015flat\u0131l\u0131yor...")
            root.update_idletasks()
            launch_exe_and_exit(exe_path)

        status_label.config(text="\u00d6nceki s\u00fcr\u00fcm GitHub'da aran\u0131yor...")
        root.update_idletasks()

        version = find_previous_release_version()
        if not version:
            status_label.config(text="\u00d6nceki s\u00fcr\u00fcm bulunamad\u0131.")
            messagebox.showinfo(APP_NAME, "\u00d6nceki s\u00fcr\u00fcm dosyas\u0131 bulunamad\u0131.")
            return

        answer = messagebox.askyesno(
            APP_NAME,
            f"{version} s\u00fcr\u00fcm\u00fc indirilecek ve kurulacak.\n\nDevam etmek ister misin?",
        )
        if not answer:
            status_label.config(text="\u00d6nceki s\u00fcr\u00fcme d\u00f6n\u00fc\u015f iptal edildi.")
            return

        status_label.config(text=f"{version} s\u00fcr\u00fcm\u00fc indiriliyor...")
        root.update_idletasks()

        asset_name, download_url = build_asset_url(version, setup=True)
        target_path = Path(tempfile.gettempdir()) / asset_name
        download_file(download_url, target_path)
        launch_installer_and_exit(target_path)
    except (HTTPError, ValueError, URLError, RuntimeError) as exc:
        status_label.config(text="\u00d6nceki s\u00fcr\u00fcme d\u00f6n\u00fc\u015f ba\u015far\u0131s\u0131z oldu.")
        messagebox.showerror(APP_NAME, f"\u00d6nceki s\u00fcr\u00fcme d\u00f6n\u00fclemedi:\n{exc}")


def install_update(downloaded_exe: Path) -> None:
    current_exe = Path(sys.executable)
    installed_exe = current_exe.with_name(downloaded_exe.name)
    updater = Path(tempfile.gettempdir()) / "testexe_update.ps1"
    source_path = str(downloaded_exe).replace("'", "''")
    target_path = str(installed_exe).replace("'", "''")

    updater.write_text(
        "\n".join(
            [
                "$ErrorActionPreference = 'Stop'",
                f"$source = '{source_path}'",
                f"$target = '{target_path}'",
                f"$oldPid = {os.getpid()}",
                "Wait-Process -Id $oldPid -Timeout 30 -ErrorAction SilentlyContinue",
                "Start-Sleep -Milliseconds 750",
                "$updated = $false",
                "for ($i = 0; $i -lt 10; $i++) {",
                "    try {",
                "        Copy-Item -LiteralPath $source -Destination $target -Force",
                "        $updated = $true",
                "        break",
                "    } catch {",
                "        Start-Sleep -Seconds 1",
                "    }",
                "}",
                "if ($updated) {",
                "    Start-Sleep -Seconds 1",
                "    Get-ChildItem Env: |",
                "        Where-Object { $_.Name -like '_PYI*' -or $_.Name -eq '_MEIPASS' } |",
                "        ForEach-Object { Remove-Item -LiteralPath ('Env:' + $_.Name) -ErrorAction SilentlyContinue }",
                "    $env:PYINSTALLER_RESET_ENVIRONMENT = '1'",
                "    Start-Process -FilePath $target",
                "    Start-Sleep -Seconds 2",
                "    Remove-Item -LiteralPath $source -Force -ErrorAction SilentlyContinue",
                "}",
                "Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue",
            ]
        ),
        encoding="utf-8",
    )
    subprocess.Popen(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-WindowStyle",
            "Hidden",
            "-File",
            str(updater),
        ],
        env=clean_pyinstaller_env(),
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    os._exit(0)


def check_for_updates(root: tk.Tk, status_label: ttk.Label) -> None:
    status_label.config(text="G\u00fcncellemeler kontrol ediliyor...")
    root.update_idletasks()

    try:
        current_version = read_version()
        latest_version = fetch_latest_version()

        if parse_version(latest_version) <= parse_version(current_version):
            status_label.config(text="En g\u00fcncel s\u00fcr\u00fcm\u00fc kullan\u0131yorsun.")
            messagebox.showinfo(APP_NAME, f"Zaten en g\u00fcncel s\u00fcr\u00fcm y\u00fckl\u00fc: {current_version}")
            return

        answer = messagebox.askyesno(
            APP_NAME,
            f"{latest_version} s\u00fcr\u00fcm\u00fc mevcut.\n\n\u015eimdi indirip kurmak ister misin?",
        )
        if not answer:
            status_label.config(text=f"G\u00fcncelleme mevcut: {latest_version}")
            return

        status_label.config(text=f"{latest_version} s\u00fcr\u00fcm\u00fc indiriliyor...")
        root.update_idletasks()

        asset_name, download_url = build_asset_url(latest_version, setup=True)
        target_path = Path(tempfile.gettempdir()) / asset_name
        download_file(download_url, target_path)
        launch_installer_and_exit(target_path)
    except (HTTPError, ValueError, URLError, RuntimeError) as exc:
        status_label.config(text="G\u00fcncelleme kontrol\u00fc ba\u015far\u0131s\u0131z oldu.")
        messagebox.showerror(APP_NAME, f"G\u00fcncellemeler kontrol edilemedi:\n{exc}")


def prompt_update_install(root: tk.Tk, status_label: ttk.Label, latest_version: str) -> None:
    answer = messagebox.askyesno(
        APP_NAME,
        f"Yeni s\u00fcr\u00fcm mevcut: {latest_version}\n\n\u015eimdi indirip kurmak ister misin?",
    )
    if not answer:
        status_label.config(text=f"Yeni s\u00fcr\u00fcm mevcut: {latest_version}")
        return

    status_label.config(text=f"{latest_version} s\u00fcr\u00fcm\u00fc indiriliyor...")
    root.update_idletasks()

    try:
        asset_name, download_url = build_asset_url(latest_version, setup=True)
        target_path = Path(tempfile.gettempdir()) / asset_name
        download_file(download_url, target_path)
        launch_installer_and_exit(target_path)
    except (HTTPError, ValueError, URLError, RuntimeError) as exc:
        status_label.config(text="G\u00fcncelleme indirilemedi.")
        messagebox.showerror(APP_NAME, f"G\u00fcncelleme indirilemedi:\n{exc}")


def check_for_updates_on_startup(root: tk.Tk, status_label: ttk.Label) -> None:
    def worker() -> None:
        try:
            current_version = read_version()
            latest_version = fetch_latest_version()
            if parse_version(latest_version) > parse_version(current_version):
                root.after(0, lambda: prompt_update_install(root, status_label, latest_version))
            else:
                root.after(0, lambda: status_label.config(text="A\u00e7\u0131l\u0131\u015fta g\u00fcncelleme bulunamad\u0131."))
        except (HTTPError, ValueError, URLError, RuntimeError):
            root.after(0, lambda: status_label.config(text="A\u00e7\u0131l\u0131\u015fta g\u00fcncelleme kontrol\u00fc yap\u0131lamad\u0131."))

    status_label.config(text="A\u00e7\u0131l\u0131\u015fta g\u00fcncelleme kontrol ediliyor...")
    threading.Thread(target=worker, daemon=True).start()


def bytes_to_gb(value: int) -> str:
    return f"{value / (1024 ** 3):.1f} GB"


def get_memory_info() -> tuple[str, str, str]:
    if os.name != "nt":
        return "Bilinmiyor", "Bilinmiyor", "Bilinmiyor"

    import ctypes

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    memory = MemoryStatus()
    memory.dwLength = ctypes.sizeof(MemoryStatus)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory))
    used = memory.ullTotalPhys - memory.ullAvailPhys
    return bytes_to_gb(memory.ullTotalPhys), bytes_to_gb(used), f"%{memory.dwMemoryLoad}"


def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "Bilinmiyor"


def collect_system_info() -> dict[str, str]:
    disk = shutil.disk_usage(Path.home().anchor or "C:\\")
    total_memory, used_memory, memory_load = get_memory_info()
    username = os.environ.get("USERNAME") or os.environ.get("USER") or "Bilinmiyor"
    now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    return {
        "Uygulama S\u00fcr\u00fcm\u00fc": read_version(),
        "Tarih ve Saat": now,
        "Bilgisayar Ad\u0131": platform.node() or "Bilinmiyor",
        "Kullan\u0131c\u0131": username,
        "Windows": platform.platform(),
        "\u0130\u015flemci": platform.processor() or "Bilinmiyor",
        "CPU \u00c7ekirdek": str(os.cpu_count() or "Bilinmiyor"),
        "RAM Toplam": total_memory,
        "RAM Kullan\u0131m": f"{used_memory} ({memory_load})",
        "Disk Toplam": bytes_to_gb(disk.total),
        "Disk Bo\u015f": bytes_to_gb(disk.free),
        "Yerel IP": get_local_ip(),
        "Python": platform.python_version(),
    }


def build_report(info: dict[str, str]) -> str:
    lines = ["Test EXE PC Durum Raporu", ""]
    lines.extend(f"{key}: {value}" for key, value in info.items())
    return "\n".join(lines)


def changelog_text() -> str:
    lines = []
    for version, changes in CHANGELOG:
        lines.append(version)
        lines.extend(f"- {change}" for change in changes)
        lines.append("")
    return "\n".join(lines).strip()


def set_readonly_text(widget: tk.Text, value: str) -> None:
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", value)
    widget.configure(state="disabled")


def refresh_dashboard(metrics: dict[str, tk.StringVar], report_box: tk.Text, status_label: ttk.Label) -> None:
    info = collect_system_info()
    for key, variable in metrics.items():
        variable.set(info.get(key, "Bilinmiyor"))
    set_readonly_text(report_box, build_report(info))
    status_label.config(text="Sistem bilgileri yenilendi.")


def copy_report(root: tk.Tk, report_box: tk.Text, status_label: ttk.Label) -> None:
    report = report_box.get("1.0", "end-1c")
    root.clipboard_clear()
    root.clipboard_append(report)
    status_label.config(text="Sistem raporu panoya kopyaland\u0131.")


def main() -> None:
    root = tk.Tk()
    root.title(f"{APP_NAME} PC Durum Paneli")
    root.geometry("860x560")
    root.minsize(800, 520)
    root.configure(bg=COLORS["bg"])

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", font=("Segoe UI", 9), background=COLORS["bg"], foreground=COLORS["text"])
    style.configure("App.TFrame", background=COLORS["bg"])
    style.configure("Panel.TFrame", background=COLORS["panel"], bordercolor=COLORS["border"], relief="solid")
    style.configure("Header.TFrame", background=COLORS["accent"])
    style.configure("Footer.TFrame", background=COLORS["bg"])
    style.configure("HeaderTitle.TLabel", background=COLORS["accent"], foreground="#ffffff", font=("Segoe UI", 18, "bold"))
    style.configure("HeaderVersion.TLabel", background=COLORS["accent"], foreground="#e8f4f8", font=("Segoe UI", 10))
    style.configure("Section.TLabel", background=COLORS["panel"], foreground=COLORS["accent_dark"], font=("Segoe UI", 11, "bold"))
    style.configure("MetricName.TLabel", background=COLORS["panel"], foreground=COLORS["muted"], font=("Segoe UI", 9, "bold"))
    style.configure("MetricValue.TLabel", background=COLORS["panel"], foreground=COLORS["text"])
    style.configure("Status.TLabel", background=COLORS["panel_alt"], foreground=COLORS["muted"], padding=(16, 7))
    style.configure("TButton", padding=(10, 6))
    style.map("TButton", background=[("active", "#dbe8ef")])

    root.columnconfigure(0, weight=2)
    root.columnconfigure(1, weight=3)
    root.rowconfigure(1, weight=1)

    header = ttk.Frame(root, padding=(18, 16, 18, 14), style="Header.TFrame")
    header.grid(row=0, column=0, columnspan=2, sticky="ew")
    header.columnconfigure(0, weight=1)

    title = ttk.Label(header, text="Test EXE PC Durum Paneli", style="HeaderTitle.TLabel")
    title.grid(row=0, column=0, sticky="w")

    version = ttk.Label(header, text=f"S\u00fcr\u00fcm: {read_version()}", style="HeaderVersion.TLabel")
    version.grid(row=0, column=1, sticky="e")

    metrics_frame = ttk.Frame(root, padding=(18, 16, 14, 16), style="Panel.TFrame")
    metrics_frame.grid(row=1, column=0, sticky="nsew", padx=(16, 8), pady=16)
    metrics_frame.columnconfigure(1, weight=1)

    metrics_label = ttk.Label(metrics_frame, text="Canl\u0131 Sistem Bilgileri", style="Section.TLabel")
    metrics_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

    metric_names = [
        "Tarih ve Saat",
        "Bilgisayar Ad\u0131",
        "Kullan\u0131c\u0131",
        "Windows",
        "\u0130\u015flemci",
        "CPU \u00c7ekirdek",
        "RAM Toplam",
        "RAM Kullan\u0131m",
        "Disk Toplam",
        "Disk Bo\u015f",
        "Yerel IP",
    ]
    metrics: dict[str, tk.StringVar] = {}
    for row, name in enumerate(metric_names, start=1):
        ttk.Label(metrics_frame, text=f"{name}:", style="MetricName.TLabel").grid(
            row=row, column=0, sticky="nw", pady=4, padx=(0, 8)
        )
        value = tk.StringVar(value="Y\u00fckleniyor...")
        metrics[name] = value
        ttk.Label(metrics_frame, textvariable=value, wraplength=280, style="MetricValue.TLabel").grid(
            row=row, column=1, sticky="ew", pady=4
        )

    detail_frame = ttk.Frame(root, padding=(16, 16, 18, 16), style="Panel.TFrame")
    detail_frame.grid(row=1, column=1, sticky="nsew", padx=(8, 16), pady=16)
    detail_frame.columnconfigure(0, weight=1)
    detail_frame.rowconfigure(1, weight=2)
    detail_frame.rowconfigure(4, weight=1)

    report_label = ttk.Label(detail_frame, text="Sistem Raporu", style="Section.TLabel")
    report_label.grid(row=0, column=0, sticky="w", pady=(0, 6))

    report_box = tk.Text(
        detail_frame,
        wrap="word",
        font=("Consolas", 9),
        height=12,
        bg="#fbfdff",
        fg=COLORS["text"],
        relief="solid",
        bd=1,
        highlightthickness=1,
        highlightbackground=COLORS["border"],
        insertbackground=COLORS["accent"],
    )
    report_box.grid(row=1, column=0, sticky="nsew")
    report_box.configure(state="disabled")

    report_scroll = ttk.Scrollbar(detail_frame, command=report_box.yview)
    report_scroll.grid(row=1, column=1, sticky="ns")
    report_box.configure(yscrollcommand=report_scroll.set)

    changelog_label = ttk.Label(detail_frame, text="S\u00fcr\u00fcm G\u00fcnl\u00fc\u011f\u00fc", style="Section.TLabel")
    changelog_label.grid(row=3, column=0, sticky="w", pady=(14, 6))

    changelog = tk.Text(
        detail_frame,
        wrap="word",
        font=("Segoe UI", 9),
        height=8,
        bg="#fbfdff",
        fg=COLORS["text"],
        relief="solid",
        bd=1,
        highlightthickness=1,
        highlightbackground=COLORS["border"],
    )
    changelog.grid(row=4, column=0, sticky="nsew")
    changelog.insert("1.0", changelog_text())
    changelog.configure(state="disabled")

    changelog_scroll = ttk.Scrollbar(detail_frame, command=changelog.yview)
    changelog_scroll.grid(row=4, column=1, sticky="ns")
    changelog.configure(yscrollcommand=changelog_scroll.set)

    status = ttk.Label(root, text="PC Durum Paneli haz\u0131r.", style="Status.TLabel")
    status.grid(row=3, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 14))

    app_buttons = ttk.Frame(root, padding=(16, 0, 16, 0), style="Footer.TFrame")
    app_buttons.grid(row=2, column=0, columnspan=2, sticky="ew")
    app_buttons.columnconfigure(0, weight=1)

    ttk.Button(
        app_buttons,
        text="Yenile",
        command=lambda: refresh_dashboard(metrics, report_box, status),
    ).pack(side="left", padx=(0, 8))
    ttk.Button(
        app_buttons,
        text="Raporu kopyala",
        command=lambda: copy_report(root, report_box, status),
    ).pack(side="left", padx=(0, 8))
    ttk.Button(
        app_buttons,
        text="G\u00fcncellemeleri kontrol et",
        command=lambda: check_for_updates(root, status),
    ).pack(side="left", padx=(0, 8))
    ttk.Button(
        app_buttons,
        text="\u00d6nceki s\u00fcr\u00fcme d\u00f6n",
        command=lambda: rollback_to_previous_version(root, status),
    ).pack(side="left", padx=(0, 8))
    ttk.Button(app_buttons, text="Kapat", command=root.destroy).pack(side="right")

    refresh_dashboard(metrics, report_box, status)
    root.after(1500, lambda: check_for_updates_on_startup(root, status))

    root.mainloop()


if __name__ == "__main__":
    main()
