# 5. Configuration

*You want to know where cellpy is reading from — and change it without breaking
the machine it is running on.*

cellpy 2.1.2 replaced `parameters.prms` with a layered
[pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
stack. It is the single biggest app-facing improvement in the release, because it
makes a question most libraries leave unanswerable — *why does this setting have
this value?* — a normal API call.

## The layers

Later wins:

| # | Layer | Where |
|---|---|---|
| 1 | defaults | in the code |
| 2 | user config | `cellpy.toml` in the OS config directory (written by `cellpy setup`) |
| 3 | project config | a `cellpy.toml` found for the project |
| 4 | environment | `CELLPY_<SECTION>__<FIELD>` |
| 5 | runtime | `config.reload(overrides)` and `config.override(...)` |

```python
from cellpy import config

settings = config.get_config()
print(list(settings.model_fields))
```

```text
['paths', 'file_names', 'reader', 'db', 'db_cols', 'batch', 'instruments',
 'defaults', 'units', 'secrets']
```

Note `secrets` sitting there in plain sight. More on that below.

## Which file actually won, and where each value came from

Two calls, and together they answer nearly every "but it works on my machine":

```python
from cellpy import config

active = config.active_config_file()
print(type(active).__name__, "·", [f for f in dir(active) if not f.startswith("_")])
print("kind:", active.kind, "· shadowing a legacy file:", active.shadowed_legacy is not None)
```

`active_config_file()` reports the file the **loader** actually used, including
the case where a legacy `.conf` is being shadowed by a newer `cellpy.toml`. That
one detail removes a whole category of confusion — a user editing the file they
remember, watching nothing change
([cellpy#851](https://github.com/jepegit/cellpy/issues/851)).

Per-key provenance is `sources()`:

```python
from cellpy import config

sources = config.sources()
print(len(sources), "keys tracked")
print("layers seen:", sorted(set(sources.values())))
print("paths.outdatadir came from:", sources["paths.outdatadir"])
```

```text
150 keys tracked
layers seen: ['default', 'env', 'user_file']
paths.outdatadir came from: user_file
```

(Your layers will differ — that is the point.) If you are building anything with
a settings panel, show this. "Where is cellpy reading from?" is the first
question anyone asks when a path is wrong, and here it is answerable in one line
instead of by reasoning about precedence.

## Changing settings

**Process-wide, permanent for this run:**

```python
from cellpy import config

config.reload({"reader": {"cycle_mode": "anode"}})
print(config.get_config().reader.cycle_mode)
```

```text
anode
```

**Scoped, and isolated per thread:**

```python
from cellpy import config

with config.override(reader={"cycle_mode": "cathode"}):
    print("inside: ", config.get_config().reader.cycle_mode)
print("outside:", config.get_config().reader.cycle_mode)
```

```text
inside:  cathode
outside: anode
```

`override()` is contextvar-based since 2.1.2a3, so it isolates per thread *and*
per asyncio task, and nested blocks stack LIFO. It used to be process-global,
which meant two workers could silently swap each other's units mid-job
([cellpy#850](https://github.com/jepegit/cellpy/issues/850)). If you are running
cellpy in a thread pool, [guide 6](06-state-and-threading.md) is the one to read.

**By environment**, which is how you configure a container:

```text
CELLPY_PATHS__OUTDATADIR=/data
CELLPY_READER__CYCLE_MODE=anode
```

Double underscore between section and field. This is the layer to reach for in
deployment: no file to mount, no file to write.

## Never write the user's config file

`cellpy.toml` in the OS config directory is shared with that person's notebooks
and CLI. An app that writes there is reaching into a space it does not own, and
the effect shows up somewhere the user will not connect to your app.

Read it, show it, override it for your process — but let `cellpy setup` be the
only thing that writes it.

If you need settings to travel with a *project*, write a project-scoped
`cellpy.toml` and point the loader at it:

```python
from cellpy import config

options = config.LoadOptions(project_config_file=None)  # a real path in your app
print([f for f in config.LoadOptions.__dataclass_fields__])
```

```text
['user_config_file', 'project_config_file', 'env_file', 'cwd', 'skip_files',
 'skip_env', 'legacy_yaml_file']
```

And **write an allow-list of sections, not the whole config.** We pin only
`reader`, `units` and `defaults`. The two exclusions are the interesting part:

- **`paths` would bake this machine's layout into a portable project** — the
  project then only works where it was created, which is the opposite of the
  point.
- **omitting `instruments` and `db` means the file structurally cannot contain a
  credential.** Not "we scrub it": there is no field for it to be in.

That second one is worth doing even though cellpy's own dump scrubbing was fixed
([cellpy#849](https://github.com/jepegit/cellpy/issues/849), 2.1.2a3). A
structural guarantee does not depend on someone else's regex staying correct, and
it survives a config schema growing a new secret-ish field.

## Credentials

Same reasoning one level up. `secrets` is a section, and legacy instrument keys
like `SQL_PWD` can sit in the in-memory config even on a version that no longer
writes them to file. If your app displays configuration, mask them:

```python
CREDENTIALISH = ("pwd", "password", "secret", "token", "key", "uid", "user")


def masked(section: str, field: str, value):
    if section == "secrets" or any(k in field.lower() for k in CREDENTIALISH):
        return "••••" if value else None
    return value


print(masked("instruments", "SQL_PWD", "hunter2"), "·", masked("paths", "outdatadir", "/data"))
```

```text
•••• · /data
```

Masking in a UI is right regardless of what the library writes to disk — the
threat is a screenshot in a support ticket, not only a file on disk.

## The relative-path trap

One setting, three ways to lose, and it cost real time in both of this project's
deployment routes.

**(a) Some defaults are relative.** With no user config, `paths.examplesdir` is
`cellpy_data/examples` and `paths.filelogdir` is `cellpy_data/logs` — resolved
against the **process working directory**, not `$HOME`. For an installed
application the cwd is wherever the shortcut happened to start it, so two
correct-looking processes disagree about where the data lives.

**(b) `examplesdir` is resolved at import time.** `example_data.DATA_PATH` is
computed when the module is imported, and if the configured directory does not
*exist*, it falls back to `site-packages/cellpy/utils/data`. Setting
`CELLPY_PATHS__EXAMPLESDIR` is therefore not enough on its own — the directory
has to exist first, or the override is discarded with a `warnings.warn`.

**(c) The fallback target is the wrong place to write.** In a container it is
root-owned while the app runs unprivileged, so the zero-setup demo fails on a
permission error at the friendliest button in the product. In a frozen Windows
app it is inside the install directory: a first run wrote ~9 MB there, and the
uninstaller left it behind, because the installer had never put it there.

The fix is to anchor the writable paths yourself, **before anything imports
`example_data`**:

```python
from pathlib import Path

WRITABLE_PATHS = (
    ("examplesdir", "CELLPY_PATHS__EXAMPLESDIR"),
    ("filelogdir", "CELLPY_PATHS__FILELOGDIR"),
)


def anchor(paths_section, home: Path) -> dict[str, Path]:
    """Make relative path settings absolute under `home`, and create them."""
    resolved = {}
    for field, _env in WRITABLE_PATHS:
        value = str(getattr(paths_section, field, "") or "")
        if not value or "://" in value:      # rawdatadir can be scp://…; leave it
            continue
        path = Path(value)
        resolved[field] = path if path.is_absolute() else (home / path)
    return resolved


from cellpy import config

for field, path in anchor(config.get_config().paths, Path.home()).items():
    print(field, "->", "absolute" if path.is_absolute() else "RELATIVE")
```

```text
examplesdir -> absolute
filelogdir -> absolute
```

In the real thing you then set the env var, call `config.reload()`, and `mkdir`
each one. Two details learned by getting them wrong:

- **Fix all of them, not the one that hurt.** Anchoring `examplesdir` alone left
  `cellpy_debug.log`, `cellpy_errors.log` and `cellpy_info.log` in the install
  directory — same defect, different field.
- **Control the cwd before you check.** Our first fix created the directory from
  the same relative path and merely moved the mess into the source repo. The
  install folder only *looked* clean because that is where the test was running.

*(Raised upstream as [cellpy#938](https://github.com/jepegit/cellpy/issues/938):
an absolute default, and creating the directory rather than falling back. A
config value that is accepted and then quietly ignored is very hard to debug from
outside the library.)*

## Where to go next

[Guide 6](06-state-and-threading.md) — the config is process-global, and so are
several other things. What that means once you have more than one thread.

---

*Sources: `cellpy.config.get_config` / `sources` / `override` / `reload` /
`active_config_file` / `LoadOptions`. Traps from
[CELLPY_PAINPOINTS.md](../../CELLPY_PAINPOINTS.md) §22–§24 and §33.*
