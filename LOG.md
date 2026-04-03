## 1. 项目初始化

创建 `ontology.md`

设计Schema结构

## 2. 结构化数据采集

`scripts/fetch_turing_kg.py`

通过 SPARQL 访问 Wikidata 

图灵QID`Q7251`

输出到 `data/processed/nodes.csv`、`data/processed/relations.csv`

首次运行结果：
```
Nodes: 31
Relations: 29
```
## 3. 文本数据采集（MacTutor）

`scripts/fetch_mactutor.py`

MacTutor 图灵传记页面

先提取段落，若页面结构不规范，则启用后备提取逻辑（可见文本行过滤）

`data/raw/mactutor_turing.json`
`data/raw/mactutor_turing.txt`

## 4. 实体抽取

`scripts/extract_entities.py`

抽取策略：模型 + 规则混合

模型层：spaCy（`PERSON/ORG/GPE/DATE/WORK_OF_ART`）
规则层：词典与正则补充（`CONCEPT`、`CANDIDATE`）

输出
`data/processed/entities_raw.csv`
`data/processed/entities_summary.csv`

对比了使用 spaCy 与不使用模型两种抽取结果：无模型共 90 条，有模型共 161 条`data\compare`


## 5. 数据清洗
`scripts/clean_entities.py`

运行结果：
```
   - Input: 161
   - Clean: 80
   - Noise: 1
   - Date: 19
```
发现还不是很干净