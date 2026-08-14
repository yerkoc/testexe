from pathlib import Path
import os
import re
import subprocess
import sys
import tempfile
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
NOTES_FILE = Path.home() / "Documents" / "testexe_not.txt"
CHANGELOG = [
    (
        "v1.0.0",
        [
            "Mini not defteri uygulamas\u0131 yay\u0131na haz\u0131r ilk s\u00fcr\u00fcm olarak d\u00fczenlendi.",
            "Not kaydetme, a\u00e7ma ve temizleme \u00f6zellikleri eklendi.",
            "Installer tabanl\u0131 g\u00fcncelleme sistemi haz\u0131rland\u0131.",
            "S\u00fcr\u00fcm g\u00fcnl\u00fc\u011f\u00fc ve \u00f6nceki s\u00fcr\u00fcme d\u00f6n\u00fc\u015f kontrolleri eklendi.",
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


def save_note(note_text: tk.Text, status_label: ttk.Label) -> None:
    NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    NOTES_FILE.write_text(note_text.get("1.0", "end-1c"), encoding="utf-8")
    status_label.config(text=f"Not kaydedildi: {NOTES_FILE}")


def open_note(note_text: tk.Text, status_label: ttk.Label) -> None:
    if not NOTES_FILE.exists():
        status_label.config(text="Kaydedilmi\u015f not bulunamad\u0131.")
        messagebox.showinfo(APP_NAME, "Hen\u00fcz kaydedilmi\u015f bir not yok.")
        return

    note_text.delete("1.0", "end")
    note_text.insert("1.0", NOTES_FILE.read_text(encoding="utf-8"))
    status_label.config(text=f"Not a\u00e7\u0131ld\u0131: {NOTES_FILE}")


def clear_note(note_text: tk.Text, status_label: ttk.Label) -> None:
    note_text.delete("1.0", "end")
    status_label.config(text="Not alan\u0131 temizlendi.")


def changelog_text() -> str:
    lines = []
    for version, changes in CHANGELOG:
        lines.append(version)
        lines.extend(f"- {change}" for change in changes)
        lines.append("")
    return "\n".join(lines).strip()


def main() -> None:
    root = tk.Tk()
    root.title(f"{APP_NAME} Not Defteri")
    root.geometry("760x520")
    root.minsize(720, 480)

    root.columnconfigure(0, weight=3)
    root.columnconfigure(1, weight=2)
    root.rowconfigure(1, weight=1)

    header = ttk.Frame(root, padding=(16, 14, 16, 8))
    header.grid(row=0, column=0, columnspan=2, sticky="ew")
    header.columnconfigure(0, weight=1)

    title = ttk.Label(header, text="Test EXE Not Defteri", font=("Segoe UI", 18, "bold"))
    title.grid(row=0, column=0, sticky="w")

    version = ttk.Label(header, text=f"S\u00fcr\u00fcm: {read_version()}", font=("Segoe UI", 10))
    version.grid(row=0, column=1, sticky="e")

    note_frame = ttk.Frame(root, padding=(16, 8, 8, 8))
    note_frame.grid(row=1, column=0, sticky="nsew")
    note_frame.columnconfigure(0, weight=1)
    note_frame.rowconfigure(1, weight=1)

    note_label = ttk.Label(note_frame, text="Notlar", font=("Segoe UI", 11, "bold"))
    note_label.grid(row=0, column=0, sticky="w", pady=(0, 6))

    note_text = tk.Text(note_frame, wrap="word", undo=True, font=("Segoe UI", 10), height=12)
    note_text.grid(row=1, column=0, sticky="nsew")

    note_scroll = ttk.Scrollbar(note_frame, command=note_text.yview)
    note_scroll.grid(row=1, column=1, sticky="ns")
    note_text.configure(yscrollcommand=note_scroll.set)

    note_buttons = ttk.Frame(note_frame)
    note_buttons.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

    side_frame = ttk.Frame(root, padding=(8, 8, 16, 8))
    side_frame.grid(row=1, column=1, sticky="nsew")
    side_frame.columnconfigure(0, weight=1)
    side_frame.rowconfigure(1, weight=1)

    changelog_label = ttk.Label(side_frame, text="S\u00fcr\u00fcm G\u00fcnl\u00fc\u011f\u00fc", font=("Segoe UI", 11, "bold"))
    changelog_label.grid(row=0, column=0, sticky="w", pady=(0, 6))

    changelog = tk.Text(side_frame, wrap="word", font=("Segoe UI", 9), height=12)
    changelog.grid(row=1, column=0, sticky="nsew")
    changelog.insert("1.0", changelog_text())
    changelog.configure(state="disabled")

    changelog_scroll = ttk.Scrollbar(side_frame, command=changelog.yview)
    changelog_scroll.grid(row=1, column=1, sticky="ns")
    changelog.configure(yscrollcommand=changelog_scroll.set)

    status = ttk.Label(root, text="Mini not defteri haz\u0131r.", font=("Segoe UI", 9), padding=(16, 6))
    status.grid(row=3, column=0, columnspan=2, sticky="ew")

    ttk.Button(note_buttons, text="Kaydet", command=lambda: save_note(note_text, status)).pack(side="left", padx=(0, 8))
    ttk.Button(note_buttons, text="A\u00e7", command=lambda: open_note(note_text, status)).pack(side="left", padx=(0, 8))
    ttk.Button(note_buttons, text="Temizle", command=lambda: clear_note(note_text, status)).pack(side="left")

    app_buttons = ttk.Frame(root, padding=(16, 4, 16, 14))
    app_buttons.grid(row=2, column=0, columnspan=2, sticky="ew")
    app_buttons.columnconfigure(0, weight=1)

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

    root.mainloop()


if __name__ == "__main__":
    main()
