#!/usr/bin/env python3
"""
Recalculate every formula in an .xlsx with LibreOffice (headless) and report formula errors.

Mechanism: `soffice --headless --convert-to xlsx` into a temporary directory (LibreOffice recalculates all formulas
on load and writes their cached values; formulas, charts, merged cells, print areas and formatting survive the
round-trip), then the converted file is verified (at least one formula must carry a value; every #REF!/#DIV/0!… is
listed) and copied over the original. No macros are involved.

    python recalc.py workbook.xlsx [timeout_seconds]

Prints JSON: {"status": "success", "total_errors": N, "error_summary": {...}, "total_formulas": M}
or {"error": "..."}.  Requires `soffice` (LibreOffice) on PATH. Rewrites the file in place with cached values,
so openpyxl `data_only=True` then returns computed numbers.

Portable and dependency-free on purpose: selftest.py and the skill's build steps call this file. If LibreOffice
is not available here, pass another recalculator to selftest.py with --recalc <path> (e.g. the xlsx skill's).

Sandboxes that block AF_UNIX sockets make soffice hang until the timeout: this script detects that at start-up and,
when gcc is available, compiles a small LD_PRELOAD shim (socketpair fallback) so LibreOffice can start. Default
timeout is 180 s: the first start creates a profile, which on a cold container can take a minute.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ERRORS = ["#VALUE!", "#DIV/0!", "#REF!", "#NAME?", "#NULL!", "#NUM!", "#N/A"]
_SHIM_SOURCE = r"""
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/socket.h>
#include <unistd.h>

static int (*real_socket)(int, int, int);
static int (*real_socketpair)(int, int, int, int[2]);
static int (*real_listen)(int, int);
static int (*real_accept)(int, struct sockaddr *, socklen_t *);
static int (*real_close)(int);
static int (*real_read)(int, void *, size_t);

/* Per-FD bookkeeping (FDs >= 1024 are passed through unshimmed). */
static int is_shimmed[1024];
static int peer_of[1024];
static int wake_r[1024];            /* accept() blocks reading this */
static int wake_w[1024];            /* close()  writes to this      */
static int listener_fd = -1;        /* FD that received listen()    */

__attribute__((constructor))
static void init(void) {
    real_socket     = dlsym(RTLD_NEXT, "socket");
    real_socketpair = dlsym(RTLD_NEXT, "socketpair");
    real_listen     = dlsym(RTLD_NEXT, "listen");
    real_accept     = dlsym(RTLD_NEXT, "accept");
    real_close      = dlsym(RTLD_NEXT, "close");
    real_read       = dlsym(RTLD_NEXT, "read");
    for (int i = 0; i < 1024; i++) {
        peer_of[i] = -1;
        wake_r[i]  = -1;
        wake_w[i]  = -1;
    }
}

/* ---- socket ---------------------------------------------------------- */
int socket(int domain, int type, int protocol) {
    if (domain == AF_UNIX) {
        int fd = real_socket(domain, type, protocol);
        if (fd >= 0) return fd;
        /* socket(AF_UNIX) blocked – fall back to socketpair(). */
        int sv[2];
        if (real_socketpair(domain, type, protocol, sv) == 0) {
            if (sv[0] >= 0 && sv[0] < 1024) {
                is_shimmed[sv[0]] = 1;
                peer_of[sv[0]]    = sv[1];
                int wp[2];
                if (pipe(wp) == 0) {
                    wake_r[sv[0]] = wp[0];
                    wake_w[sv[0]] = wp[1];
                }
            }
            return sv[0];
        }
        errno = EPERM;
        return -1;
    }
    return real_socket(domain, type, protocol);
}

/* ---- listen ---------------------------------------------------------- */
int listen(int sockfd, int backlog) {
    if (sockfd >= 0 && sockfd < 1024 && is_shimmed[sockfd]) {
        listener_fd = sockfd;
        return 0;
    }
    return real_listen(sockfd, backlog);
}

/* ---- accept ---------------------------------------------------------- */
int accept(int sockfd, struct sockaddr *addr, socklen_t *addrlen) {
    if (sockfd >= 0 && sockfd < 1024 && is_shimmed[sockfd]) {
        /* Block until close() writes to the wake pipe. */
        if (wake_r[sockfd] >= 0) {
            char buf;
            real_read(wake_r[sockfd], &buf, 1);
        }
        errno = ECONNABORTED;
        return -1;
    }
    return real_accept(sockfd, addr, addrlen);
}

/* ---- close ----------------------------------------------------------- */
int close(int fd) {
    if (fd >= 0 && fd < 1024 && is_shimmed[fd]) {
        int was_listener = (fd == listener_fd);
        is_shimmed[fd] = 0;

        if (wake_w[fd] >= 0) {              /* unblock accept() */
            char c = 0;
            write(wake_w[fd], &c, 1);
            real_close(wake_w[fd]);
            wake_w[fd] = -1;
        }
        if (wake_r[fd] >= 0) { real_close(wake_r[fd]); wake_r[fd]  = -1; }
        if (peer_of[fd] >= 0) { real_close(peer_of[fd]); peer_of[fd] = -1; }

        if (was_listener)
            _exit(0);                        /* conversion done – exit */
    }
    return real_close(fd);
}
"""


def soffice_env() -> dict:
    """Environment for soffice: headless VCL plugin, plus an LD_PRELOAD shim when AF_UNIX sockets are blocked."""
    env = dict(os.environ, SAL_USE_VCLPLUGIN="svp")
    import socket
    try:
        socket.socket(socket.AF_UNIX, socket.SOCK_STREAM).close()
        return env
    except OSError:
        pass
    so = Path(tempfile.gettempdir()) / "lo_socket_shim.so"
    if not so.exists():
        if not shutil.which("gcc"):
            return env  # cannot build the shim; soffice may hang — the timeout will report it
        c = Path(tempfile.gettempdir()) / "lo_socket_shim.c"; c.write_text(_SHIM_SOURCE)
        subprocess.run(["gcc", "-shared", "-fPIC", "-o", str(so), str(c), "-ldl"], capture_output=True)
    if so.exists():
        env["LD_PRELOAD"] = str(so)
    return env


_FORMULA_CELL = re.compile(r"(<c\b[^>]*>)(\s*<f\b[^>]*(?:/>|>.*?</f>))\s*<v>.*?</v>", re.S)


def strip_cached_values(src: str, dst: str) -> None:
    """Copy the workbook, deleting every cached <v> that sits next to a formula <f>. Nothing else in the package is touched
    (charts, styles, print areas survive), so the recalculation cannot silently keep a stale result."""
    import zipfile
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.startswith("xl/worksheets/sheet") and item.filename.endswith(".xml"):
                data = _FORMULA_CELL.sub(lambda m: m.group(1) + m.group(2), data.decode("utf-8")).encode("utf-8")
            zout.writestr(item, data)


def recalc(path: str, timeout: int = 180) -> dict:
    """Round-trip the workbook through `soffice --convert-to xlsx` (LibreOffice recalculates every formula on load and
    writes cached values), verify the result, then replace the original. No macros, no profile tricks."""
    p = Path(path).absolute()
    if not p.exists():
        return {"error": f"{path} does not exist"}
    if not shutil.which("soffice"):
        return {"error": "soffice not found on PATH; LibreOffice is required to recalculate"}
    env = soffice_env()
    with tempfile.TemporaryDirectory(prefix="recalc-") as d:
        outdir = Path(d) / "out"; outdir.mkdir()
        src = Path(d) / p.name
        strip_cached_values(str(p), str(src))   # LibreOffice keeps cached values it finds; remove them so every formula is recomputed
        cmd = ["soffice", "--headless", "--norestore", f"-env:UserInstallation={(Path(d) / 'profile').as_uri()}",
               "--convert-to", "xlsx", "--outdir", str(outdir), str(src)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        except subprocess.TimeoutExpired:
            return {"error": f"LibreOffice timed out after {timeout}s; formulas were NOT recalculated"}
        out = outdir / p.name
        if r.returncode != 0 or not out.exists():
            return {"error": f"LibreOffice conversion failed: {(r.stderr or r.stdout or '').strip()[-300:] or r.returncode}"}
        from openpyxl import load_workbook
        wb_f = load_workbook(str(out), data_only=False); wb_v = load_workbook(str(out), data_only=True)
        summary = {e: [] for e in ERRORS}; total = 0; n_formulas = 0; n_cached = 0
        for name in wb_f.sheetnames:
            wsf, wsv = wb_f[name], wb_v[name]
            for row in wsf.iter_rows():
                for c in row:
                    if isinstance(c.value, str) and c.value.startswith("="):
                        n_formulas += 1
                        v = wsv[c.coordinate].value
                        if v is not None: n_cached += 1
                        if isinstance(v, str):
                            for e in ERRORS:
                                if e in v: summary[e].append(f"{name}!{c.coordinate}"); total += 1
        if n_formulas and n_cached == 0:
            return {"error": "LibreOffice converted the file but no formula received a cached value; nothing was recalculated"}
        shutil.copyfile(str(out), str(p))
    return {"status": "success", "total_errors": total, "error_summary": {k: v[:20] for k, v in summary.items() if v},
            "total_formulas": n_formulas, "formulas_with_values": n_cached}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    out = recalc(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 180)
    print(json.dumps(out, indent=2))
    sys.exit(0 if out.get("status") == "success" else 1)
