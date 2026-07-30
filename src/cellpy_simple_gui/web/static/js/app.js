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
    cells: [],
    examples: [],
    filesPath: "",
    filesMax: 10,
    journalPath: "",
    canPick: false,
    tab: "summary",
    project: null,
    projects: [],
    openTarget: "",
    saveName: "",
    dirty: false,
    showImport: false,
    instruments: [],
    rawExamples: [],
    ingest: {
      instrument: "", model: "", mass: "", area: "",
      nominal_capacity: "", nom_cap_specifics: "", cycle_mode: "", paths: "", maxFiles: 10,
    },
    job: { active: false, progress: 0, message: "", error: "" },
    summary: {
      plot_type: "capacity_ce", basis: "gravimetric",
      group_average: false, spread: false, max_cycle: "",
      share_y: false,
    },
    plotTypes: [],
    cell: { cell_id: "", from: 1, to: 10, maxCurves: 8, min: 1, max: 1,
            mode: "gravimetric", method: "forth-and-forth" },
    exportFormats: ["csv", "xlsx", "parquet", "json"],
    figureFormats: ["png", "svg", "pdf"],
    exportOpen: false,
    exportCellOpen: false,
    notices: [],
    cellsManagerOpen: false,
    cellsManagerFilter: "",
    cellsManagerSort: "default",
    cellsManagerGroup: 1,

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
      this.$watch("theme", (v) => this.relayoutCharts());
      window.addEventListener("resize", () => this.relayoutCharts());
    },

    async refreshPlotTypes() {
      try {
        this.plotTypes = (await (await api("/api/plot-types")).json()).types;
      } catch (_) {}
    },
    currentPlotTypeBasis() {
      const t = this.plotTypes.find((t) => t.id === this.summary.plot_type);
      return t ? t.basis : true;
    },
    async probeCapabilities() {
      try {
        this.canPick = (await (await api("/api/system/capabilities")).json()).file_picker;
      } catch (_) { this.canPick = false; }
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
      if (this.tab === "summary") this.plotSummary();
      if (this.tab === "cell") this.ensureCellSelected();
    },

    async refreshProjects() {
      try {
        const r = await (await api("/api/projects")).json();
        this.projects = r.projects;
        this.project = r.current.name;
        if (this.project && !this.saveName) this.saveName = this.project;
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
    async loadJournal() {
      const path = this.journalPath.trim();
      if (!path) return;
      await this.runJob("/api/projects/load-journal", { path });
      this.journalPath = "";
      await this.refreshProjects();
    },

    // ---- native file pickers (desktop only) ----
    async pick(kind, assign) {
      try {
        const r = await (await api("/api/system/pick", { method: "POST", body: { kind } })).json();
        if (r.paths && r.paths.length) assign(r.paths);
      } catch (e) { this.notify("error", e.message); }
    },
    pickCellpy() { this.pick("cellpy", (p) => { this.filesPath = p.join("; "); }); },
    pickRaw() { this.pick("raw", (p) => { this.ingest.paths = p.join("; "); }); },
    pickJournal() { this.pick("journal", (p) => { this.journalPath = p[0]; this.loadJournal(); }); },

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
      this.job = { active: true, progress: 0, message: "Starting…", error: "" };
      let job_id;
      try {
        job_id = (await (await api(url, { method: "POST", body })).json()).job_id;
      } catch (e) {
        this.job = { active: false, progress: 0, message: "", error: e.message };
        this.notify("error", e.message || "Job failed to start.");
        return;
      }
      await this.streamJob(job_id);
    },
    streamJob(job_id) {
      return new Promise((resolve) => {
        const es = new EventSource(`/api/jobs/${job_id}/events?token=${encodeURIComponent(TOKEN)}`);
        es.onmessage = (ev) => {
          const s = JSON.parse(ev.data);
          this.job.progress = s.progress;
          this.job.message = s.message;
          if (["done", "error", "cancelled"].includes(s.status)) {
            es.close();
            this.job.active = false;
            this.job.error = "";
            if (s.status === "error") this.notify("error", s.message || "Job failed.");
            else this.reportJobResult(s.result);
            this.refreshState();
            resolve();
          }
        };
        es.onerror = () => {
          es.close(); this.job.active = false;
          this.notify("error", "Lost connection to the job.");
          this.refreshState(); resolve();
        };
      });
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
    notify(type, text) {
      const id = Date.now() + Math.random();
      this.notices.push({ id, type, text });
      setTimeout(() => { this.notices = this.notices.filter((n) => n.id !== id); }, type === "error" ? 9000 : 5000);
    },

    // ---- editing ----
    openCellsManager() {
      this.cellsManagerOpen = true;
      this.$nextTick(() => this.$refs.cellsManagerFilter?.focus());
    },
    closeCellsManager() {
      this.cellsManagerOpen = false;
    },
    async updateCell(id, patch, { plot = true } = {}) {
      const body = { id, ...patch };
      if ("mass" in patch && (patch.mass === null || patch.mass === undefined)) {
        delete body.mass; // library.update ignores non-positive / missing mass
      }
      const r = await (await api(`/api/cells/${id}/update`, { method: "POST", body })).json();
      this.cells = r.state.cells;
      this.markDirty();
      if (plot && this.tab === "summary") this.plotSummary();
    },
    async selectAll(v) {
      const s = await (await api(`/api/cells/select?value=${v}`, { method: "POST" })).json();
      this.cells = s.cells;
      this.markDirty();
      this.plotSummary();
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
      if (this.tab === "summary") this.plotSummary();
    },
    async removeCell(id) {
      const s = await (await api(`/api/cells/${id}`, { method: "DELETE" })).json();
      this.cells = s.cells;
      this.markDirty();
      if (this.cell.cell_id === id) this.cell.cell_id = "";
      this.plotSummary();
    },
    async clearAll() {
      const s = await (await api("/api/cells/clear", { method: "POST" })).json();
      this.cells = s.cells; this.cell.cell_id = ""; this.project = s.project;
      this.dirty = false;
      this.cellsManagerOpen = false;
      Plotly.purge("summaryChart"); Plotly.purge("cellChart");
      this.plotSummary();
    },

    // ---- summary plot ----
    summarySpec() {
      return {
        plot_type: this.summary.plot_type,
        basis: this.summary.basis,
        group_average: this.summary.group_average,
        spread: this.summary.spread,
        max_cycle: this._num(this.summary.max_cycle),
        share_y: !!this.summary.share_y,
        title: "Cycle summary",
      };
    },
    async plotSummary() {
      try {
        const fig = await (await api("/api/plots/summary", { method: "POST", body: this.summarySpec() })).json();
        Plotly.react("summaryChart", fig.data, fig.layout, PLOTLY_CONFIG);
      } catch (e) { console.error(e); }
    },

    // ---- cell explorer ----
    ensureCellSelected() {
      if (!this.cells.length) { Plotly.purge("cellChart"); return; }
      if (!this.cell.cell_id || !this.currentCell()) this.cell.cell_id = this.cells[0].id;
      this.onCellChange();
    },
    async onCellChange() {
      if (!this.cell.cell_id) return;
      const info = await (await api(`/api/cells/${this.cell.cell_id}/cycles`)).json();
      this.cell.min = info.min; this.cell.max = info.max;
      this.cell.from = info.min;
      this.cell.to = Math.min(info.max, info.min + 9);
      this.plotCell();
    },
    buildCycleList() {
      let { from, to, maxCurves } = this.cell;
      from = Math.max(this.cell.min, Math.min(from, this.cell.max));
      to = Math.max(from, Math.min(to, this.cell.max));
      const span = to - from + 1;
      const n = Math.max(1, Math.min(maxCurves, span));
      const step = (n === 1) ? 0 : (span - 1) / (n - 1);
      const out = new Set();
      for (let i = 0; i < n; i++) out.add(Math.round(from + i * step));
      return [...out].sort((a, b) => a - b);
    },
    cellSpec() {
      return {
        cell_id: this.cell.cell_id, cycles: this.buildCycleList(),
        mode: this.cell.mode, method: this.cell.method, title: "",
      };
    },
    async plotCell() {
      if (!this.cell.cell_id) return;
      try {
        const fig = await (await api("/api/plots/cycles", { method: "POST", body: this.cellSpec() })).json();
        Plotly.react("cellChart", fig.data, fig.layout, PLOTLY_CONFIG);
      } catch (e) { console.error(e); }
    },

    // ---- exports (data + static figures via kaleido) ----
    async exportSummary(fmt) {
      await this.download(`/api/export/summary?fmt=${fmt}`, this.summarySpec(), `summary.${fmt}`);
    },
    async exportCycles(fmt) {
      if (!this.cell.cell_id) return;
      await this.download(`/api/export/cycles?fmt=${fmt}`, this.cellSpec(), `cycles.${fmt}`);
    },
    async download(url, body, filename) {
      try {
        const res = await api(url, { method: "POST", body });
        const cd = res.headers.get("Content-Disposition") || "";
        const m = /filename\*?=(?:UTF-8''|")?([^\";]+)/i.exec(cd);
        const name = (m ? decodeURIComponent(m[1].replace(/"/g, "")) : filename) || filename;
        const blob = await res.blob();
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob); a.download = name; a.click();
        URL.revokeObjectURL(a.href);
        this.notify("ok", `Exported “${name}” to your downloads folder.`);
      } catch (e) {
        this.notify("error", `Export failed: ${e.message}`);
      }
    },

    // ---- misc ----
    toggleTheme() {
      this.theme = this.theme === "dark" ? "light" : "dark";
      localStorage.setItem("csg-theme", this.theme);
    },
    relayoutCharts() {
      ["summaryChart", "cellChart"].forEach((id) => {
        const el = document.getElementById(id);
        if (el && el.data) Plotly.Plots.resize(el);
      });
    },
  };
}
