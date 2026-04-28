# Knowledge-Gragh-of-Turing

图灵（Alan Turing）主题知识图谱课程项目。

## Features

- Scheme：人物 / 机构 / 作品 / 概念 / 事件与地点

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
│       └── enrich_relations_wikidata.py
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

## Quickstart

安装依赖：

```bash
pip install -r requirements.txt
```

运行完整流程：

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

## Data source

- Wikidata SPARQL Endpoint：`https://query.wikidata.org/sparql`
- MacTutor 传记页面：`https://mathshistory.st-andrews.ac.uk/Biographies/Turing/`

## Frontend visualization

新增了一个轻量前端页面用于动态展示节点和关系：

- 页面路径：`frontend/index.html`
- 功能：
  - 动态力导向图展示
  - 点击节点查看详细信息与邻接节点
  - 按类型筛选（Person / Organization / Work / Concept / Place）
  - 按关键词搜索（节点名称 / QID）
  - 支持导入本地 `nodes.csv` 与 `relations.csv`

推荐用本地 HTTP 服务打开（避免 `file://` 读取 CSV 的限制）：

```bash
python -m http.server 8000
```

然后访问：`http://localhost:8000/frontend/index.html`

