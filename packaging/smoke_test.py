"""Smoke-test a built app by driving it over HTTP.

Deliberately talks to a *running binary* rather than importing anything: the
point is to exercise what ships, including the parts PyInstaller has to be told
about explicitly. A frozen build that imports cleanly and then reports zero
instruments is the exact failure this is here to catch (#117).

    python packaging/smoke_test.py dist/cellpy-simple-gui/cellpy-simple-gui.exe

Exits non-zero on the first failure, so it can gate a release (#124).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# The instruments a normal install discovers. cellpy builds these module names
# as strings at runtime, so this list is the whole point of the exercise.
EXPECTED_INSTRUMENTS = [
    "arbin_res", "arbin_sql", "arbin_sql_7", "arbin_sql_csv", "arbin_sql_h5",
    "arbin_sql_xlsx", "batmo_bdf", "biologics_mpr", "maccor_txt", "neware_nda",
    "neware_txt", "neware_xlsx", "pec_csv",
]

URL_RE = re.compile(r"http://127\.0\.0\.1:(\d+)/\?token=([A-Za-z0-9_-]+)")

failures: list[str] = []
passes: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    (passes if ok else failures).append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{'  — ' + detail if detail else ''}")
    return ok


class App:
    def __init__(self, exe: Path) -> None:
        self.proc = subprocess.Popen(
            [str(exe), "--server", "--no-open"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        self.base = ""
        self.token = ""
        self.log: list[str] = []

    def wait_for_url(self, timeout: float = 180.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = self.proc.stdout.readline()
            if not line:
                if self.proc.poll() is not None:
                    raise RuntimeError(
                        "app exited before serving:\n" + "".join(self.log[-40:])
                    )
                continue
            self.log.append(line)
            m = URL_RE.search(line)
            if m:
                self.base = f"http://127.0.0.1:{m.group(1)}"
                self.token = m.group(2)
                return
        raise RuntimeError("timed out waiting for the app to serve:\n" + "".join(self.log[-40:]))

    def call(self, path: str, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(
            f"{self.base}{path}", data=data, method="POST" if data else "GET"
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("X-CSG-Token", self.token)
        with urllib.request.urlopen(req, timeout=600) as r:
            body = r.read()
        try:
            return json.loads(body)
        except ValueError:
            return body

    def job(self, resp: dict, timeout: float = 600.0) -> dict:
        jid = resp["job_id"]
        deadline = time.time() + timeout
        while time.time() < deadline:
            st = self.call(f"/api/jobs/{jid}")
            if st.get("status") in ("done", "error", "cancelled"):
                return st
            time.sleep(0.2)
        return {"status": "timeout", "message": "job did not finish"}

    def close(self) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def main(exe: Path) -> int:
    if not exe.is_file():
        print(f"no such executable: {exe}")
        return 2

    print(f"smoke-testing {exe}")
    app = App(exe)
    try:
        t0 = time.perf_counter()
        app.wait_for_url()
        print(f"  (served in {time.perf_counter() - t0:.1f}s at {app.base})\n")

        caps = app.call("/api/system/capabilities")
        check("serves the API", isinstance(caps, dict) and "dev_mode" in caps)

        # --- the reason this file exists ---------------------------------- #
        found = sorted(i["id"] for i in app.call("/api/instruments")["instruments"])
        missing = [i for i in EXPECTED_INSTRUMENTS if i not in found]
        check(
            f"discovers all {len(EXPECTED_INSTRUMENTS)} instrument loaders",
            not missing,
            f"missing {missing}" if missing else f"found {len(found)}",
        )

        # --- real loaders, not just the registry --------------------------- #
        for kind, label in (("arbin", "Arbin .res (binary, ODBC)"), ("maccor", "Maccor (text)")):
            st = app.job(app.call("/api/ingest/example", {"kind": kind}))
            check(f"imports a real raw file — {label}", st.get("status") == "done",
                  st.get("message", "")[:120])

        # --- cells, collection, figure ------------------------------------- #
        st = app.job(app.call("/api/load/example", {"kinds": ["cellpy"]}))
        check("loads a bundled .cellpy cell", st.get("status") == "done",
              st.get("message", "")[:120])

        n_cells = len(app.call("/api/state")["cells"])
        check("has cells in the library", n_cells > 0, f"{n_cells} cells")

        fig = app.call("/api/plots/summary", {"plot_type": "capacity_ce", "basis": "gravimetric"})
        traces = len(fig.get("data", []))
        check("renders a summary figure", traces > 0, f"{traces} traces")

        cycles = app.call("/api/plots/cycles", {"cycles": [1, 2, 3], "curve_kind": "dqdv"})
        check("renders dQ/dV across cells", len(cycles.get("data", [])) > 0)

        data = app.call("/api/export/summary?fmt=csv",
                        {"plot_type": "capacity_ce", "basis": "gravimetric"})
        check("exports data as CSV", isinstance(data, bytes) and b"," in data[:200])
    finally:
        app.close()

    print(f"\n{len(passes)} passed, {len(failures)} failed")
    if failures:
        print("failed: " + ", ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(Path(sys.argv[1])))
