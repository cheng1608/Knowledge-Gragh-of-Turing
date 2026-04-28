const TYPE_COLORS = {
  Person: "#5b8ff9",
  Organization: "#5ad8a6",
  Work: "#f6bd16",
  Concept: "#9270ca",
  Place: "#f6903d",
  Event: "#6dc8ec",
};

let allNodes = [];
/** Canonical graph edges (no suggestions). */
let baseEdges = [];
/** Optional suggested edges (dashed). */
let suggestedEdges = [];
/** Rendered union; includes suggestions when enabled. */
let allEdges = [];
let network = null;
let visNodes = null;
let visEdges = null;
let showSuggested = false;

const networkEl = document.getElementById("network");
const statsEl = document.getElementById("stats");
const detailEl = document.getElementById("nodeDetail");
const edgeDetailEl = document.getElementById("edgeDetail");
const neighborsEl = document.getElementById("neighborsList");
const searchInput = document.getElementById("searchInput");
const typeFiltersEl = document.getElementById("typeFilters");
const loadDefaultBtn = document.getElementById("loadDefaultBtn");
const resetBtn = document.getElementById("resetBtn");
const fitBtn = document.getElementById("fitBtn");
const importBtn = document.getElementById("importBtn");
const nodesFileInput = document.getElementById("nodesFile");
const relationsFileInput = document.getElementById("relationsFile");
const pathFromInput = document.getElementById("pathFromInput");
const pathToInput = document.getElementById("pathToInput");
const pathBtn = document.getElementById("pathBtn");
const pathResultEl = document.getElementById("pathResult");
const exportBtn = document.getElementById("exportBtn");
const pagerankBtn = document.getElementById("pagerankBtn");
const pagerankResultEl = document.getElementById("pagerankResult");
const minConfidenceInput = document.getElementById("minConfidenceInput");
const loadSuggestedBtn = document.getElementById("loadSuggestedBtn");
const toggleSuggestedEl = document.getElementById("toggleSuggested");
const suggestedFileInput = document.getElementById("suggestedFile");

function parseCsvText(csvText) {
  const result = Papa.parse(csvText, {
    header: true,
    skipEmptyLines: true,
    dynamicTyping: false,
  });
  if (result.errors && result.errors.length > 0) {
    throw new Error(`CSV 解析失败: ${result.errors[0].message}`);
  }
  return result.data;
}

function normalizeNodes(rawNodes) {
  return rawNodes
    .filter((n) => n.id && n.name)
    .map((n) => ({
      id: n.id.trim(),
      label: n.name.trim(),
      name: n.name.trim(),
      category: (n.label || "Unknown").trim(),
      source: (n.source || "").trim(),
      confidence: Number(n.confidence || 0),
      description: (n.wikidata_description || "").trim(),
      color: TYPE_COLORS[(n.label || "").trim()] || "#9aa4b2",
    }));
}

function normalizeEdges(rawEdges, nodeIdSet, options = {}) {
  const { isSuggested = false } = options;
  return rawEdges
    .filter((e) => e.start_id && e.end_id)
    .filter((e) => nodeIdSet.has(e.start_id.trim()) && nodeIdSet.has(e.end_id.trim()))
    .map((e, idx) => {
      const conf = Number(e.confidence || 0);
      const baseColor = isSuggested ? "#f97316" : "#98a2b3";
      const baseWidth = isSuggested ? 1 : 1.2;
      return {
        id: `e-${isSuggested ? "s" : "c"}-${idx}-${e.start_id}-${e.end_id}-${(e.relation || "").slice(0, 24)}`,
        from: e.start_id.trim(),
        to: e.end_id.trim(),
        label: (e.relation || "").trim(),
        relation: (e.relation || "").trim(),
        year: (e.year || "").trim(),
        role: (e.role || "").trim(),
        source: (e.source || "").trim(),
        sourceUrl: (e.source_url || "").trim(),
        evidence: (e.evidence || "").trim(),
        confidence: conf,
        isSuggested,
        arrows: "to",
        font: { align: "top", size: 11 },
        dashes: isSuggested,
        color: { color: baseColor, opacity: isSuggested ? 0.85 : 0.7 },
        width: baseWidth,
        baseColor,
        baseWidth,
      };
    });
}

function recomputeAllEdges() {
  allEdges = showSuggested ? [...baseEdges, ...suggestedEdges] : [...baseEdges];
}

function getMinConfidence() {
  const v = Number(minConfidenceInput?.value ?? 0);
  return Number.isFinite(v) ? v : 0;
}

function getFilteredGraph() {
  const keyword = searchInput.value.trim().toLowerCase();
  const selectedTypes = getSelectedTypes();
  const minC = getMinConfidence();

  const filteredNodes = allNodes.filter((n) => {
    const inType = selectedTypes.size === 0 ? true : selectedTypes.has(n.category);
    const inKeyword =
      keyword.length === 0 ||
      n.name.toLowerCase().includes(keyword) ||
      n.id.toLowerCase().includes(keyword);
    return inType && inKeyword;
  });
  const idSet = new Set(filteredNodes.map((n) => n.id));

  const filteredEdges = allEdges.filter(
    (e) =>
      idSet.has(e.from) &&
      idSet.has(e.to) &&
      (Number.isNaN(e.confidence) ? true : e.confidence >= minC)
  );

  return { filteredNodes, filteredEdges, idSet };
}

function renderTypeFilters() {
  const categories = [...new Set(allNodes.map((n) => n.category))].sort();
  const html = categories
    .map(
      (cat) =>
        `<label><input type="checkbox" class="type-filter" value="${cat}" checked /> ${cat}</label>`
    )
    .join("");
  typeFiltersEl.innerHTML = html || "<span>暂无可筛选类型</span>";

  typeFiltersEl.querySelectorAll(".type-filter").forEach((checkbox) => {
    checkbox.addEventListener("change", applyFilters);
  });
}

function getSelectedTypes() {
  const checked = [...typeFiltersEl.querySelectorAll(".type-filter:checked")];
  return new Set(checked.map((c) => c.value));
}

function applyFilters() {
  if (!visNodes || !visEdges) {
    return;
  }

  const { filteredNodes, filteredEdges } = getFilteredGraph();

  visNodes.clear();
  visEdges.clear();
  visNodes.add(filteredNodes);
  visEdges.add(filteredEdges);

  updateStats(filteredNodes.length, filteredEdges.length);
}

function updateStats(nodeCount, edgeCount) {
  const sug = suggestedEdges.length;
  const extra = showSuggested && sug ? ` | 建议边: ${sug}` : "";
  statsEl.textContent = `节点: ${nodeCount} | 关系: ${edgeCount}${extra}`;
}

function clearDetail() {
  detailEl.textContent = "点击图中的节点或连线查看详情";
  edgeDetailEl.textContent = "点击一条有向边查看 source / confidence / 证据";
  edgeDetailEl.classList.add("muted");
  neighborsEl.innerHTML = "";
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function showEdgeDetail(edge) {
  if (!edge) {
    return;
  }
  detailEl.textContent = "（当前选中关系，见下方「关系详情」）";
  edgeDetailEl.classList.remove("muted");
  const urlLine = edge.sourceUrl
    ? `source_url: ${edge.sourceUrl}`
    : "source_url: -";
  edgeDetailEl.textContent = [
    `${edge.from} -[${edge.relation}]-> ${edge.to}`,
    `year: ${edge.year || "-"}`,
    `role: ${edge.role || "-"}`,
    `source: ${edge.source || "-"}`,
    `confidence: ${Number.isNaN(edge.confidence) ? "-" : edge.confidence}`,
    `suggested: ${edge.isSuggested ? "yes" : "no"}`,
    urlLine,
    `evidence: ${edge.evidence || "-"}`,
  ].join("\n");
}

function showNodeDetail(nodeId) {
  edgeDetailEl.classList.add("muted");
  edgeDetailEl.textContent = "点击一条有向边查看 source / confidence / 证据";

  const node = allNodes.find((n) => n.id === nodeId);
  if (!node) {
    clearDetail();
    return;
  }

  detailEl.textContent = [
    `name: ${node.name}`,
    `id: ${node.id}`,
    `label: ${node.category}`,
    `source: ${node.source || "-"}`,
    `confidence: ${Number.isNaN(node.confidence) ? "-" : node.confidence}`,
    `description: ${node.description || "-"}`,
  ].join("\n");

  const incident = allEdges.filter((e) => e.from === nodeId || e.to === nodeId);
  if (!incident.length) {
    neighborsEl.innerHTML = "<li>无邻接边</li>";
    return;
  }

  const lines = incident
    .map((e) => {
      const other = e.from === nodeId ? e.to : e.from;
      const on = allNodes.find((n) => n.id === other);
      const oname = on ? on.name : other;
      const dir = e.from === nodeId ? "→" : "←";
      const meta = [
        e.relation,
        e.year ? `y=${e.year}` : "",
        Number.isNaN(e.confidence) ? "" : `c=${e.confidence}`,
      ]
        .filter(Boolean)
        .join(" ");
      return `<li><code>${escapeHtml(meta)}</code> ${dir} ${escapeHtml(oname)} <small>(${escapeHtml(other)})</small></li>`;
    })
    .join("");
  neighborsEl.innerHTML = lines;
}

function buildUndirectedAdj(edges) {
  const adj = new Map();
  for (const e of edges) {
    if (!adj.has(e.from)) adj.set(e.from, new Set());
    if (!adj.has(e.to)) adj.set(e.to, new Set());
    adj.get(e.from).add(e.to);
    adj.get(e.to).add(e.from);
  }
  return adj;
}

function shortestPathNodes(adj, fromId, toId) {
  if (fromId === toId) {
    return [fromId];
  }
  const q = [fromId];
  const prev = new Map([[fromId, null]]);
  while (q.length) {
    const u = q.shift();
    if (u === toId) {
      break;
    }
    const nbrs = adj.get(u);
    if (!nbrs) {
      continue;
    }
    for (const v of nbrs) {
      if (!prev.has(v)) {
        prev.set(v, u);
        q.push(v);
      }
    }
  }
  if (!prev.has(toId)) {
    return null;
  }
  const path = [];
  let cur = toId;
  while (cur != null) {
    path.push(cur);
    cur = prev.get(cur);
  }
  path.reverse();
  return path;
}

function findEdgeBetween(a, b, edges) {
  return (
    edges.find((e) => e.from === a && e.to === b) ||
    edges.find((e) => e.from === b && e.to === a)
  );
}

function runPathQuery() {
  const fromQ = (pathFromInput.value || "").trim();
  const toQ = (pathToInput.value || "").trim();
  if (!fromQ || !toQ) {
    pathResultEl.textContent = "请填写起点与终点（name 或 id）。";
    return;
  }
  const resolve = (q) => {
    const low = q.toLowerCase();
    return (
      allNodes.find((n) => n.id === q) ||
      allNodes.find((n) => n.name.toLowerCase() === low) ||
      allNodes.find((n) => n.name.toLowerCase().includes(low))
    );
  };
  const a = resolve(fromQ);
  const b = resolve(toQ);
  if (!a || !b) {
    pathResultEl.textContent = "未找到起点或终点节点。";
    return;
  }
  const adj = buildUndirectedAdj(baseEdges);
  const path = shortestPathNodes(adj, a.id, b.id);
  if (!path) {
    pathResultEl.textContent = `在结构化边（不含建议边）上无路径: ${a.name} ↔ ${b.name}`;
    return;
  }
  const hops = [];
  for (let i = 0; i < path.length - 1; i++) {
    const e = findEdgeBetween(path[i], path[i + 1], baseEdges);
    const lbl = e ? e.relation : "?";
    hops.push(`${path[i]} -[${lbl}]-> ${path[i + 1]}`);
  }
  pathResultEl.textContent = [
    `长度 ${path.length - 1}（节点序列）`,
    path.map((id) => allNodes.find((n) => n.id === id)?.name || id).join(" → "),
    "",
    ...hops,
  ].join("\n");
}

function toCsvRow(cells) {
  return cells.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(",");
}

function exportFilteredCsv() {
  const { filteredNodes, filteredEdges } = getFilteredGraph();
  const nodeHeader = ["id", "label", "name", "source", "confidence", "wikidata_description"];
  const nodeLines = [
    toCsvRow(nodeHeader),
    ...filteredNodes.map((n) =>
      toCsvRow([n.id, n.category, n.name, n.source, n.confidence, n.description])
    ),
  ];
  const relHeader = [
    "start_id",
    "relation",
    "end_id",
    "year",
    "role",
    "source",
    "confidence",
    "evidence",
    "source_url",
  ];
  const relLines = [
    toCsvRow(relHeader),
    ...filteredEdges.map((e) =>
      toCsvRow([
        e.from,
        e.relation,
        e.to,
        e.year,
        e.role,
        e.source,
        e.confidence,
        e.evidence,
        e.sourceUrl,
      ])
    ),
  ];
  const blob = new Blob([nodeLines.join("\n") + "\n\n" + relLines.join("\n")], {
    type: "text/csv;charset=utf-8",
  });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "turing_kg_subgraph_export.csv";
  a.click();
  URL.revokeObjectURL(a.href);
}

function pageRankFiltered() {
  const { filteredNodes, filteredEdges } = getFilteredGraph();
  const ids = filteredNodes.map((n) => n.id);
  const N = ids.length;
  if (!N) {
    pagerankResultEl.textContent = "无节点。";
    return;
  }
  const idSet = new Set(ids);
  const out = new Map();
  for (const id of ids) {
    out.set(id, []);
  }
  for (const e of filteredEdges) {
    if (idSet.has(e.from) && idSet.has(e.to)) {
      out.get(e.from).push(e.to);
    }
  }
  let ranks = new Map(ids.map((id) => [id, 1 / N]));
  const iters = 36;
  const d = 0.85;
  for (let i = 0; i < iters; i++) {
    const next = new Map(ids.map((id) => [id, (1 - d) / N]));
    for (const u of ids) {
      const outs = out.get(u) || [];
      const mass = d * (ranks.get(u) || 0);
      if (!outs.length) {
        const give = mass / N;
        for (const v of ids) {
          next.set(v, next.get(v) + give);
        }
      } else {
        const give = mass / outs.length;
        for (const v of outs) {
          next.set(v, next.get(v) + give);
        }
      }
    }
    ranks = next;
  }
  const ranked = [...ranks.entries()].sort((x, y) => y[1] - x[1]).slice(0, 12);
  pagerankResultEl.textContent = ranked
    .map(([id, r]) => {
      const n = allNodes.find((x) => x.id === id);
      return `${n ? n.name : id}: ${r.toFixed(4)}`;
    })
    .join("\n");
}

function initNetwork() {
  recomputeAllEdges();
  visNodes = new vis.DataSet(allNodes);
  visEdges = new vis.DataSet(allEdges);

  const data = { nodes: visNodes, edges: visEdges };
  const options = {
    interaction: {
      hover: true,
      multiselect: false,
      navigationButtons: true,
      keyboard: true,
    },
    nodes: {
      shape: "dot",
      size: 16,
      borderWidth: 1,
      font: { size: 13, color: "#1f2937" },
    },
    physics: {
      stabilization: true,
      barnesHut: {
        gravitationalConstant: -2500,
        springLength: 120,
        springConstant: 0.04,
      },
    },
    edges: {
      smooth: {
        type: "dynamic",
      },
      arrows: {
        to: { enabled: true, scaleFactor: 0.6 },
      },
    },
  };

  if (network) {
    network.destroy();
  }
  network = new vis.Network(networkEl, data, options);

  network.on("click", (params) => {
    if (params.edges.length > 0) {
      const eid = params.edges[0];
      const edge = visEdges.get(eid);
      showEdgeDetail(edge);
      return;
    }
    if (params.nodes.length > 0) {
      showNodeDetail(params.nodes[0]);
      return;
    }
    clearDetail();
  });

  network.once("stabilizationIterationsDone", () => {
    network.fit({ animation: true });
  });

  updateStats(allNodes.length, allEdges.length);
}

async function fetchCsv(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`读取失败: ${url}`);
  }
  return response.text();
}

async function loadDefaultData() {
  const [nodesCsv, edgesCsv] = await Promise.all([
    fetchCsv("../data/final/nodes_final.csv"),
    fetchCsv("../data/final/relations_final.csv"),
  ]);

  const parsedNodes = parseCsvText(nodesCsv);
  const parsedEdges = parseCsvText(edgesCsv);
  setGraphData(parsedNodes, parsedEdges);
}

function readFileAsText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("文件读取失败"));
    reader.readAsText(file, "utf-8");
  });
}

async function importFromLocalFiles() {
  const nodesFile = nodesFileInput.files[0];
  const relationsFile = relationsFileInput.files[0];
  if (!nodesFile || !relationsFile) {
    alert("请同时选择 nodes 与 relations 两个 CSV 文件。");
    return;
  }

  const [nodesCsv, edgesCsv] = await Promise.all([
    readFileAsText(nodesFile),
    readFileAsText(relationsFile),
  ]);
  const parsedNodes = parseCsvText(nodesCsv);
  const parsedEdges = parseCsvText(edgesCsv);
  setGraphData(parsedNodes, parsedEdges);
}

function setGraphData(rawNodes, rawEdges, suggestedRaw = null) {
  allNodes = normalizeNodes(rawNodes);
  suggestedEdges = [];
  showSuggested = false;
  const nodeIds = new Set(allNodes.map((n) => n.id));
  baseEdges = normalizeEdges(rawEdges, nodeIds, { isSuggested: false });
  let suggestedRows = null;
  if (Array.isArray(suggestedRaw)) {
    suggestedRows = suggestedRaw;
  } else if (typeof suggestedRaw === "string" && suggestedRaw.trim()) {
    suggestedRows = parseCsvText(suggestedRaw);
  }
  suggestedEdges = suggestedRows
    ? normalizeEdges(suggestedRows, nodeIds, { isSuggested: true })
    : [];
  if (suggestedEdges.length) {
    showSuggested = true;
  }
  if (toggleSuggestedEl) {
    toggleSuggestedEl.checked = showSuggested && suggestedEdges.length > 0;
  }
  recomputeAllEdges();
  renderTypeFilters();
  clearDetail();
  initNetwork();
  applyFilters();
}

async function loadSuggestedDefault() {
  try {
    const text = await fetchCsv("../data/compare/relations_suggested.csv");
    const rows = parseCsvText(text);
    const nodeIds = new Set(allNodes.map((n) => n.id));
    suggestedEdges = normalizeEdges(rows, nodeIds, { isSuggested: true });
    showSuggested = suggestedEdges.length > 0;
    if (toggleSuggestedEl) {
      toggleSuggestedEl.checked = showSuggested;
    }
    recomputeAllEdges();
    initNetwork();
    applyFilters();
  } catch (e) {
    alert(
      "未能加载 data/compare/relations_suggested.csv。请先运行 python scripts/graph/suggest_edges.py，或使用文件选择导入。"
    );
    console.error(e);
  }
}

async function importSuggestedFile() {
  const f = suggestedFileInput?.files?.[0];
  if (!f) {
    alert("请选择一个建议边 CSV。");
    return;
  }
  const text = await readFileAsText(f);
  const rows = parseCsvText(text);
  const nodeIds = new Set(allNodes.map((n) => n.id));
  suggestedEdges = normalizeEdges(rows, nodeIds, { isSuggested: true });
  showSuggested = true;
  if (toggleSuggestedEl) {
    toggleSuggestedEl.checked = true;
  }
  recomputeAllEdges();
  initNetwork();
  applyFilters();
}

loadDefaultBtn.addEventListener("click", async () => {
  try {
    await loadDefaultData();
  } catch (error) {
    alert(
      "默认数据加载失败，请确认你是通过本地服务器访问该页面，或改用下方本地 CSV 导入。"
    );
    console.error(error);
  }
});

searchInput.addEventListener("input", applyFilters);
if (minConfidenceInput) {
  minConfidenceInput.addEventListener("input", applyFilters);
}

resetBtn.addEventListener("click", () => {
  searchInput.value = "";
  if (minConfidenceInput) {
    minConfidenceInput.value = "0";
  }
  typeFiltersEl.querySelectorAll(".type-filter").forEach((el) => {
    el.checked = true;
  });
  applyFilters();
  clearDetail();
});

fitBtn.addEventListener("click", () => {
  if (network) {
    network.fit({ animation: true });
  }
});

importBtn.addEventListener("click", async () => {
  try {
    await importFromLocalFiles();
  } catch (error) {
    alert(`导入失败: ${error.message}`);
    console.error(error);
  }
});

if (pathBtn) {
  pathBtn.addEventListener("click", runPathQuery);
}
if (exportBtn) {
  exportBtn.addEventListener("click", exportFilteredCsv);
}
if (pagerankBtn) {
  pagerankBtn.addEventListener("click", pageRankFiltered);
}
if (loadSuggestedBtn) {
  loadSuggestedBtn.addEventListener("click", () => loadSuggestedDefault());
}
if (toggleSuggestedEl) {
  toggleSuggestedEl.addEventListener("change", () => {
    showSuggested = toggleSuggestedEl.checked;
    recomputeAllEdges();
    initNetwork();
    applyFilters();
  });
}
const importSuggestedBtn = document.getElementById("importSuggestedBtn");
if (importSuggestedBtn) {
  importSuggestedBtn.addEventListener("click", () => importSuggestedFile().catch((e) => alert(e.message)));
}

loadDefaultData().catch(() => {
  // 如果直接用 file:// 打开页面会触发跨域，交给用户手动导入 CSV。
});
