/* cellpy simple gui — front-end logic (Alpine component) */

const TOKEN = document.querySelector('meta[name="csg-token"]').content;

async function api(path, { method = "GET", body = null } = {}) {
  const opts = {
    method,
    headers: { "X-CSG-Token": TOKEN },
    credentials: "same-origin",
  };
  if (body !== null) {
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

function app() {
  return {
    theme: localStorage.getItem("csg-theme") || "dark",
    figureThemePref: localStorage.getItem("csg-figure-theme") || "match",
    colorScheme: localStorage.getItem("csg-color-scheme") || "cellpy",
    cells: [],
    examples: [],
    filesPath: "",
    filesMax: 10,
    journalPath: "",
    canPick: false,
    devMode: false,
    maxFilesCeiling: 10, // server-enforced ceiling; higher in dev mode (#97)
    tab: "summary",
    project: null,
    projects: [],
    openTarget: "",
    saveName: "",
    dirty: false,
    showDemo: false,
    showLoadFiles: false,
    showImport: false,
    instruments: [],
    rawExamples: [],
    ingest: {
      instrument: "", model: "", mass: "", area: "",
      nominal_capacity: "", nom_cap_specifics: "", cycle_mode: "", paths: "", maxFiles: 10,
    },
    job: { active: false, id: "", progress: 0, message: "", error: "" },
    _jobEs: null,
    plotBusy: { summary: false, cycles: false, cell: false },
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
    },
    cycles: {
      layout: "per_cycle", from: 1, to: 10, maxCurves: 8, min: 1, max: 1,
      mode: "gravimetric", method: "forth-and-forth",
      group_legend_muting: true,
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
      } catch (_) { this.canPick = false; }
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
    get cellPlotKindLabel() {
      return {
        dqdv: "dQ/dV", dvdq: "dV/dQ", raw: "Raw", cycleinfo: "Raw + steps",
      }[this.cell.plotKind] || "Curves";
    },
    get cellAxisLabels() {
      if (this.cell.plotKind === "dqdv") return { x: "Voltage x", y: "dQ/dV y" };
      if (this.cell.plotKind === "dvdq") return { x: "Capacity x", y: "dV/dQ y" };
      if (this.cell.plotKind === "raw") return { x: "Time x", y: "Value y" };
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
      const paths = this.filesPath.split(";").map((s) => s.trim()).filter(Boolean);
      if (!paths.length) return;
      await this.runJob("/api/load/files", { paths, max_files: this._num(this.filesMax) || 10 });
      this.filesPath = "";
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
    pickCellpy() { this.pick("cellpy", (p) => { this.filesPath = p.join("; "); }); },
    pickRaw() { this.pick("raw", (p) => { this.ingest.paths = p.join("; "); }); },
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
    currentModels() {
      const ins = this.instruments.find((i) => i.id === this.ingest.instrument);
      return ins ? ins.models : [];
    },
    _num(v) {
      const n = parseFloat(v);
      return Number.isFinite(n) ? n : null;
    },
    async ingestRaw() {
      const paths = this.ingest.paths.split(";").map((s) => s.trim()).filter(Boolean);
      if (!paths.length) return;
      const body = {
        paths,
        max_files: this._num(this.ingest.maxFiles) || 10,
        instrument: this.ingest.instrument,
        model: this.ingest.model || null,
        mass: this._num(this.ingest.mass),
        area: this._num(this.ingest.area),
        nominal_capacity: this._num(this.ingest.nominal_capacity),
        nom_cap_specifics: this.ingest.nom_cap_specifics || null,
        cycle_mode: this.ingest.cycle_mode || null,
      };
      await this.runJob("/api/ingest", body);
      this.ingest.paths = "";
    },
    async ingestExample(kind) {
      await this.runJob("/api/ingest/example", { kind, mass: this._num(this.ingest.mass) });
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
      // load / ingest jobs report {added:[...], errors:[...], matched?, note?}
      if ("added" in r) {
        const n = (r.added || []).length;
        const errs = r.errors || [];
        const notes = r.notes || [];
        if (n > 0 && errs.length) this.notify("warn", `Loaded ${n} cell${n > 1 ? "s" : ""}; ${errs.length} problem${errs.length > 1 ? "s" : ""}: ${errs.join(" · ")}`);
        else if (n > 0) this.notify("ok", `Loaded ${n} cell${n > 1 ? "s" : ""}.`);
        else if (errs.length) this.notify("error", errs.join(" · "));
        else this.notify("warn", "Nothing was loaded — no files matched.");
        if (notes.length) this.notify("warn", notes.join(" · "));
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
      this.$nextTick(() => this.$refs.cellsManagerFilter?.focus());
    },
    closeCellsManager() {
      this.cellsManagerOpen = false;
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
      if (plot) this.replotCurrent();
    },
    async selectAll(v) {
      const s = await (await api(`/api/cells/select?value=${v}`, { method: "POST" })).json();
      this.cells = s.cells;
      this.markDirty();
      this.replotCurrent();
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
      this.replotCurrent();
    },
    async removeCell(id) {
      const s = await (await api(`/api/cells/${id}`, { method: "DELETE" })).json();
      this.cells = s.cells;
      this.markDirty();
      if (this.cell.cell_id === id) this.cell.cell_id = "";
      this.replotCurrent();
    },
    async clearAll() {
      const s = await (await api("/api/cells/clear", { method: "POST" })).json();
      this.cells = s.cells; this.cell.cell_id = ""; this.project = s.project;
      this.dirty = false;
      this.cellsManagerOpen = false;
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
      this.plotBusy[kind] = true;
      try {
        await fn();
      } catch (e) {
        console.error(e);
      } finally {
        this.plotBusy[kind] = false;
      }
    },
    async plotSummary() {
      await this._withPlotBusy("summary", async () => {
        const fig = await (await api("/api/plots/summary", { method: "POST", body: this.summarySpec() })).json();
        Plotly.react("summaryChart", fig.data, fig.layout, PLOTLY_CONFIG);
        this._applyFigureHeight("summaryChart", fig);
        requestAnimationFrame(() => this.relayoutCharts());
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
      const fig = await (await api("/api/plots/cycles", { method: "POST", body: this.cyclesSpec() })).json();
      Plotly.react("cyclesChart", fig.data, fig.layout, PLOTLY_CONFIG);
      this._applyFigureHeight("cyclesChart", fig);
      requestAnimationFrame(() => this.relayoutCharts());
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
        await this._plotCellFigure();
      });
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
        max_points: this._num(this.cell.maxPoints) || 4000,
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
    async _plotCellFigure() {
      if (!this.cell.cell_id) return;
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
      const fig = await (await api(url, { method: "POST", body })).json();
      Plotly.react("cellChart", fig.data, fig.layout, PLOTLY_CONFIG);
      this._applyFigureHeight("cellChart", fig);
      requestAnimationFrame(() => this.relayoutCharts());
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
      // Keep the Plotly div at the figure's layout height so Plots.resize only
      // adjusts width and does not squash the last facet / x-axis (#63).
      const el = document.getElementById(id);
      const h = fig && fig.layout && fig.layout.height;
      if (el && h) el.style.height = `${h}px`;
    },
    relayoutCharts() {
      ["summaryChart", "cyclesChart", "cellChart"].forEach((id) => {
        const el = document.getElementById(id);
        if (el && el.data) Plotly.Plots.resize(el);
      });
    },
  };
}
