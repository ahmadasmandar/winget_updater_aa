import logging
import os
import shutil
import subprocess
import time

from .parser import parse_json_output, parse_upgrade_output

logger = logging.getLogger(__name__)
WINGET_EXE = shutil.which("winget") or os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WindowsApps", "winget.exe")
if not os.path.isfile(WINGET_EXE):
    class StartupError(RuntimeError):
        pass
    raise StartupError(f"winget executable was not found: {WINGET_EXE}")
class StartupError(RuntimeError):
    pass

WINGET_CODES = {
    0: "success", 0x8A15002B: "no_applicable_upgrade", 0x881A001F: "no_applicable_upgrade",
    0x881A002B: "no_applicable_upgrade", 0x8A150014: "package_not_found",
    0x8A15003B: "installer_technology_mismatch", 0x881A008E: "installer_technology_mismatch",
}
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x10)


class WingetError(RuntimeError):
    pass


class WingetBackend:
    def __init__(self, executable=WINGET_EXE, log=None):
        self.executable = executable
        self.log = log or logger

    def _command(self, args):
        return [self.executable, *args]

    def run(self, args, timeout, cancelled=None, visible=False):
        command = self._command(args)
        self.log.info("Running: %s", subprocess.list2cmdline(command))
        if visible:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=None, stderr=None, creationflags=CREATE_NEW_CONSOLE)
            started = time.monotonic()
            try:
                while process.poll() is None:
                    if cancelled and cancelled():
                        process.terminate()
                        raise WingetError("Operation cancelled")
                    if time.monotonic() - started >= timeout:
                        process.kill()
                        raise WingetError("winget operation timed out")
                    time.sleep(0.2)
                self.log.info("winget exited with return code %s", process.returncode)
                return process.returncode, ""
            except OSError as exc:
                raise WingetError(str(exc)) from exc
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                   encoding="utf-8", errors="replace", creationflags=CREATE_NO_WINDOW)
        output = ""
        try:
            while process.poll() is None:
                if cancelled and cancelled():
                    process.terminate()
                    raise WingetError("Operation cancelled")
                try:
                    chunk, _ = process.communicate(timeout=0.2)
                    output += chunk or ""
                    break
                except subprocess.TimeoutExpired as exc:
                    output += (exc.stdout or "") if isinstance(exc.stdout, str) else ""
                    if timeout <= 0:
                        process.kill()
                        raise WingetError("winget operation timed out")
                    timeout -= 0.2
            if process.returncode is None:
                process.wait(timeout=1)
            return process.returncode, output
        except subprocess.TimeoutExpired as exc:
            process.kill()
            raise WingetError("winget operation timed out") from exc

    def list_packages(self, cancelled=None):
        args = ["upgrade", "--include-unknown", "--disable-interactivity", "--accept-source-agreements", "--output", "json"]
        code, output = self.run(args, 60, cancelled)
        if code == 0:
            try:
                return parse_json_output(output)
            except (ValueError, TypeError, AttributeError):
                self.log.warning("JSON output could not be parsed; using text parser")
        fallback = ["upgrade", "--include-unknown", "--disable-interactivity", "--accept-source-agreements"]
        code, output = self.run(fallback, 60, cancelled)
        if code not in (0, 0x8A15002B, 0x881A002B, 0x881A001F):
            raise WingetError(f"winget upgrade query failed with code {code}")
        return parse_upgrade_output(output)

    def operation(self, args, timeout=1800, cancelled=None, visible=True):
        return self.run([*args, "--disable-interactivity"], timeout, cancelled, visible=visible)

    def info(self, package_id, cancelled=None):
        return self.run(["show", "--id", package_id, "-e", "--disable-interactivity"], 30, cancelled)

    def version(self):
        return self.run(["--version"], 30)[1].strip()
