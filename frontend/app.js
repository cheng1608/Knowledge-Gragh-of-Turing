const TYPE_COLORS = {
  Person: "#5b8ff9",
  Organization: "#5ad8a6",
  Work: "#f6bd16",
  Concept: "#9270ca",
  Place: "#f6903d",
  Event: "#6dc8ec",
};

let allNodes = [];
let allEdges = [];
let network = null;
let visNodes = null;
let visEdges = null;

const networkEl = document.getElementById("network");
const statsEl = document.getElementById("stats");
const detailEl = document.getElementById("nodeDetail");
const neighborsEl = document.getElementById("neighborsList");
const searchInput = document.getElementById("searchInput");
const typeFiltersEl = document.getElementById("typeFilters");
const loadDefaultBtn = document.getElementById("loadDefaultBtn");
const resetBtn = document.getElementById("resetBtn");
const fitBtn = document.getElementById("fitBtn");
const importBtn = document.getElementById("importBtn");
const nodesFileInput = document.getElementById("nodesFile");
const relationsFileInput = document.getElementById("relationsFile");

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

function normalizeEdges(rawEdges, nodeIdSet) {
  return rawEdges
    .filter((e) => e.start_id && e.end_id)
    .filter((e) => nodeIdSet.has(e.start_id.trim()) && nodeIdSet.has(e.end_id.trim()))
    .map((e, idx) => ({
      id: `e-${idx}-${e.start_id}-${e.end_id}`,
      from: e.start_id.trim(),
      to: e.end_id.trim(),
      label: (e.relation || "").trim(),
      relation: (e.relation || "").trim(),
      confidence: Number(e.confidence || 0),
      arrows: "to",
      font: { align: "top", size: 11 },
      color: { color: "#98a2b3", opacity: 0.7 },
      width: 1.2,
    }));
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

  const keyword = searchInput.value.trim().toLowerCase();
  const selectedTypes = getSelectedTypes();

  const filteredNodes = allNodes.filter((n) => {
    const inType = selectedTypes.size === 0 ? true : selectedTypes.has(n.category);
    const inKeyword =
      keyword.length === 0 ||
      n.name.toLowerCase().includes(keyword) ||
      n.id.toLowerCase().includes(keyword);
    return inType && inKeyword;
  });
  const idSet = new Set(filteredNodes.map((n) => n.id));

  const filteredEdges = allEdges.filter((e) => idSet.has(e.from) && idSet.has(e.to));

  visNodes.clear();
  visEdges.clear();
  visNodes.add(filteredNodes);
  visEdges.add(filteredEdges);

  updateStats(filteredNodes.length, filteredEdges.length);
}

function updateStats(nodeCount, edgeCount) {
  statsEl.textContent = `节点: ${nodeCount} | 关系: ${edgeCount}`;
}

function clearDetail() {
  detailEl.textContent = "点击图中的节点查看详情";
  neighborsEl.innerHTML = "";
}

function showNodeDetail(nodeId) {
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

  const connected = new Set();
  allEdges.forEach((e) => {
    if (e.from === nodeId) {
      connected.add(e.to);
    }
    if (e.to === nodeId) {
      connected.add(e.from);
    }
  });

  const connectedNodes = [...connected]
    .map((id) => allNodes.find((n) => n.id === id))
    .filter(Boolean)
    .sort((a, b) => a.name.localeCompare(b.name));

  neighborsEl.innerHTML = connectedNodes.length
    ? connectedNodes.map((n) => `<li>${n.name} (${n.category})</li>`).join("")
    : "<li>无邻接节点</li>";
}

function initNetwork() {
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
    if (params.nodes.length === 0) {
      clearDetail();
      return;
    }
    showNodeDetail(params.nodes[0]);
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

function setGraphData(rawNodes, rawEdges) {
  allNodes = normalizeNodes(rawNodes);
  const nodeIds = new Set(allNodes.map((n) => n.id));
  allEdges = normalizeEdges(rawEdges, nodeIds);
  renderTypeFilters();
  clearDetail();
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

resetBtn.addEventListener("click", () => {
  searchInput.value = "";
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

loadDefaultData().catch(() => {
  // 如果直接用 file:// 打开页面会触发跨域，交给用户手动导入 CSV。
});
