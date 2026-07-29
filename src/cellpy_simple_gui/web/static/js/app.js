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
    tab: "summary",
    project: null,
    projects: [],
    openTarget: "",
    saveName: "",
    showImport: false,
    instruments: [],
    rawExamples: [],
    ingest: {
      instrument: "", model: "", mass: "", area: "",
      nominal_capacity: "", nom_cap_specifics: "", cycle_mode: "", paths: "",
    },
    job: { active: false, progress: 0, message: "", error: "" },
    summary: {
      basis: "gravimetric", show_charge: true, show_discharge: true,
      show_efficiency: false, group_average: false, spread: false, max_cycle: "",
    },
    cell: { cell_id: "", from: 1, to: 10, maxCurves: 8, min: 1, max: 1,
            mode: "gravimetric", method: "forth-and-forth" },
    exportFormats: ["csv", "xlsx", "parquet", "json"],
    exportOpen: false,
    exportCellOpen: false,

    // ---- lifecycle ----
    async init() {
      try {
        this.examples = await (await api("/api/examples")).json();
      } catch (_) {}
      await this.refreshInstruments();
      await this.refreshProjects();
      await this.refreshState();
      this.$watch("theme", (v) => this.relayoutCharts());
    },

    get nSelected() { return this.cells.filter((c) => c.selected).length; },
    get nGroups() { return new Set(this.cells.map((c) => c.group)).size; },

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
      await this.refreshProjects();
    },
    async openProject() {
      if (!this.openTarget) return;
      await this.runJob("/api/projects/open", { target: this.openTarget });
      await this.refreshProjects();
    },

    // ---- loading (jobs + SSE) ----
    async loadExamples() {
      const kinds = this.examples.length ? this.examples.map((e) => e.id) : ["cellpy", "old_cellpy", "rate"];
      await this.runJob("/api/load/example", { kinds });
    },
    async loadFiles() {
      const paths = this.filesPath.split(";").map((s) => s.trim()).filter(Boolean);
      if (!paths.length) return;
      await this.runJob("/api/load/files", { paths });
      this.filesPath = "";
    },

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
            if (s.status === "error") this.job.error = s.message;
            if (s.result && s.result.errors && s.result.errors.length) {
              this.job.error = s.result.errors.join(" · ");
            }
            this.refreshState();
            resolve();
          }
        };
        es.onerror = () => { es.close(); this.job.active = false; this.refreshState(); resolve(); };
      });
    },

    // ---- editing ----
    async updateCell(id, patch) {
      const r = await (await api(`/api/cells/${id}/update`, { method: "POST", body: { id, ...patch } })).json();
      this.cells = r.state.cells;
      if (this.tab === "summary") this.plotSummary();
    },
    async selectAll(v) {
      const s = await (await api(`/api/cells/select?value=${v}`, { method: "POST" })).json();
      this.cells = s.cells; this.plotSummary();
    },
    async removeCell(id) {
      const s = await (await api(`/api/cells/${id}`, { method: "DELETE" })).json();
      this.cells = s.cells;
      if (this.cell.cell_id === id) this.cell.cell_id = "";
      this.plotSummary();
    },
    async clearAll() {
      const s = await (await api("/api/cells/clear", { method: "POST" })).json();
      this.cells = s.cells; this.cell.cell_id = ""; this.project = s.project;
      Plotly.purge("summaryChart"); Plotly.purge("cellChart");
      this.plotSummary();
    },

    // ---- summary plot ----
    summarySpec() {
      return {
        basis: this.summary.basis,
        show_charge: this.summary.show_charge,
        show_discharge: this.summary.show_discharge,
        show_efficiency: this.summary.show_efficiency,
        group_average: this.summary.group_average,
        spread: this.summary.group_average,
        max_cycle: this._num(this.summary.max_cycle),
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

    // ---- exports (csv / xlsx / parquet / json) ----
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
        const blob = await res.blob();
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob); a.download = filename; a.click();
        URL.revokeObjectURL(a.href);
      } catch (e) { this.job.error = e.message; }
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
