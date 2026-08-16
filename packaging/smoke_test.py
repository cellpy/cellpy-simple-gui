"""Smoke-test a built app by driving it over HTTP.

Deliberately talks to a *running app* rather than importing anything: the point
is to exercise what ships. A frozen build that imports cleanly and then reports
zero instruments is the exact failure this is here to catch (#117), and a
container that starts but cannot write its volume is the same shape of bug.

Two ways in:

    python packaging/smoke_test.py dist/cellpy-simple-gui/cellpy-simple-gui.exe
    python packaging/smoke_test.py --url http://127.0.0.1:8577 --token TOKEN

The first launches the binary and reads its token from the startup log; the
second attaches to something already running — a container, a staging instance
(#121). The checks are the same either way, plus the ones that only mean
something when the app is served off loopback.

Exits non-zero on the first failure, so it can gate a release (#124).
"""

from __future__ import annotations

import argparse
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

URL_RE = re.compile(r"http://[\d.]+:(\d+)/\?token=([A-Za-z0-9_-]+)")

failures: list[str] = []
passes: list[str] = []
skips: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    (passes if ok else failures).append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{'  — ' + detail if detail else ''}")
    return ok


def skip(name: str, detail: str) -> None:
    """A capability this machine genuinely lacks, as opposed to a broken build.

    Deliberately not a PASS. The whole lesson of this file is that a green tick
    which does not distinguish "it worked" from "it could not be tried" is worse
    than a red one — so skips are printed, counted and listed at the end. They
    just do not fail the run, because a release must not be blocked by a vendor
    driver we do not ship.
    """
    skips.append(name)
    print(f"  SKIP  {name}  — {detail}")


#: Reading Arbin `.res` needs a reader for Access databases — the Microsoft
#: Access ODBC driver on Windows, mdbtools on posix — and neither is on a stock
#: machine. Matched narrowly: any *other* Arbin failure is still a failure.
#:
#: Two vocabularies, on purpose. The app translates these into advice (#143), so
#: what a current build reports is *our* phrasing; the raw driver text is what
#: an older build, or an untranslated path, still emits.
#:
#: Worth the redundancy: this check first matched only the raw text, and then
#: #143 rewrote that text one PR later, silently turning the skip back into a
#: failure. Matching a message is fragile in exactly this way — our own wording
#: is at least a string we control and would notice changing.
_MISSING_ODBC = (
    # our translation
    "access database engine",
    "mdbtools",
    # the raw driver errors underneath it
    "im002",
    "odbc driver manager",
    "no default driver",
    "mdb-export",
)


class Client:
    """Talks to an app that is already serving."""

    def __init__(self, base: str, token: str) -> None:
        self.base = base.rstrip("/")
        self.token = token

    def call(self, path: str, payload=None, *, method: str | None = None,
             raw: bool = False):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(
            f"{self.base}{path}", data=data,
            method=method or ("POST" if data else "GET"),
        )
        req.add_header("Content-Type", "application/json")
        if not raw:
            req.add_header("X-CSG-Token", self.token)
        with urllib.request.urlopen(req, timeout=600) as r:
            body = r.read()
        try:
            return json.loads(body)
        except ValueError:
            return body

    def status(self, path: str, *, with_token: bool) -> int:
        """The HTTP status alone — for checking that a guard actually guards."""
        req = urllib.request.Request(f"{self.base}{path}")
        if with_token:
            req.add_header("X-CSG-Token", self.token)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status
        except urllib.error.HTTPError as exc:
            return exc.code

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
        pass


class LaunchedApp(Client):
    """Launches a binary and picks its URL and token out of the startup log."""

    def __init__(self, exe: Path) -> None:
        self.proc = subprocess.Popen(
            [str(exe), "--server", "--no-open"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        self.log: list[str] = []
        super().__init__("", "")

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
        raise RuntimeError(
            "timed out waiting for the app to serve:\n" + "".join(self.log[-40:])
        )

    def close(self) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def run_checks(app: Client) -> None:
    caps = app.call("/api/system/capabilities")
    check("serves the API", isinstance(caps, dict) and "dev_mode" in caps)

    # The token has to actually guard, not merely exist.
    check("refuses the API without a token",
          app.status("/api/system/capabilities", with_token=False) == 401)

    served = caps.get("host_paths_allowed") is False
    if served:
        # Bound off loopback: the #120 sandbox must be active, and a host path
        # must be refused rather than read.
        check("confines paths to the data directory",
              bool(caps.get("sandbox_root")), str(caps.get("sandbox_root")))

        # classify-import guards *first*, so the refusal can only come from the
        # sandbox. Going through /projects/open instead would pass on a plain
        # "no such project" 404 and prove nothing.
        detail = ""
        try:
            app.call("/api/projects/classify-import", {"path": "/etc/hostname"})
        except urllib.error.HTTPError as exc:
            detail = (json.loads(exc.read() or b"{}").get("detail") or "")[:120]
        check("refuses a host path outside the sandbox",
              "outside the data directory" in detail, detail or "was not refused")

    # --- the reason this file exists --------------------------------------- #
    found = sorted(i["id"] for i in app.call("/api/instruments")["instruments"])
    missing = [i for i in EXPECTED_INSTRUMENTS if i not in found]
    check(
        f"discovers all {len(EXPECTED_INSTRUMENTS)} instrument loaders",
        not missing,
        f"missing {missing}" if missing else f"found {len(found)}",
    )

    # --- real loaders, not just the registry -------------------------------- #
    # `status == "done"` is NOT the check. An ingest whose loader is missing
    # finishes cleanly and reports its failure in the result payload instead —
    # which is how the first container build passed this while importing zero
    # Arbin files (cellpy shells out to `mdb-export` on posix, and it was not
    # installed). Assert on what came back.
    # "Arbin .res" is one check but two mechanisms: ODBC on Windows, a shell-out
    # to `mdb-export` on posix. Naming either one here would be wrong somewhere.
    for kind, label in (("arbin", "Arbin .res (binary)"),
                        ("maccor", "Maccor (text)")):
        st = app.job(app.call("/api/ingest/example", {"kind": kind}))
        result = st.get("result") or {}
        added, errors = result.get("added") or [], result.get("errors") or []
        joined = "; ".join(errors)
        name = f"imports a real raw file — {label}"

        if kind == "arbin" and any(m in joined.lower() for m in _MISSING_ODBC):
            skip(name, "no Access ODBC driver on this machine — see "
                       "docs/windows-installer.md")
            continue

        check(
            name,
            st.get("status") == "done" and bool(added) and not errors,
            joined[:160] or f"added {len(added)}",
        )

    # --- cells, collection, figure ------------------------------------------ #
    st = app.job(app.call("/api/load/example", {"kinds": ["cellpy"]}))
    check("loads a bundled .cellpy cell", st.get("status") == "done",
          st.get("message", "")[:120])

    n_cells = len(app.call("/api/state")["cells"])
    check("has cells in the library", n_cells > 0, f"{n_cells} cells")

    fig = app.call("/api/plots/summary",
                   {"plot_type": "capacity_ce", "basis": "gravimetric"})
    traces = len(fig.get("data", []))
    check("renders a summary figure", traces > 0, f"{traces} traces")

    cycles = app.call("/api/plots/cycles", {"cycles": [1, 2, 3], "curve_kind": "dqdv"})
    check("renders dQ/dV across cells", len(cycles.get("data", [])) > 0)

    data = app.call("/api/export/summary?fmt=csv",
                    {"plot_type": "capacity_ce", "basis": "gravimetric"})
    check("exports data as CSV", isinstance(data, bytes) and b"," in data[:200])

    # Static figure export has one legitimate failure: kaleido 1.x renders by
    # driving a separate Chrome, and there may not be one. So this asserts the
    # *contract* — real PNG bytes, or a clean 503 — rather than success, which
    # would fail on a perfectly good install that simply lacks a browser.
    # Anything else (a 500, or a 200 that is not a PNG) is a genuine bug.
    spec = {"plot_type": "capacity_ce", "basis": "gravimetric"}
    try:
        png = app.call("/api/export/summary?fmt=png", spec)
        ok = isinstance(png, bytes) and png[:8] == b"\x89PNG\r\n\x1a\n"
        detail = f"{len(png)} bytes" if ok else f"200 but not a PNG: {str(png)[:80]}"
    except urllib.error.HTTPError as exc:
        body = (exc.read() or b"").decode("utf-8", "replace")
        ok = exc.code == 503
        detail = (
            f"unavailable (503) — {body[:90]}" if ok
            else f"HTTP {exc.code}: {body[:90]}"
        )
    check("figure export works, or declines cleanly", ok, detail)

    # --- persistence: the volume has to be real ----------------------------- #
    # Saving writes .cellpy files under CSG_DATA_DIR, so this is also the check
    # that a container's mount is writable by the user the image runs as.
    name = "smoke-test-project"
    st = app.job(app.call("/api/projects/save", {"name": name}))
    saved = check("saves a project", st.get("status") == "done",
                  st.get("message", "")[:160])

    if saved:
        listed = [p["slug"] for p in app.call("/api/projects").get("projects", [])]
        check("lists the saved project", name in listed, ", ".join(listed) or "none")

        app.call("/api/cells/clear", {}, method="POST")
        check("clears the library", len(app.call("/api/state")["cells"]) == 0)

        st = app.job(app.call("/api/projects/open", {"target": name}))
        reopened = len(app.call("/api/state")["cells"])
        check("reopens it with its cells", st.get("status") == "done" and reopened > 0,
              f"{reopened} cells")

        app.call(f"/api/projects/{name}", method="DELETE")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exe", nargs="?", type=Path,
                        help="built executable to launch")
    parser.add_argument("--url", help="base URL of an app that is already running")
    parser.add_argument("--token", help="its CSG token")
    args = parser.parse_args(argv)

    if args.url:
        if not args.token:
            parser.error("--url needs --token")
        print(f"smoke-testing {args.url}")
        app: Client = Client(args.url, args.token)
    elif args.exe:
        if not args.exe.is_file():
            print(f"no such executable: {args.exe}")
            return 2
        print(f"smoke-testing {args.exe}")
        launched = LaunchedApp(args.exe)
        t0 = time.perf_counter()
        launched.wait_for_url()
        print(f"  (served in {time.perf_counter() - t0:.1f}s at {launched.base})\n")
        app = launched
    else:
        parser.error("give an executable path or --url/--token")

    try:
        run_checks(app)
    finally:
        app.close()

    tally = f"\n{len(passes)} passed, {len(failures)} failed"
    if skips:
        tally += f", {len(skips)} skipped"
    print(tally)
    if failures:
        print("failed: " + ", ".join(failures))
    if skips:
        print("skipped: " + ", ".join(skips))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
