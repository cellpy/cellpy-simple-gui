/* cellpy simple gui — front-end logic (Alpine component) */

const TOKEN = document.querySelector('meta[name="csg-token"]').content;

async function api(path, { method = "GET", body = null } = {}) {
  const opts = {
    method,
    headers: { "X-CSG-Token": TOKEN },
    credentials: "same-origin",
  };
  if (body instanceof FormData) {
    // Multipart uploads (#133): the browser has to set Content-Type itself,
    // because only it knows the boundary it generated. Setting the header here
    // produces a request the server cannot parse.
    opts.body = body;
  } else if (body !== null) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return res;
}

const PLOTLY_CONFIG = {
  responsive: true,
  displaylogo: false,
  toImageButtonOptions: { format: "png", scale: 2 },
  modeBarButtonsToRemove: ["lasso2d", "select2d"],
};

// Breathing room under a chart grown to fill the window (#93), matching the
// page's bottom padding so the card does not sit flush against the edge.
const CHART_BOTTOM_GUTTER = 16;

// Recent sources (#136): typed paths / globs, journals and remote folders the
// user has loaded from before, offered as <datalist> suggestions.
const RECENT_KEY = "csg.recent";
const RECENT_CAP = 8;
const RECENT_KINDS = ["cellpy", "raw", "journal", "remoteDir"];

function loadRecent() {
  const out = {};
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(RECENT_KEY) || "{}") || {}; } catch (_) {}
  for (const k of RECENT_KINDS) {
    out[k] = Array.isArray(saved[k]) ? saved[k].filter((v) => typeof v === "string").slice(0, RECENT_CAP) : [];
  }
  return out;
}

function app() {
  return {
    theme: localStorage.getItem("csg-theme") || "dark",
    figureThemePref: localStorage.getItem("csg-figure-theme") || "match",
    colorScheme: localStorage.getItem("csg-color-scheme") || "cellpy",
    cells: [],
    examples: [],
    filesMax: 10,
    journalPath: "",
    // Add cells modal (#136): every file source feeds a staged list that the
    // user reviews before the one primary button runs the unchanged job.
    addCells: { open: false, tab: "cellpy" },
    dragOver: "",
    typed: { cellpy: "", raw: "" },
    previewBusy: false,
    staged: { cellpy: [], raw: [] }, // rows: {path, name, dir, ext, source, status, detail}
    stageNote: { cellpy: "", raw: "" },
    lastResult: null, // {kind, added, errors, notes, at} from the last load / ingest job
    resultOpen: false, // details disclosure on the result card
    recent: loadRecent(), // typed patterns / journals / remote folders, most recent first
    canPick: false,
    devMode: false,
    maxFilesCeiling: 10, // server-enforced ceiling; higher in dev mode (#97)
    hostPathsAllowed: true, // served instances say false (#120) -> upload (#133)
    maxUploadMb: 512,
    uploading: false,
    uploadStatus: "",
    tab: "summary",
    project: null,
    projects: [],
    openTarget: "",
    saveName: "",
    dirty: false,
    dataCollapsed: false, // folds the Data panel once cells are loaded
    instruments: [],
    rawExamples: [],
    ingest: {
      instrument: "", model: "", mass: "", area: "",
      nominal_capacity: "", nom_cap_specifics: "", cycle_mode: "", maxFiles: 10,
    },
    // Remote folder find (#162): one block per tab, so extensions can follow
    // the instrument for raw files and stay .cellpy/.h5 for cellpy files.
    remoteFind: {
      load: { open: false, dir: "", filter: "" },
      ingest: { open: false, dir: "", filter: "" },
    },
    _remoteFindTarget: null, // which form the running find job fills in
    job: { active: false, id: "", progress: 0, message: "", error: "" },
    _jobEs: null,
    plotBusy: { summary: false, cycles: false, cell: false },
    // In-flight plot requests per chart (#184): the spinner stays up until the
    // last one settles, and only the newest request may draw — a response
    // overtaken by a later request is dropped, so a burst of edits no longer
    // replays every intermediate figure.
    _plotInflight: { summary: 0, cycles: 0, cell: 0 },
    _plotSeq: { summary: 0, cycles: 0, cell: 0 },
    // The Manage cells modal defers redraws until it closes (#184).
    _replotOnClose: false,
    summary: {
      plot_type: "capacity_ce", basis: "gravimetric",
      group_average: false, spread: false, max_cycle: "",
      group_legend_muting: true,
      share_y: false,
      yRanges: {}, // column id → {min, max} strings; either end optional
    },
    plotTypes: [],
    cell: {
      cell_id: "", from: 1, to: 10, maxCurves: 8, min: 1, max: 1,
      plotKind: "curves", mode: "gravimetric", method: "forth-and-forth",
      voltageResolution: 0.005, direction: "charge",
      rawPlotType: "voltage-current", maxPoints: 4000,
      xRange: { min: "", max: "" },
      yRange: { min: "", max: "" },
      // Compare mode (#169): picks = [{key, cell_id, cyclesText, min, max}].
      compare: false, compareLayout: "overlay", picks: [],
      // Server-side notes about the last figure, e.g. cycles a cell lacks (#175).
      notes: [],
    },
    cycles: {
      layout: "per_cycle", from: 1, to: 10, maxCurves: 8, min: 1, max: 1,
      mode: "gravimetric", method: "forth-and-forth",
      group_legend_muting: true,
      // dQ/dV & dV/dQ over the same selection (#95)
      curveKind: "voltage", direction: "charge", voltageResolution: 0.005,
      xRange: { min: "", max: "" },
      yRange: { min: "", max: "" },
    },
    exportFormats: ["csv", "xlsx", "parquet", "json"],
    figureFormats: ["png", "svg", "pdf"],
    cellFileFormats: ["cellpy", "csv", "xlsx"],
    exportOpen: false,
    exportCellOpen: false,
    exportCyclesOpen: false,
    exportCellsOpen: false,
    notices: [],
    cellsManagerOpen: false,
    cellsManagerFilter: "",
    cellsManagerSort: "default",
    cellsManagerGroup: 1,
    cellpyConfigOpen: false,
    cellpyConfigLoading: false,
    cellpyConfigError: "",
    cellpyConfig: null,
    projectCellpyConfig: "", // set when the open project carries its own cellpy.toml
    cellpyConfigPinning: false,
    diagOpen: false,
    diagTab: "logs",
    diagLevel: "",
    diagAuto: false,
    diagLogs: [],
    diagJobs: [],
    diagError: "",
    _diagTimer: null,

    // ---- lifecycle ----
    async init() {
      try {
        this.examples = await (await api("/api/examples")).json();
      } catch (_) {}
      await this.refreshInstruments();
      await this.refreshPlotTypes();
      await this.refreshProjects();
      await this.probeCapabilities();
      await this.refreshState();
      this.$watch("theme", () => {
        this.relayoutCharts();
        if (this.figureThemePref === "match") this.replotCurrent();
      });
      window.addEventListener("resize", () => this.relayoutCharts());
    },

    resolvedFigureTheme() {
      if (this.figureThemePref === "match") {
        return this.theme === "dark" ? "dark" : "light";
      }
      return this.figureThemePref === "dark" ? "dark" : "light";
    },
    appearanceFields() {
      return {
        figure_theme: this.resolvedFigureTheme(),
        color_scheme: this.colorScheme || "cellpy",
      };
    },
    onAppearanceChange() {
      localStorage.setItem("csg-figure-theme", this.figureThemePref);
      localStorage.setItem("csg-color-scheme", this.colorScheme);
      this.replotCurrent();
    },
    replotCurrent() {
      if (this.tab === "summary") this.plotSummary();
      else if (this.tab === "cycles") this.plotCycles();
      else if (this.tab === "cell") this.plotCell();
    },

    async refreshPlotTypes() {
      try {
        const basis = encodeURIComponent(this.summary.basis || "gravimetric");
        this.plotTypes = (await (await api(`/api/plot-types?basis=${basis}`)).json()).types;
        this.syncYRangeKeys();
      } catch (_) {}
    },
    currentPlotTypeBasis() {
      const t = this.plotTypes.find((t) => t.id === this.summary.plot_type);
      return t ? t.basis : true;
    },
    currentSummaryPanels() {
      const t = this.plotTypes.find((t) => t.id === this.summary.plot_type);
      return (t && t.panels) || [];
    },
    syncYRangeKeys() {
      const next = {};
      for (const p of this.currentSummaryPanels()) {
        next[p.id] = this.summary.yRanges[p.id] || { min: "", max: "" };
      }
      this.summary.yRanges = next;
    },
    hasYRanges() {
      return Object.values(this.summary.yRanges || {}).some(
        (r) => this.buildAxisRange(r) != null
      );
    },
    buildYRanges() {
      const out = {};
      for (const [key, r] of Object.entries(this.summary.yRanges || {})) {
        const pair = this.buildAxisRange(r);
        if (pair) out[key] = pair;
      }
      return Object.keys(out).length ? out : null;
    },
    async onSummaryPlotOptionsChange() {
      await this.refreshPlotTypes();
      this.plotSummary();
    },
    onYRangeChange() {
      if (this.hasYRanges()) this.summary.share_y = false;
      this.plotSummary();
    },
    async probeCapabilities() {
      try {
        const caps = await (await api("/api/system/capabilities")).json();
        this.canPick = caps.file_picker;
        this.devMode = !!caps.dev_mode;
        if (caps.max_files) this.maxFilesCeiling = caps.max_files;
        // Served instances refuse host paths (#120), so the path field there
        // describes a filesystem the browser cannot see — upload leads instead.
        this.hostPathsAllowed = caps.host_paths_allowed !== false;
        if (caps.max_upload_mb) this.maxUploadMb = caps.max_upload_mb;
      } catch (_) { this.canPick = false; }
    },

    // ---- Add cells modal (#136) ----
    openAddCells(tab) {
      if (this.job.active) return;
      if (tab) this.addCells.tab = tab;
      this.addCells.open = true;
    },
    closeAddCells() {
      this.addCells.open = false;
      this.dragOver = "";
    },
    get addCellsPrimaryLabel() {
      const tab = this.addCells.tab;
      if (tab === "journal") return "Open journal";
      const n = this.loadableStaged(tab).length;
      const verb = tab === "raw" ? "Import" : "Load";
      if (!n) return `${verb} files`;
      return `${verb} ${n} file${n === 1 ? "" : "s"}`;
    },
    get addCellsDisabledReason() {
      if (this.job.active) return "";
      const tab = this.addCells.tab;
      if (tab === "journal") {
        return this.journalPath.trim() ? "" : "Enter or browse to a batch journal.";
      }
      const rows = this.staged[tab];
      if (!rows.length) {
        return tab === "raw"
          ? "Add raw files to the list first."
          : "Add cellpy files to the list first.";
      }
      if (!this.loadableStaged(tab).length) {
        return "None of the staged files can be loaded — remove them or fix the paths.";
      }
      if (tab === "raw" && !this.ingest.instrument) return "Choose an instrument.";
      return "";
    },
    async addCellsPrimary() {
      if (this.addCellsDisabledReason) return;
      const tab = this.addCells.tab;
      if (tab === "cellpy") await this.loadFiles();
      else if (tab === "raw") await this.ingestRaw();
      else await this.loadJournalFromModal();
    },
    get showsH5Hint() {
      return this.staged.cellpy.some((r) => r.ext === ".h5" || r.ext === ".hdf5");
    },
    showsRemoteHint(kind) {
      const re = /^(sftp|ssh|scp):\/\//i;
      return re.test((this.typed[kind] || "").trim()) || this.staged[kind].some((r) => r.status === "remote");
    },
    loadableStaged(kind) {
      return this.staged[kind].filter((r) => r.status !== "missing" && r.status !== "refused");
    },
    acceptedExtensions(kind) {
      if (kind === "cellpy") return [".cellpy", ".h5", ".hdf5"];
      return this.remoteFindExtensions("ingest").map((e) => e.toLowerCase());
    },
    _splitPath(path) {
      const text = String(path);
      const cut = Math.max(text.lastIndexOf("/"), text.lastIndexOf("\\"));
      const name = cut >= 0 ? text.slice(cut + 1) : text;
      const dir = cut >= 0 ? text.slice(0, cut + 1) : "";
      const dot = name.lastIndexOf(".");
      const ext = dot > 0 ? name.slice(dot).toLowerCase() : "";
      return { name, dir, ext };
    },
    _row(kind, path, source, status, detail) {
      const { name, dir, ext } = this._splitPath(path);
      let st = status;
      if (!st) {
        const accepted = this.acceptedExtensions(kind);
        // Advisory only: the loader decides; an odd extension is still sent.
        st = accepted.length && ext && !accepted.includes(ext) ? "unsupported" : "ok";
      }
      return { path, name, dir, ext, source, status: st, detail: detail || "" };
    },
    stage(kind, rows) {
      const have = new Set(this.staged[kind].map((r) => r.path));
      let added = 0;
      for (const row of rows) {
        if (have.has(row.path)) continue;
        have.add(row.path);
        this.staged[kind].push(row);
        added++;
      }
      // Staging new files starts the next round: the previous outcome has
      // been seen, so it makes way for the "why is Load disabled" reason.
      if (added) this.dismissResult();
    },
    unstage(kind, idx) {
      this.staged[kind].splice(idx, 1);
      if (!this.staged[kind].length) this.stageNote[kind] = "";
    },
    clearStaged(kind) {
      this.staged[kind] = [];
      this.stageNote[kind] = "";
    },
    stagedSummary(kind) {
      const rows = this.staged[kind];
      const ok = this.loadableStaged(kind).length;
      const bad = rows.length - ok;
      const base = `${rows.length} file${rows.length === 1 ? "" : "s"} staged`;
      return bad ? `${base} · ${bad} cannot be loaded` : base;
    },
    statusLabel(row) {
      return ({
        ok: "ready", remote: "remote", unsupported: "check type",
        missing: "not found", refused: "refused", failed: "failed",
      })[row.status] || row.status;
    },
    /** Expand typed paths / globs server-side and stage the outcome. */
    async previewInto(kind, patterns, source) {
      const clean = patterns.map((s) => s.trim()).filter(Boolean);
      if (!clean.length) return;
      const max = kind === "raw" ? this._num(this.ingest.maxFiles) : this._num(this.filesMax);
      this.previewBusy = true;
      try {
        const out = await (await api("/api/files/preview", {
          method: "POST", body: { patterns: clean, max_files: max || 10 },
        })).json();
        const rows = [];
        for (const p of out.paths || []) {
          const remote = /^(sftp|ssh|scp):\/\//i.test(p);
          const fromGlob = !clean.includes(p) && clean.some((c) => /[*?[]/.test(c));
          rows.push(this._row(kind, p, fromGlob ? "glob" : source, remote ? "remote" : null));
        }
        // Errors name the offending pattern, so they can sit in the list as
        // rows the user can remove, instead of vanishing into a toast.
        for (const err of out.errors || []) {
          const m = /^(?:Not found|No files matched|Remote path refused|Remote globs are not supported yet): (.+?)(?:\.\s|$)/.exec(err)
            || /^“(.+?)” is outside the data directory/.exec(err);
          const status = /refused|outside the data directory|not supported/i.test(err) ? "refused" : "missing";
          if (m) rows.push(this._row(kind, m[1], source, status, err));
          else this.notify("warn", err);
        }
        this.stage(kind, rows);
        const shown = (out.paths || []).length;
        if (shown && source === "typed") for (const c of clean) this.remember(kind, c);
        this.stageNote[kind] = out.total > shown
          ? `Showing ${shown} of ${out.total} matches — raise “max” or narrow the pattern.`
          : "";
      } catch (e) {
        this.notify("error", e.message || String(e));
      } finally {
        this.previewBusy = false;
      }
    },
    async addTyped(kind) {
      const text = (this.typed[kind] || "").trim();
      if (!text) return;
      await this.previewInto(kind, text.split(";"), "typed");
      this.typed[kind] = "";
    },
    pickInto(kind) {
      this.pick(kind, (paths) => this.stage(kind, paths.map((p) => this._row(kind, p, "pick"))));
    },
    async uploadInto(kind, event) {
      const input = event.target;
      const files = [...(input.files || [])];
      try {
        await this.uploadFiles(kind, files);
      } finally {
        input.value = ""; // let the same file be picked again
      }
    },
    async onDrop(kind, event) {
      const files = [...((event.dataTransfer && event.dataTransfer.files) || [])];
      if (!files.length) return;
      // pywebview exposes the host path on dropped files; when every file
      // carries one, stage those paths directly instead of copying the bytes.
      const full = files.map((f) => f.pywebviewFullPath).filter(Boolean);
      if (this.hostPathsAllowed && full.length === files.length) {
        await this.previewInto(kind, full, "pick");
        return;
      }
      await this.uploadFiles(kind, files);
    },
    /** Upload browser files into the data directory and stage the saved paths. */
    async uploadFiles(kind, files) {
      if (!files.length) return;
      this.uploading = true;
      this.uploadStatus = `Uploading ${files.length} file(s)…`;
      try {
        const body = new FormData();
        for (const f of files) body.append("files", f, f.name);
        // api() throws on a non-2xx with the server's detail already unwrapped.
        const out = await (await api("/api/upload", { method: "POST", body })).json();
        for (const err of out.errors || []) this.notify("warn", err);
        const saved = out.saved || [];
        this.stage(kind, saved.map((s) => this._row(kind, s.path, "upload")));
      } catch (e) {
        this.notify("error", e.message || String(e));
      } finally {
        this.uploading = false;
        this.uploadStatus = "";
      }
    },
    remember(kind, value) {
      const v = (value || "").trim();
      if (!v || !RECENT_KINDS.includes(kind)) return;
      this.recent[kind] = [v, ...this.recent[kind].filter((x) => x !== v)].slice(0, RECENT_CAP);
      try { localStorage.setItem(RECENT_KEY, JSON.stringify(this.recent)); } catch (_) {}
    },
    get resultSummary() {
      const r = this.lastResult;
      if (!r) return "";
      const n = r.added;
      const bad = (r.errors || []).length;
      const head = n ? `Loaded ${n} cell${n === 1 ? "" : "s"}` : "Nothing loaded";
      return bad ? `${head} · ${bad} skipped` : head;
    },
    get resultDetails() {
      const r = this.lastResult;
      return r ? [...(r.errors || []), ...(r.notes || [])] : [];
    },
    dismissResult() {
      this.lastResult = null;
      this.resultOpen = false;
    },
    pickJournalInto() {
      this.pick("journal", (p) => { this.journalPath = p[0]; });
    },
    async loadJournalFromModal() {
      if (!this.journalPath.trim()) return;
      await this.loadImportPath();
      if (!this.job.error) this.closeAddCells();
    },

    get curatedPlotTypes() {
      return this.plotTypes.filter((t) => t.source !== "registry");
    },
    get registryPlotTypes() {
      // Dev mode lists every cellpy family; split so the ones this data cannot
      // plot are visibly grouped and disabled rather than silently empty (#97).
      const reg = this.plotTypes.filter((t) => t.source === "registry");
      return {
        available: reg.filter((t) => !t.unavailable_reason),
        unavailable: reg.filter((t) => t.unavailable_reason),
      };
    },

    get cellUsesIcaOptions() {
      // dQ/dV and dV/dQ share cellpy's IcaOptions (cycles, resolution, direction).
      return this.cell.plotKind === "dqdv" || this.cell.plotKind === "dvdq";
    },
    get cellIsRawKind() {
      // cellpy plots the whole raw frame (cellpy #867), so these are thinned.
      return this.cell.plotKind === "raw" || this.cell.plotKind === "cycleinfo";
    },
    get cellCompareActive() {
      // Compare draws collected curves (#169); raw / cycle-info are per-cell
      // time series with no collection to filter, so they stay single-cell.
      return !!this.cell.compare && !this.cellIsRawKind;
    },
    get cellPlotKindLabel() {
      const base = {
        dqdv: "dQ/dV", dvdq: "dV/dQ", raw: "Raw", cycleinfo: "Raw + steps",
      }[this.cell.plotKind] || "Curves";
      return this.cellCompareActive ? `${base} · compare` : base;
    },
    get cellAxisLabels() {
      if (this.cell.plotKind === "dqdv") return { x: "Voltage x", y: "dQ/dV y" };
      if (this.cell.plotKind === "dvdq") return { x: "Capacity x", y: "dV/dQ y" };
      if (this.cell.plotKind === "raw") return { x: "Time x", y: "Value y" };
      return { x: "Capacity x", y: "Voltage y" };
    },

    get cyclesIsDifferential() {
      // dQ/dV and dV/dQ in the Cycles pane (#95): they come from collect_ica /
      // collect_dva, so mode/method do not apply but direction/resolution do,
      // and the film rendering is available.
      return this.cycles.curveKind === "dqdv" || this.cycles.curveKind === "dvdq";
    },
    get cyclesAxisLabels() {
      if (this.cycles.curveKind === "dqdv") return { x: "Voltage x", y: "dQ/dV y" };
      if (this.cycles.curveKind === "dvdq") return { x: "Capacity x", y: "dV/dQ y" };
      return { x: "Capacity x", y: "Voltage y" };
    },

    get nSelected() { return this.cells.filter((c) => c.selected).length; },
    get nGroups() { return new Set(this.cells.map((c) => c.group)).size; },
    get projectTagLabel() {
      if (!this.project) return "no project";
      return this.dirty ? `${this.project}*` : this.project;
    },
    get projectTagTitle() {
      if (!this.project) return "No project name yet — Save writes cells to a folder.";
      if (this.dirty) return "Unsaved changes — click Save to write the project folder.";
      return "Project saved to disk (in this session).";
    },
    markDirty() { this.dirty = true; },
    get filteredSortedCells() {
      let list = this.cells.slice();
      const q = (this.cellsManagerFilter || "").trim().toLowerCase();
      if (q) list = list.filter((c) => (c.label || "").toLowerCase().includes(q));
      if (this.cellsManagerSort === "group") {
        list.sort((a, b) => a.group - b.group || (a.label || "").localeCompare(b.label || ""));
      } else if (this.cellsManagerSort === "name") {
        list.sort((a, b) => (a.label || "").localeCompare(b.label || ""));
      }
      return list;
    },

    nomCapUnit(basis) {
      return ({ gravimetric: "mAh/g", areal: "mAh/cm²", absolute: "mAh" })[basis] || "mAh/g";
    },
    fmt(v, d = 2) {
      if (v === null || v === undefined || isNaN(v)) return "–";
      return Number(v).toLocaleString(undefined, { maximumFractionDigits: d });
    },

    currentCell() { return this.cells.find((c) => c.id === this.cell.cell_id); },

    async refreshState() {
      const s = await (await api("/api/state")).json();
      this.cells = s.cells;
      this.project = s.project;
      if (this.project && !this.saveName) this.saveName = this.project;
      // Every load job ends here, so a successful load folds the Data panel
      // and an emptied library unfolds it again.
      this.dataCollapsed = this.cells.length > 0;
      // Dev mode marks each cellpy family against the *loaded* cells, so the
      // list goes stale whenever the library changes (it is first built at
      // startup, when nothing is loaded yet).
      if (this.devMode) await this.refreshPlotTypes();
      if (this.tab === "summary") this.plotSummary();
      if (this.tab === "cycles") this.ensureCyclesBounds();
      if (this.tab === "cell") this.ensureCellSelected();
    },

    async refreshProjects() {
      try {
        const r = await (await api("/api/projects")).json();
        this.projects = r.projects;
        this.project = r.current.name;
        this.projectCellpyConfig = r.current.cellpy_config || "";
        if (this.project && !this.saveName) this.saveName = this.project;
        if (this.openTarget && !this.projects.some((p) => p.slug === this.openTarget)) {
          this.openTarget = "";
        }
      } catch (_) {}
    },

    async saveProject() {
      const name = this.saveName.trim();
      if (!name || !this.cells.length) return;
      await this.runJob("/api/projects/save", { name });
      this.dirty = false;
      await this.refreshProjects();
    },
    async openProject() {
      if (!this.openTarget) return;
      await this.runJob("/api/projects/open", { target: this.openTarget });
      this.dirty = false;
      await this.refreshProjects();
    },
    async closeProject() {
      if (!this.cells.length && !this.project) return;
      const msg = this.dirty
        ? "Close the current project? Unsaved changes will be lost."
        : "Close the current project and clear loaded cells?";
      if (!window.confirm(msg)) return;
      await this.clearAll();
      this.saveName = "";
      this.dirty = false;
      this.notify("ok", "Project closed.");
    },

    // ---- loading (jobs + SSE) ----
    async loadExamples() {
      const kinds = this.examples.length ? this.examples.map((e) => e.id) : ["cellpy", "old_cellpy", "rate"];
      await this.runJob("/api/load/example", { kinds });
    },
    async loadFiles() {
      const paths = this.loadableStaged("cellpy").map((r) => r.path);
      if (!paths.length) return;
      // The preview already applied the cap, so every staged path is wanted.
      await this._runStagedJob("cellpy", "/api/load/files", { paths, max_files: paths.length });
    },
    /** Run a load / ingest job for a staged list, then settle the list from the result. */
    async _runStagedJob(kind, url, body) {
      this.lastResult = null;
      await this.runJob(url, body);
      const r = this.lastResult;
      if (!r || r.kind !== "added") return; // job failed outright: keep the list
      const errs = r.errors || [];
      // Loader errors read "<path>: <reason>", so a failing row can stay in
      // the list, marked, while everything that loaded leaves it.
      const keep = [];
      for (const row of this.staged[kind]) {
        const err = errs.find((e) => e.startsWith(row.path));
        if (err) keep.push({ ...row, status: "failed", detail: err });
        else if (row.status === "missing" || row.status === "refused") keep.push(row);
      }
      this.staged[kind] = keep;
      if (!keep.length) {
        this.stageNote[kind] = "";
        this.closeAddCells();
      }
    },
    async loadImportPath() {
      const path = this.journalPath.trim();
      if (!path) return;
      let kind;
      try {
        kind = (await (await api("/api/projects/classify-import", {
          method: "POST", body: { path },
        })).json()).kind;
      } catch (e) {
        this.notify("error", e.message || String(e));
        return;
      }
      if (kind === "project") {
        await this.runJob("/api/projects/open", { target: path });
        this.dirty = false;
      } else {
        await this.runJob("/api/projects/load-journal", { path });
      }
      if (!this.job.error) this.remember("journal", path);
      this.journalPath = "";
      await this.refreshProjects();
    },
    /** @deprecated use loadImportPath — kept for any leftover call sites */
    async loadJournal() { return this.loadImportPath(); },

    // ---- native file pickers (desktop only) ----
    async pick(kind, assign) {
      try {
        const r = await (await api("/api/system/pick", { method: "POST", body: { kind } })).json();
        if (r.paths && r.paths.length) assign(r.paths);
      } catch (e) { this.notify("error", e.message); }
    },
    pickImportFile() { this.pick("journal", (p) => { this.journalPath = p[0]; this.loadImportPath(); }); },
    pickJournal() { this.pickImportFile(); },

    async refreshInstruments() {
      try {
        const r = await (await api("/api/instruments")).json();
        this.instruments = r.instruments;
        this.rawExamples = r.examples;
        if (!this.ingest.instrument && this.instruments.length)
          this.ingest.instrument = this.instruments[0].id;
      } catch (_) {}
    },
    currentInstrument() {
      return this.instruments.find((i) => i.id === this.ingest.instrument) || null;
    },
    currentModels() {
      const ins = this.currentInstrument();
      return ins ? ins.models : [];
    },
    _num(v) {
      const n = parseFloat(v);
      return Number.isFinite(n) ? n : null;
    },
    async ingestRaw() {
      const paths = this.loadableStaged("raw").map((r) => r.path);
      if (!paths.length) return;
      const body = {
        paths,
        max_files: paths.length,
        instrument: this.ingest.instrument,
        model: this.ingest.model || null,
        mass: this._num(this.ingest.mass),
        area: this._num(this.ingest.area),
        nominal_capacity: this._num(this.ingest.nominal_capacity),
        nom_cap_specifics: this.ingest.nom_cap_specifics || null,
        cycle_mode: this.ingest.cycle_mode || null,
      };
      await this._runStagedJob("raw", "/api/ingest", body);
    },
    async ingestExample(kind) {
      await this.runJob("/api/ingest/example", { kind, mass: this._num(this.ingest.mass) });
    },
    // ---- remote folder find (#162) ----
    remoteFindExtensions(target) {
      if (target === "load") return [".cellpy", ".h5"];
      const ins = this.currentInstrument();
      return ins && ins.suffixes ? ins.suffixes : [];
    },
    async findRemote(target) {
      const form = this.remoteFind[target];
      const directory = (form.dir || "").trim();
      if (!directory) return;
      const max = target === "load" ? this._num(this.filesMax) : this._num(this.ingest.maxFiles);
      this._remoteFindTarget = target;
      await this.runJob("/api/remote/find", {
        directory,
        extensions: this.remoteFindExtensions(target),
        filter: (form.filter || "").trim() || null,
        max_files: max || 10,
      });
      this._remoteFindTarget = null; // cleared already on success; also on error/cancel
    },
    _applyRemoteFind(r) {
      const target = this._remoteFindTarget;
      this._remoteFindTarget = null;
      const paths = r.paths || [];
      const errs = r.errors || [];
      const notes = r.notes || [];
      const kind = target === "ingest" ? "raw" : "cellpy";
      if (paths.length) {
        // Matches land in the staged list, where each one can be reviewed or
        // removed before the load — no more `;`-joined string to eyeball.
        this.stage(kind, paths.map((p) => this._row(kind, p, "remote", "remote")));
        this.stageNote[kind] = r.total > paths.length
          ? `Found ${r.total} files, showing the first ${paths.length} — raise “max” or narrow the filter.`
          : "";
        this.remember("remoteDir", this.remoteFind[target].dir);
        this.remoteFind[target].open = false;
      } else if (errs.length) {
        this.notify("error", errs.join(" · "));
      } else {
        this.notify("warn", "No files found.");
      }
      if (errs.length && paths.length) this.notify("warn", errs.join(" · "));
      if (notes.length) this.notify("warn", notes.join(" · "));
    },
    async runJob(url, body) {
      this._closeJobStream();
      this.job = { active: true, id: "", progress: 0, message: "Starting…", error: "" };
      let job_id;
      try {
        job_id = (await (await api(url, { method: "POST", body })).json()).job_id;
      } catch (e) {
        this.job = { active: false, id: "", progress: 0, message: "", error: e.message };
        this.notify("error", e.message || "Job failed to start.");
        return;
      }
      this.job.id = job_id;
      await this.streamJob(job_id);
    },
    streamJob(job_id) {
      return new Promise((resolve) => {
        this._closeJobStream();
        const es = new EventSource(`/api/jobs/${job_id}/events?token=${encodeURIComponent(TOKEN)}`);
        this._jobEs = es;
        es.onmessage = (ev) => {
          if (this._jobEs !== es) return; // dismissed / superseded
          const s = JSON.parse(ev.data);
          this.job.progress = s.progress;
          this.job.message = s.message;
          if (["done", "error", "cancelled"].includes(s.status)) {
            this._closeJobStream();
            this.job.active = false;
            this.job.error = "";
            if (s.status === "error") this.notify("error", s.message || "Job failed.");
            else if (s.status === "cancelled") this.notify("warn", "Cancelled.");
            else this.reportJobResult(s.result);
            this.refreshState();
            resolve();
          }
        };
        es.onerror = () => {
          if (this._jobEs !== es) { resolve(); return; }
          this._closeJobStream();
          this.job.active = false;
          this.notify("error", "Lost connection to the job.");
          this.refreshState();
          resolve();
        };
      });
    },
    _closeJobStream() {
      if (this._jobEs) {
        try { this._jobEs.close(); } catch (_) {}
        this._jobEs = null;
      }
    },
    async cancelJob() {
      const id = this.job.id;
      if (!id || !this.job.active) return;
      this.job.message = "Cancelling…";
      try {
        await api(`/api/jobs/${id}/cancel`, { method: "POST" });
      } catch (e) {
        this.notify("error", e.message || "Could not cancel.");
      }
      // Cooperative cancel may wait on a blocked cellpy call — still free the UI.
      this.dismissJob("Cancel requested — UI unlocked. The job will stop when possible.");
    },
    dismissJob(note) {
      this._closeJobStream();
      const id = this.job.id;
      this.job = { active: false, id: "", progress: 0, message: "", error: "" };
      if (id) {
        // Best-effort: ask the backend to stop even if we already left the stream.
        api(`/api/jobs/${id}/cancel`, { method: "POST" }).catch(() => {});
      }
      this.notify("warn", note || "Progress dismissed — you can keep working.");
      this.refreshState();
    },
    reportJobResult(r) {
      if (!r || typeof r !== "object") return;
      // remote find (#162) reports {paths:[...], total, errors:[...], notes:[...]}
      if ("paths" in r && "total" in r) {
        this._applyRemoteFind(r);
        return;
      }
      // load / ingest jobs report {added:[...], errors:[...], matched?, note?}
      if ("added" in r) {
        const n = (r.added || []).length;
        const errs = r.errors || [];
        const notes = r.notes || [];
        this.lastResult = { kind: "added", added: n, errors: errs, notes, at: Date.now() };
        this.resultOpen = false;
        // The result card (modal footer / Data panel) carries the outcome and
        // its details, so only outright failure still interrupts with a toast.
        if (!n && errs.length) this.notify("error", errs.join(" · "));
        else if (!n) this.notify("warn", "Nothing was loaded — no files matched.");
      } else if ("name" in r && "n_cells" in r) {
        const n = r.n_cells;
        const cells = `${n} cell${n === 1 ? "" : "s"}`;
        if (r.action === "saved") {
          this.dirty = false;
          this.notify("ok", `Saved “${r.name}” — ${cells}.`);
        } else if (r.action === "opened") {
          this.dirty = false;
          this.notify("ok", `Opened “${r.name}” — ${cells}.`);
        } else {
          this.notify("ok", `Project “${r.name}” — ${cells}.`);
        }
      }
      if ("added" in r && (r.added || []).length) this.markDirty();
    },
    notify(type, text, { sticky = false } = {}) {
      const id = Date.now() + Math.random();
      this.notices.push({ id, type, text });
      if (!sticky) {
        setTimeout(() => { this.notices = this.notices.filter((n) => n.id !== id); }, type === "error" ? 9000 : 5000);
      }
      return id;
    },
    dismissNotice(id) {
      this.notices = this.notices.filter((n) => n.id !== id);
    },

    // ---- editing ----
    openCellsManager() {
      this.cellsManagerOpen = true;
      this._replotOnClose = false;
      this.$nextTick(() => this.$refs.cellsManagerFilter?.focus());
    },
    closeCellsManager() {
      if (!this.cellsManagerOpen) return;
      this.cellsManagerOpen = false;
      // One redraw for the whole editing session, not one per edit (#184).
      if (this._replotOnClose) {
        this._replotOnClose = false;
        this.replotCurrent();
      }
    },
    /** The library changed: redraw now, or once the Manage cells modal closes. */
    _replotAfterEdit() {
      if (this.cellsManagerOpen) {
        this._replotOnClose = true;
        return;
      }
      this.replotCurrent();
    },
    async openCellpyConfig() {
      this.cellpyConfigOpen = true;
      // Re-read every time: the user may edit cellpy.toml while the app is open.
      this.cellpyConfigLoading = true;
      this.cellpyConfigError = "";
      try {
        this.cellpyConfig = await (await api("/api/system/cellpy-config")).json();
      } catch (e) {
        this.cellpyConfig = null;
        this.cellpyConfigError = `Could not read the cellpy configuration: ${e.message || e}`;
      } finally {
        this.cellpyConfigLoading = false;
      }
    },
    async openDiagnostics() {
      this.diagOpen = true;
      await this.refreshDiagnostics();
    },
    closeDiagnostics() {
      this.diagOpen = false;
      this.diagAuto = false;
      this.toggleDiagAuto();
    },
    toggleDiagAuto() {
      if (this._diagTimer) { clearInterval(this._diagTimer); this._diagTimer = null; }
      if (this.diagAuto && this.diagOpen) {
        this._diagTimer = setInterval(() => this.refreshDiagnostics(), 2000);
      }
    },
    async refreshDiagnostics() {
      this.diagError = "";
      try {
        if (this.diagTab === "logs") {
          const lvl = this.diagLevel ? `&level=${this.diagLevel}` : "";
          const r = await (await api(`/api/system/logs?limit=300${lvl}`)).json();
          this.diagLogs = r.records;
        } else {
          this.diagJobs = (await (await api("/api/system/jobs")).json()).jobs;
        }
      } catch (e) {
        this.diagError = e.message || "Could not read diagnostics.";
      }
    },
    async copyDiagnostics() {
      // Plain text, so it can go straight into a bug report.
      const lines = this.diagTab === "logs"
        ? this.diagLogs.map((r) => `${r.time} ${r.level} ${r.name} - ${r.message}`)
        : this.diagJobs.map((j) =>
            `${j.kind} ${j.status} queued=${j.queued_seconds}s ran=${j.elapsed_seconds}s ${j.error || j.message}`
          );
      const text = lines.join("\n");
      try {
        await navigator.clipboard.writeText(text);
        this.notify("ok", "Copied to the clipboard.");
      } catch (_) {
        this.notify("error", "Could not copy — select the text manually.");
      }
    },
    async pinProjectConfig() {
      if (!this.project || this.cellpyConfigPinning) return;
      if (
        this.projectCellpyConfig &&
        !window.confirm(`Overwrite the cellpy settings already pinned to “${this.project}”?`)
      ) return;
      this.cellpyConfigPinning = true;
      try {
        const r = await (await api("/api/projects/pin-config", { method: "POST" })).json();
        this.projectCellpyConfig = r.current?.cellpy_config || "";
        this.notify("ok", `Pinned ${r.sections.join(", ")} to “${this.project}”.`);
        await this.openCellpyConfig(); // re-read so the layer badges update
      } catch (e) {
        this.notify("error", e.message || "Could not pin the settings.");
      } finally {
        this.cellpyConfigPinning = false;
      }
    },
    async updateCell(id, patch, { plot = true } = {}) {
      const body = { id, ...patch };
      // library.update ignores non-positive / missing physical numerics
      for (const key of ["mass", "area", "nominal_capacity"]) {
        if (key in patch && (patch[key] === null || patch[key] === undefined)) {
          delete body[key];
        }
      }
      for (const key of ["cycle_mode", "nom_cap_specifics"]) {
        if (key in patch && !patch[key]) {
          delete body[key];
        }
      }
      const r = await (await api(`/api/cells/${id}/update`, { method: "POST", body })).json();
      this.cells = r.state.cells;
      this.markDirty();
      if (plot) this._replotAfterEdit();
    },
    async selectAll(v) {
      const s = await (await api(`/api/cells/select?value=${v}`, { method: "POST" })).json();
      this.cells = s.cells;
      this.markDirty();
      this._replotAfterEdit();
    },
    async selectGroup() {
      const g = Number(this.cellsManagerGroup);
      if (!Number.isFinite(g) || g < 1) return;
      // Select only this group (deselect others). Previously skipped already-selected
      // members, so the control looked dead when every cell started selected.
      for (const c of this.cells) {
        const want = Number(c.group) === g;
        if (Boolean(c.selected) !== want) {
          await this.updateCell(c.id, { selected: want }, { plot: false });
        }
      }
      this._replotAfterEdit();
    },
    async removeCell(id) {
      const s = await (await api(`/api/cells/${id}`, { method: "DELETE" })).json();
      this.cells = s.cells;
      this.markDirty();
      if (this.cell.cell_id === id) this.cell.cell_id = "";
      if (!this.cells.length) this.dataCollapsed = false;
      this._replotAfterEdit();
    },
    async clearAll() {
      const s = await (await api("/api/cells/clear", { method: "POST" })).json();
      this.cells = s.cells; this.cell.cell_id = ""; this.project = s.project;
      this.dirty = false;
      this.dataCollapsed = false;
      this.dismissResult();
      this.cellsManagerOpen = false;
      this._replotOnClose = false;
      Plotly.purge("summaryChart"); Plotly.purge("cyclesChart"); Plotly.purge("cellChart");
      this.replotCurrent();
    },

    // ---- summary plot ----
    summarySpec() {
      const y_ranges = this.buildYRanges();
      return {
        plot_type: this.summary.plot_type,
        basis: this.summary.basis,
        group_average: this.summary.group_average,
        spread: this.summary.spread,
        group_legend_muting: !!this.summary.group_legend_muting,
        max_cycle: this._num(this.summary.max_cycle),
        share_y: !!this.summary.share_y && !y_ranges,
        ...(y_ranges ? { y_ranges } : {}),
        title: "Cycle summary",
        ...this.appearanceFields(),
      };
    },
    async _withPlotBusy(kind, fn) {
      // Counted, not boolean: with several requests in flight the spinner
      // used to vanish when the *first* one came back (#184).
      this._plotInflight[kind]++;
      this.plotBusy[kind] = true;
      try {
        await fn();
      } catch (e) {
        console.error(e);
      } finally {
        this._plotInflight[kind]--;
        if (this._plotInflight[kind] <= 0) {
          this._plotInflight[kind] = 0;
          this.plotBusy[kind] = false;
        }
      }
    },
    /** Fetch a figure; resolves to it, or to null when a newer request for the same chart has since started (#184). */
    async _fetchFigure(kind, url, body) {
      const seq = ++this._plotSeq[kind];
      const fig = await (await api(url, { method: "POST", body })).json();
      return this._plotSeq[kind] === seq ? fig : null;
    },
    _drawFigure(id, fig) {
      Plotly.react(id, fig.data, fig.layout, PLOTLY_CONFIG);
      this._applyFigureHeight(id, fig);
      requestAnimationFrame(() => this.relayoutCharts());
    },
    async plotSummary() {
      await this._withPlotBusy("summary", async () => {
        const fig = await this._fetchFigure("summary", "/api/plots/summary", this.summarySpec());
        if (fig) this._drawFigure("summaryChart", fig);
      });
    },

    // ---- cycles collector (selected cells) ----
    async ensureCyclesBounds() {
      if (!this.nSelected) {
        Plotly.purge("cyclesChart");
        this.cycles.min = 0; this.cycles.max = 0;
        return;
      }
      await this._withPlotBusy("cycles", async () => {
        try {
          const info = await (await api("/api/plots/cycles/bounds")).json();
          this.cycles.min = info.min; this.cycles.max = info.max;
          if (!this.cycles.from || this.cycles.from < info.min || this.cycles.from > info.max) {
            this.cycles.from = info.min;
          }
          if (!this.cycles.to || this.cycles.to < this.cycles.from || this.cycles.to > info.max) {
            this.cycles.to = Math.min(info.max, info.min + 9);
          }
        } catch (e) { console.error(e); }
        await this._plotCyclesFigure();
      });
    },
    buildCycleListFrom(state) {
      let { from, to, maxCurves, min, max } = state;
      from = Math.max(min, Math.min(from, max));
      to = Math.max(from, Math.min(to, max));
      const span = to - from + 1;
      const n = Math.max(1, Math.min(maxCurves, span));
      const step = (n === 1) ? 0 : (span - 1) / (n - 1);
      const out = new Set();
      for (let i = 0; i < n; i++) out.add(Math.round(from + i * step));
      return [...out].sort((a, b) => a - b);
    },
    cyclesSpec() {
      return {
        cycles: this.buildCycleListFrom(this.cycles),
        mode: this.cycles.mode, method: this.cycles.method,
        layout: this.cycles.layout,
        curve_kind: this.cycles.curveKind || "voltage",
        direction: this.cycles.direction || "charge",
        voltage_resolution: Number(this.cycles.voltageResolution) || 0.005,
        group_legend_muting: !!this.cycles.group_legend_muting,
        title: "",
        ...this.axisRangeFields(this.cycles),
        ...this.appearanceFields(),
      };
    },
    async _plotCyclesFigure() {
      if (!this.nSelected) {
        Plotly.purge("cyclesChart");
        return;
      }
      const fig = await this._fetchFigure("cycles", "/api/plots/cycles", this.cyclesSpec());
      if (fig) this._drawFigure("cyclesChart", fig);
    },
    async plotCycles() {
      if (!this.nSelected) {
        Plotly.purge("cyclesChart");
        return;
      }
      await this._withPlotBusy("cycles", () => this._plotCyclesFigure());
    },

    // ---- cell explorer ----
    ensureCellSelected() {
      if (!this.cells.length) { Plotly.purge("cellChart"); return; }
      if (!this.cell.cell_id || !this.currentCell()) this.cell.cell_id = this.cells[0].id;
      this.onCellChange();
    },
    async onCellChange() {
      if (!this.cell.cell_id) return;
      await this._withPlotBusy("cell", async () => {
        const info = await (await api(`/api/cells/${this.cell.cell_id}/cycles`)).json();
        this.cell.min = info.min; this.cell.max = info.max;
        this.cell.from = info.min;
        this.cell.to = Math.min(info.max, info.min + 9);
        // The top Cell select stays pick #1 in compare mode, so the mental
        // model is "the explorer, plus more cells" (#169).
        if (this.cell.picks.length) {
          Object.assign(this.cell.picks[0], { cell_id: this.cell.cell_id, min: info.min, max: info.max });
        }
        await this._plotCellFigure();
      });
    },

    // ---- compare mode (#169) ----
    parseCycleList(text, limit = 40) {
      // "1, 3, 5-9" → [1, 3, 5, 6, 7, 8, 9]; de-duplicated, sorted, capped so
      // one pick cannot flood the figure. Deliberately *not* clamped to the
      // cell's cycle range: a cycle the cell lacks must reach the server so
      // the figure can say so, instead of vanishing on the way out (#175).
      const out = new Set();
      for (const tok of String(text || "").split(/[,\s;]+/)) {
        if (!tok) continue;
        const m = /^(\d+)\s*[-–:]\s*(\d+)$/.exec(tok);
        let a, b;
        if (m) { a = Number(m[1]); b = Number(m[2]); }
        else if (/^\d+$/.test(tok)) { a = b = Number(tok); }
        else continue;
        if (a > b) [a, b] = [b, a];
        a = Math.max(a, 1);
        for (let c = a; c <= b && out.size < limit; c++) out.add(c);
        if (out.size >= limit) break;
      }
      return [...out].sort((x, y) => x - y);
    },
    pickRangeHint(p) {
      return p.min ? `${p.min}–${p.max}` : "1, 3, 5-9";
    },
    _newPick(cell_id, cyclesText) {
      return {
        key: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        cell_id, cyclesText, min: 0, max: 0,
      };
    },
    async _loadPickBounds(pick) {
      try {
        const info = await (await api(`/api/cells/${pick.cell_id}/cycles`)).json();
        pick.min = info.min; pick.max = info.max;
      } catch (e) { console.error(e); }
    },
    async onCompareToggle() {
      if (this.cell.compare && !this.cell.picks.length) {
        // Pick #1 is the explorer's current selection; a second cell is added
        // straight away so the toggle shows a comparison, not the same chart.
        const seed = this.buildCycleListFrom(this.cell).join(", ");
        const first = this._newPick(this.cell.cell_id, seed);
        first.min = this.cell.min; first.max = this.cell.max;
        this.cell.picks = [first];
        const other = this.cells.find((c) => c.id !== this.cell.cell_id);
        if (other) {
          const second = this._newPick(other.id, seed);
          this.cell.picks.push(second);
          await this._loadPickBounds(second);
        }
      }
      await this.plotCell();
    },
    async addPick() {
      if (this.cell.picks.length >= 8) return;
      const taken = new Set(this.cell.picks.map((p) => p.cell_id));
      const next = this.cells.find((c) => !taken.has(c.id)) || this.cells[0];
      if (!next) return;
      const last = this.cell.picks[this.cell.picks.length - 1];
      const pick = this._newPick(next.id, last ? last.cyclesText : String(this.cell.from));
      this.cell.picks.push(pick);
      await this._loadPickBounds(pick);
      await this.plotCell();
    },
    async removePick(i) {
      if (this.cell.picks.length <= 1) return;
      this.cell.picks.splice(i, 1);
      if (i === 0 && this.cell.picks[0].cell_id !== this.cell.cell_id) {
        // Row 1 is mirrored by the top Cell select; keep them in step.
        this.cell.cell_id = this.cell.picks[0].cell_id;
        await this.onCellChange();
        return;
      }
      await this.plotCell();
    },
    async onPickCellChange(i) {
      const pick = this.cell.picks[i];
      if (!pick) return;
      await this._loadPickBounds(pick);
      if (i === 0 && pick.cell_id !== this.cell.cell_id) {
        this.cell.cell_id = pick.cell_id;
        await this.onCellChange();
        return;
      }
      await this.plotCell();
    },
    compareSpec() {
      const res = Number(this.cell.voltageResolution);
      const kind = this.cell.plotKind;
      return {
        picks: this.cell.picks.map((p) => ({
          cell_id: p.cell_id,
          cycles: this.parseCycleList(p.cyclesText),
        })),
        curve_kind: kind === "dqdv" || kind === "dvdq" ? kind : "voltage",
        mode: this.cell.mode, method: this.cell.method,
        direction: ["charge", "discharge", "both"].includes(this.cell.direction)
          ? this.cell.direction
          : "charge",
        voltage_resolution: Number.isFinite(res) && res > 0 ? res : 0.005,
        layout: this.cell.compareLayout === "per_cell" ? "per_cell" : "overlay",
        title: "",
        ...this.axisRangeFields(this.cell),
        ...this.appearanceFields(),
      };
    },
    buildAxisRange(r) {
      if (!r) return null;
      const lo = this._num(r.min);
      const hi = this._num(r.max);
      if (lo == null && hi == null) return null;
      if (lo != null && hi != null && lo >= hi) return null;
      // One end may be null — server fills it from the data extent.
      return [lo, hi];
    },
    axisRangeFields(state) {
      const x_range = this.buildAxisRange(state?.xRange);
      const y_range = this.buildAxisRange(state?.yRange);
      return {
        ...(x_range ? { x_range } : {}),
        ...(y_range ? { y_range } : {}),
      };
    },
    cellSpec() {
      return {
        cell_id: this.cell.cell_id,
        cycles: this.buildCycleListFrom(this.cell),
        mode: this.cell.mode, method: this.cell.method,
        layout: "per_cell", title: "",
        ...this.axisRangeFields(this.cell),
        ...this.appearanceFields(),
      };
    },
    rawSpec() {
      return {
        cell_id: this.cell.cell_id,
        plot_type: this.cell.rawPlotType || "voltage-current",
        max_points: this._num(this.cell.maxPoints) || 4000,
        ...this.axisRangeFields(this.cell),
        ...this.appearanceFields(),
      };
    },
    cycleInfoSpec() {
      return {
        cell_id: this.cell.cell_id,
        cycles: this.buildCycleListFrom(this.cell),
        ...this.appearanceFields(),
      };
    },
    icaSpec() {
      const res = Number(this.cell.voltageResolution);
      return {
        cell_id: this.cell.cell_id,
        cycles: this.buildCycleListFrom(this.cell),
        voltage_resolution: Number.isFinite(res) && res > 0 ? res : 0.005,
        direction: ["charge", "discharge", "both"].includes(this.cell.direction)
          ? this.cell.direction
          : "charge",
        title: "",
        ...this.axisRangeFields(this.cell),
        ...this.appearanceFields(),
      };
    },
    _figureNotes(fig) {
      // Core stamps user-facing notes in layout.meta.warnings (#175).
      const w = fig?.layout?.meta?.warnings;
      return Array.isArray(w) ? w.map(String) : [];
    },
    async _plotCellFigure() {
      if (!this.cell.cell_id) return;
      if (this.cellCompareActive) {
        const fig = await this._fetchFigure("cell", "/api/plots/compare", this.compareSpec());
        if (!fig) return;
        this.cell.notes = this._figureNotes(fig);
        this._drawFigure("cellChart", fig);
        return;
      }
      const kind = this.cell.plotKind;
      const url = kind === "dqdv" ? "/api/plots/ica"
        : kind === "dvdq" ? "/api/plots/dva"
        : kind === "raw" ? "/api/plots/raw"
        : kind === "cycleinfo" ? "/api/plots/cycle-info"
        : "/api/plots/cycles";
      // DVA reuses the ICA spec — cellpy derives both from IcaOptions.
      const body = this.cellUsesIcaOptions ? this.icaSpec()
        : kind === "raw" ? this.rawSpec()
        : kind === "cycleinfo" ? this.cycleInfoSpec()
        : this.cellSpec();
      const fig = await this._fetchFigure("cell", url, body);
      if (!fig) return;
      this.cell.notes = this._figureNotes(fig);
      this._drawFigure("cellChart", fig);
    },
    async plotCell() {
      if (!this.cell.cell_id) return;
      await this._withPlotBusy("cell", () => this._plotCellFigure());
    },

    // ---- exports (data + static figures via kaleido + library cells) ----
    async exportSummary(fmt) {
      await this.download(`/api/export/summary?fmt=${fmt}`, this.summarySpec(), `summary.${fmt}`);
    },
    async exportCycles(fmt) {
      if (!this.cell.cell_id) return;
      if (this.cellCompareActive) {
        // Export parity: the same picks the chart drew (#169).
        await this.download(`/api/export/compare?fmt=${fmt}`, this.compareSpec(), `compare.${fmt}`);
        return;
      }
      if (this.cell.plotKind === "dqdv") {
        await this.download(`/api/export/ica?fmt=${fmt}`, this.icaSpec(), `ica.${fmt}`);
        return;
      }
      if (this.cell.plotKind === "dvdq") {
        await this.download(`/api/export/dva?fmt=${fmt}`, this.icaSpec(), `dva.${fmt}`);
        return;
      }
      if (this.cellIsRawKind) {
        // No raw data endpoint: the figure is thinned for the browser, so an
        // export from it would be misleading. Point at the real sources.
        this.notify(
          "warn",
          "For raw data use Export cells (csv); for this figure use the camera " +
          "icon in the plot toolbar."
        );
        return;
      }
      await this.download(`/api/export/cycles?fmt=${fmt}`, this.cellSpec(), `cycles.${fmt}`);
    },
    async exportCyclesCollector(fmt) {
      if (!this.nSelected) return;
      await this.download(`/api/export/cycles?fmt=${fmt}`, this.cyclesSpec(), `cycles.${fmt}`);
    },
    async exportLibraryCells(fmt) {
      if (!this.nSelected) {
        this.notify("error", "Select one or more cells to export.");
        return;
      }
      await this.download(`/api/export/cells?fmt=${fmt}`, {}, `cells.${fmt}`);
    },
    async download(url, body, filename) {
      // Figure exports (kaleido) can take seconds before the Save dialog appears.
      const ext = String(filename || "").split(".").pop()?.toLowerCase() || "";
      const isFigure = this.figureFormats.includes(ext);
      let statusId = null;
      if (isFigure || this.canPick) {
        statusId = this.notify("warn", "Preparing export…", { sticky: true });
        await this.$nextTick();
        await new Promise((r) => setTimeout(r, 0));
      }
      try {
        const res = await api(url, { method: "POST", body });
        const cd = res.headers.get("Content-Disposition") || "";
        const m = /filename\*?=(?:UTF-8''|")?([^\";]+)/i.exec(cd);
        const name = (m ? decodeURIComponent(m[1].replace(/"/g, "")) : filename) || filename;
        const blob = await res.blob();
        // Desktop (pywebview): <a download> often never reaches the real Downloads
        // folder — use a native Save As dialog and write the bytes server-side.
        if (this.canPick) {
          if (statusId) {
            this.dismissNotice(statusId);
            statusId = this.notify("warn", "Choose where to save…", { sticky: true });
          }
          const saveRes = await fetch(
            `/api/system/save?filename=${encodeURIComponent(name)}`,
            {
              method: "POST",
              headers: {
                "X-CSG-Token": TOKEN,
                "Content-Type": "application/octet-stream",
              },
              credentials: "same-origin",
              body: blob,
            },
          );
          if (!saveRes.ok) {
            let detail = saveRes.statusText;
            try { detail = (await saveRes.json()).detail || detail; } catch (_) {}
            throw new Error(detail);
          }
          const out = await saveRes.json();
          if (out.cancelled || !out.path) {
            this.notify("ok", "Export cancelled.");
            return;
          }
          this.notify("ok", `Saved “${name}” to ${out.path}`);
          return;
        }
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob); a.download = name; a.click();
        URL.revokeObjectURL(a.href);
        this.notify("ok", `Download started for “${name}”.`);
      } catch (e) {
        this.notify("error", `Export failed: ${e.message}`);
      } finally {
        if (statusId) this.dismissNotice(statusId);
      }
    },

    // ---- misc ----
    toggleTheme() {
      this.theme = this.theme === "dark" ? "light" : "dark";
      localStorage.setItem("csg-theme", this.theme);
    },
    _applyFigureHeight(id, fig) {
      // Keep the Plotly div at least at the figure's layout height so
      // Plots.resize only adjusts width and does not squash the last facet /
      // x-axis (#63). The natural height is remembered so a later window
      // resize can re-fit without another round trip.
      const el = document.getElementById(id);
      const h = fig && fig.layout && fig.layout.height;
      if (!el || !h) return;
      el.dataset.naturalHeight = String(h);
      this._fitChartHeight(el);
    },
    _fitChartHeight(el) {
      const natural = Number(el.dataset.naturalHeight);
      if (!natural) return;
      // offsetParent is null while the tab is hidden — measuring then gives a
      // meaningless height, so leave it for when the tab is shown.
      // .chart carries a CSS min-height; without folding it in, the div sits at
      // that floor while the figure stays shorter, leaving a gap inside the card.
      const cssMin = parseFloat(getComputedStyle(el).minHeight) || 0;
      const target = el.offsetParent === null
        ? Math.max(natural, cssMin)
        : Math.max(natural, cssMin, this._availableChartHeight(el));
      el.style.height = `${target}px`;
      // Plotly honours an explicit layout.height, so the div alone is not
      // enough — the figure has to be told as well.
      const current = el.layout && el.layout.height;
      if (el.data && current !== target) Plotly.relayout(el, { height: target });
    },
    _availableChartHeight(el) {
      // A single-panel figure is much shorter than the pane, which left a big
      // empty gap under the Cell-explorer chart (#93). Grow it to the bottom of
      // the scroll area; never shrink — that is what clipped facets in #63.
      const card = el.closest(".chart-card") || el;
      const scroller = el.closest(".main");
      if (!scroller) return 0;
      const cardBox = card.getBoundingClientRect();
      // Measure the card's offset within the *content*, not the viewport:
      // using viewport coordinates makes the result depend on scroll position,
      // and since this only ever grows, the height then ratchets up and never
      // comes back down.
      const cardTop = cardBox.top - scroller.getBoundingClientRect().top + scroller.scrollTop;
      const chartInset = cardBox.height - el.getBoundingClientRect().height;
      return Math.floor(
        scroller.clientHeight - cardTop - chartInset - CHART_BOTTOM_GUTTER
      );
    },
    relayoutCharts() {
      ["summaryChart", "cyclesChart", "cellChart"].forEach((id) => {
        const el = document.getElementById(id);
        if (!el || !el.data) return;
        this._fitChartHeight(el);
        Plotly.Plots.resize(el);
      });
    },
  };
}
