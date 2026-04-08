# Knowledge-Gragh-of-Turing

图灵（Alan Turing）主题知识图谱课程项目

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
│   ├── align_to_schema.py
│   ├── build_graph_tables.py
│   ├── clean_entities.py
│   ├── entity_linking.py
│   ├── extract_entities.py
│   ├── fetch_mactutor.py
│   ├── fetch_turing_kg.py
│   └── refine_entities.py
├── data/
│   ├── compare/                 # 是否使用 spaCy 的抽取对比
│   │   ├── no_spacy/
│   │   └── with_spacy/
│   ├── final/                   # 对齐本体后的图数据表
│   │   ├── nodes_final.csv
│   │   └── relations_final.csv
│   ├── processed/               # Wikidata 子图、实体清洗/链接等中间结果
│   │   ├── nodes.csv
│   │   ├── relations.csv
│   │   └── …                    # 其余 entities_*.csv、date_mentions.csv 等
│   └── raw/                     # MacTutor 抓取结果
│       ├── mactutor_turing.json
│       └── mactutor_turing.txt
└── .vscode/                     # 可选：编辑器设置（若纳入版本库）
    └── settings.json
```

## Quickstart

安装依赖：

```bash
pip install -r requirements.txt
```

None

## Data source

- Wikidata SPARQL Endpoint：`https://query.wikidata.org/sparql`
- MacTutor 传记页面：`https://mathshistory.st-andrews.ac.uk/Biographies/Turing/`

