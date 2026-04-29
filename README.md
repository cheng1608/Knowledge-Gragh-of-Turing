# Knowledge-Gragh-of-Turing

图灵（Alan Turing）主题知识图谱课程项目。

## Features

- Scheme：人物 / 机构 / 作品 / 概念 / 事件与地点
- 统一关系契约：`relations_final.csv` 支持 `confidence/evidence/source_url`
- 多阶段补边：Wikidata 子图补边 + 孤立节点补边 + 文本共现补边
- 质量闭环：图约束校验（`validation_report.csv`）
- 分析增强：子图导出、PageRank Top、建议边图层

## Project structure

```
.
├── LOG.md
├── README.md
├── ontology.md
├── neo4j.cypher
├── requirements.txt
├── .gitignore
├── scripts/
│   ├── ingestion/
│   │   ├── fetch_mactutor.py
│   │   └── fetch_turing_kg.py
│   ├── entity_processing/
│   │   ├── extract_entities.py
│   │   ├── clean_entities.py
│   │   ├── refine_entities.py
│   │   ├── align_to_schema.py
│   │   └── entity_linking.py
│   └── graph/
│       ├── build_graph_tables.py
│       ├── enrich_relations_wikidata.py
│       ├── enrich_isolated_nodes.py
│       ├── enrich_relations_text_cooccurrence.py
│       ├── relation_schema.py
│       ├── validate_graph.py
│       └── suggest_edges.py
└── data/
    ├── raw/
    │   ├── mactutor_turing.json
    │   └── mactutor_turing.txt
    ├── processed/
    │   ├── kg_seed/
    │   │   ├── nodes.csv
    │   │   └── relations.csv
    │   └── entities/
    │       ├── entities_raw.csv
    │       ├── entities_clean.csv
    │       ├── entities_refined.csv
    │       ├── entities_schema_aligned.csv
    │       ├── entities_linked.csv
    │       └── ...
    ├── final/
    │   ├── nodes_final.csv
    │   └── relations_final.csv
    └── compare/
```

## 如何运行项目

### 1) 环境准备

建议 Python 3.9+，在项目根目录执行：

```bash
pip install -r requirements.txt
```

### 2) 运行完整数据流水线（从采集到终表）

```bash
# 1) 结构化种子图（Wikidata）
python scripts/ingestion/fetch_turing_kg.py

# 2) 文本抓取（MacTutor）
python scripts/ingestion/fetch_mactutor.py

# 3) 实体处理
python scripts/entity_processing/extract_entities.py
python scripts/entity_processing/clean_entities.py
python scripts/entity_processing/refine_entities.py
python scripts/entity_processing/align_to_schema.py
python scripts/entity_processing/entity_linking.py

# 4) 构建终表（可选 Wikidata 补边）
python scripts/graph/build_graph_tables.py
# 或
python scripts/graph/build_graph_tables.py --enrich-wikidata
# 或（推荐，自动做多阶段补边，图更稠密）
python scripts/graph/build_graph_tables.py --enrich-all
```

运行完成后，核心输出为：
- `data/final/nodes_final.csv`
- `data/final/relations_final.csv`

### 3) 只启动前端查看效果（已有终表时）

如果你已经有 `data/final/nodes_final.csv` 与 `data/final/relations_final.csv`，可直接启动前端：

```bash
python -m http.server 8000
```

浏览器打开：`http://127.0.0.1:8000/frontend/index.html`

### 4) 常见问题

- 页面空白/加载失败：确认不是 `file://` 直接打开，而是通过本地 HTTP 服务访问。
- 关系较稀疏：优先使用 `python scripts/graph/build_graph_tables.py --enrich-all` 重建终表。
- 端口被占用：可改成 `python -m http.server 9000`，再访问 `http://127.0.0.1:9000/frontend/index.html`。

### 关系表字段说明（`data/final/relations_final.csv`）

- 基础字段：`start_id, relation, end_id, year, role, source`
- 增强字段：
  - `confidence`：关系置信度（0~1）
  - `evidence`：证据文本（如文本共现句子片段）
  - `source_url`：可点击来源链接

### 质量验证与评估

```bash
# 图约束校验：输出 data/compare/validation_report.csv
python scripts/graph/validate_graph.py
```

### 建议边生成（不并入终表）

```bash
python scripts/graph/suggest_edges.py
```

输出：`data/compare/relations_suggested.csv`

## Data source

- Wikidata SPARQL Endpoint：`https://query.wikidata.org/sparql`
- MacTutor 传记页面：`https://mathshistory.st-andrews.ac.uk/Biographies/Turing/`

## Frontend visualization

新增了一个轻量前端页面用于动态展示节点和关系：

- 页面路径：`frontend/index.html`
- 功能：
  - 动态力导向图展示
  - 点击节点查看详细信息与邻接关系
  - 点击边查看 `relation/year/role/source/confidence/evidence/source_url`
  - 按类型筛选（Person / Organization / Work / Concept / Place）
  - 按关键词搜索（节点名称 / QID）
  - 按最小关系置信度过滤
  - 导出当前筛选子图 CSV
  - 当前子图 PageRank Top
  - 建议边图层加载与开关（虚线显示）
  - 支持导入本地 `nodes.csv` 与 `relations.csv`

推荐用本地 HTTP 服务打开（避免 `file://` 读取 CSV 的限制）：

```bash
python -m http.server 8000
```

然后访问：`http://localhost:8000/frontend/index.html`

### Neo4j 导入（可选）

项目已在 `neo4j.cypher` 提供：
- CSV 导入示例（节点与关系）
- 常用查询示例（总量、1 跳邻居、2 跳路径）

