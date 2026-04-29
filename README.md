# Knowledge-Gragh-of-Turing

图灵（Alan Turing）主题知识图谱课程项目。

## Features

- Scheme：人物 / 机构 / 作品 / 概念 / 事件与地点
- 多阶段补边：Wikidata 子图补边 + 孤立节点补边 + 文本补边
- 分析增强：子图导出、PageRank Top、建议边图层

## 项目结构

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

## 运行项目

### 1) 环境

建议 Python 3.9+，在项目根目录执行：

```bash
pip install -r requirements.txt
```

### 2) 运行数据流水线

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

### 3) 前端查看效果

 生成了`data/final/nodes_final.csv` 与 `data/final/relations_final.csv`以后，可直接启动前端：

```bash
python -m http.server 8000
```

浏览器打开：`http://127.0.0.1:8000/frontend/index.html`

### 关系表字段说明（`data/final/relations_final.csv`）

- 基础字段：`start_id, relation, end_id, year, role, source`
- 增强字段：
  - `confidence`：关系置信度（0~1）
  - `evidence`：证据文本（如文本共现句子片段）
  - `source_url`：可点击来源链接


### 建议边(后期补充关系)

```bash
python scripts/graph/suggest_edges.py
```

输出：`data/compare/relations_suggested.csv`

## 数据来源

- Wikidata SPARQL Endpoint：`https://query.wikidata.org/sparql`
- MacTutor 传记页面：`https://mathshistory.st-andrews.ac.uk/Biographies/Turing/`



