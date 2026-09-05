# Deploying cellpy simple GUI as a server

The app was built as a desktop tool and grew a server mode. That history is not
a footnote — it decides what a safe deployment looks like. Read the first
section before the ones with commands in them.

---

## What this app is, and is not

**One instance serves one person.** The cell library, the job manager and
cellpy's own configuration session all live in process-global state. Two people
on one instance would share a library, overwrite each other's grouping and
selection, and race each other's per-project cellpy config. There is no user
model to fix this with, because there was never meant to be one: the deployment
target is a container per person, or one spawned on demand.

**The token is not authentication.** Every start mints a token, printed in the
log and planted as a cookie by the index page. It exists to stop *other
processes on the same machine* from driving the local API. It is a single shared
secret with no identity behind it, no expiry, no revocation, and no rate
limiting. Anyone who can reach the port and knows the token **is** the user.

So, before this leaves a trusted network:

> Put it behind a reverse proxy that terminates TLS and performs real
> authentication, or keep it on a network where you already trust everyone who
> can reach the port.

That is the whole security model. It is small on purpose, but shipping it
without saying so would be the mistake.

**What an authenticated user can do.** In served mode, reads and writes are
confined to `CSG_DATA_DIR` (see *Local vs served* in the README). That bounds
the damage to the instance's own data — it is not a sandbox against someone you
have handed a shell-equivalent to. Uploading arbitrary instrument files means
handing them to cellpy's parsers.

**SSH remotes are desktop-only.** `sftp://` / `ssh://` / `scp://` URIs are
refused in served mode for the same reason host paths are: opening an SSH
session to an arbitrary host is outside the data-directory sandbox. Paste remote
URIs in the desktop app instead (see *Remote files* in the README).

---

## Container

### Run the published image

```bash
docker run --rm -p 127.0.0.1:8577:8577 -v cellpy-data:/data --init \
  -e CSG_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(16))") \
  ghcr.io/cellpy/cellpy-simple-gui:latest
```

Then open `http://127.0.0.1:8577/?token=<the token you set>`. Omit `CSG_TOKEN`
and a fresh one is generated per start and printed in the log:

```bash
docker logs <container> | grep "running at"
```

### Or with compose

`docker-compose.yml` in the repo root is a working starting point rather than a
production manifest. It publishes on loopback, uses a named volume, and requires
`CSG_TOKEN` to be set:

```bash
echo "CSG_TOKEN=$(python -c 'import secrets; print(secrets.token_urlsafe(16))')" > .env
docker compose up --build
```

### Build it yourself

```bash
docker build -t cellpy-simple-gui .
```

Build arguments:

| arg | default | effect |
|---|---|---|
| `WITH_DEMO_DATA` | `1` | Bake in ~15 MB of cellpy demo cells, so the demo works offline. |
| `PYTHON_VERSION` | `3.13` | Base image Python. |
| `UV_VERSION` | pinned | The uv used to build the venv. |

---

## Things that bite

### The volume must be writable by uid 10001

The image runs as a non-root user. A **named volume** inherits the right
ownership automatically and is the easy path. A **bind mount** keeps its host
ownership, so this fails:

```bash
docker run -v /srv/cellpy:/data ...     # /srv/cellpy owned by root
```

Fix it on the host, once:

```bash
sudo chown -R 10001:10001 /srv/cellpy
```

The entrypoint checks this at start and refuses with that message, rather than
letting it surface as a permission error halfway through a save.

### cellpy's own directories are separate from the app's

`CSG_DATA_DIR` decides where *projects* go. cellpy has its own `[paths]`, and
they default under `$HOME` — which inside a container is image-local and
disappears with it. The image sets the two that matter:

- `CELLPY_PATHS__OUTDATADIR=/data` — so anything cellpy writes lands on the volume.
- `CELLPY_PATHS__EXAMPLESDIR=/home/app/cellpy_data/examples` — where the baked-in
  demo cells live.

The second one is not cosmetic. cellpy resolves `examplesdir` **at import time**
and, if the directory does not exist, falls back to one inside `site-packages` —
root-owned in this image, so a non-root process cannot write there and the
zero-setup demo fails. Point it somewhere writable *and make sure it exists*.

Override any other field with `CELLPY_PATHS__<FIELD>`; the app's cellpy-version
badge shows every resolved setting and which layer won, which is the fastest way
to confirm a deployment reads what you think it does.

### Server-side figure export is not in the image

**Export ▾ → Figure** (PNG/SVG/PDF) returns a `503`. The reason is not image
size. The pinned kaleido resolves to 1.x, which **does not bundle a renderer** —
it drives a separate Chrome through `choreographer`, so installing the wheel
alone changes nothing at runtime except the error you get.

Measured rather than assumed, in this base image: `plotly_get_chrome` exits `0`,
and `to_image` then dies with `BrowserFailedError` because slim does not carry
the shared libraries Chrome needs. Shipping a build flag that produced a broken
image would have been worse than not offering one, so there isn't one, and
[#135](https://github.com/cellpy/cellpy-simple-gui/issues/135) is closed
**wontfix**: Chrome plus its shared libraries is a large addition to an image
for a feature the browser already covers.

Everything else is unaffected: CSV, Excel, Parquet and JSON export all work, and
the Plotly toolbar's camera button still saves a PNG client-side, which is what
most people reach for anyway.

### Two loaders need system libraries, and fail quietly without them

Worth knowing if you build your own base. The image installs `mdbtools` and
`unixodbc` because two instrument loaders are Python wheels over system
libraries, and both fail in ways that are easy to miss:

- **`mdbtools`** — on posix, cellpy reads Arbin `.res` by shelling out to
  `mdb-export`. Without it the import job still reports **done**; only its result
  payload says nothing was added.
- **`unixodbc`** — provides `libodbc.so.2`, which `pyodbc` links against.
  Without it `arbin_sql` and `arbin_sql_7` raise `ImportError` during discovery
  and simply never appear in the instrument list.

Actually *connecting* to an Arbin SQL Server additionally needs a vendor ODBC
driver, which is not shipped here.

### The port is fixed once, at startup

If `CSG_PORT` is occupied the app picks a *different* free port, which inside a
container silently breaks the published mapping. In a fresh container nothing is
listening, so this does not arise in practice — but do not run two servers in
one container and expect the mapping to hold.

---

## Behind a reverse proxy

Two things need attention.

**Force the sandbox.** The app infers its mode from the bind address, and a
proxy connects from loopback — so an instance bound to `127.0.0.1` and published
by a proxy still looks local from inside, and would accept host paths. Set:

```bash
CSG_ALLOW_HOST_PATHS=0
```

The container image binds `0.0.0.0` and is already in served mode; this matters
when you run the app directly rather than in the image. Confirm either way:

```bash
curl -H "X-CSG-Token: $CSG_TOKEN" localhost:8577/api/system/capabilities
# -> "host_paths_allowed": false, "sandbox_root": "/data"
```

**Do not buffer the event stream.** Background loading reports progress over
SSE. nginx buffers proxied responses by default, which turns live progress into
a spinner that jumps to 100% at the end:

```nginx
location / {
    proxy_pass         http://127.0.0.1:8577;
    proxy_http_version 1.1;
    proxy_set_header   Connection "";
    proxy_buffering    off;          # SSE progress
    proxy_read_timeout 1h;           # long loads must not be cut off
}
```

`/healthz` is the only route outside the token guard — use it for liveness
probes, and do not expose it more widely than you need to.

---

## Environment reference

| variable | default | meaning |
|---|---|---|
| `CSG_HOST` | `127.0.0.1` (`0.0.0.0` in the image) | Bind address. Also selects local vs served mode. |
| `CSG_PORT` | `8577` | Port. |
| `CSG_TOKEN` | random per start | The shared secret in the URL. Not authentication. |
| `CSG_DATA_DIR` | `~/.cellpy_simple_gui` (`/data` in the image) | Projects and app state. |
| `CSG_ALLOW_HOST_PATHS` | inferred from `CSG_HOST` | Force the path sandbox on (`0`) or off (`1`). |
| `CSG_DEV_MODE` | `0` | Developer mode: every plot family, raised batch limits. Do not enable on a served instance. |

The cap on how many files one glob may pull in is not separately configurable —
it is `10`, or `500` in developer mode.

---

## Getting files in

Two ways, and a served instance needs the first.

**Upload from the browser.** *Add cellpy files → Upload from this computer*.
Files are written to `CSG_DATA_DIR/uploads/` and then loaded through the same
path as anything else, so the sandbox stays the only thing deciding what is
readable. Up to **512 MB** per file by default:

```bash
CSG_MAX_UPLOAD_MB=2048
```

The cap exists so one request cannot fill the disk. A file over it is refused
with a message, and the others in the same upload still land — five files with
one oversized leaves you four and a warning, not nothing.

**Mount data at the volume.** Anything already inside `CSG_DATA_DIR` can be
loaded by path, which is the better route for a directory of existing cells.
On a served instance the path field is demoted below upload, because it refers
to a filesystem the browser cannot see.

### Uploads are never deleted automatically

They accumulate in `CSG_DATA_DIR/uploads/` until you clear them. That is
deliberate: between uploading a file and saving a project from it, the upload is
the only copy, and quietly deleting someone's data to reclaim disk is a worse
failure than a folder that grows.

```bash
curl -H "X-CSG-Token: $CSG_TOKEN" localhost:8577/api/uploads          # how much
curl -X DELETE -H "X-CSG-Token: $CSG_TOKEN" localhost:8577/api/uploads  # clear
```

Saved projects keep their own copies of the cells, so clearing uploads does not
affect them.
