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
发现还不是很干净，规则匹配进一步清洗
`scripts\refine_entities.py`

生成data\processed\entities_refined.csv和data\processed\entities_review.csv

## 6.类型对齐
`scripts\align_to_schema.py`

在传记里抽取的用的是spaCy的模型分类，要和设计的schema对齐

对齐后输出为entities_schema命名的

## 7. 消歧（实体链接）

`scripts\entity_linking.py`

使用 Wikidata API 做实体消歧（链接到 QID）
有问题，应该用词袋模型计算相似度

输入：
`data/processed/entities_schema_aligned.csv`

输出：
`data/processed/entities_linked.csv`
`data/processed/entities_unlinked.csv`

技术路径：
- 候选召回：`wbsearchentities`
- 候选类型读取：`Special:EntityData/{qid}.json`（取 P31）
- 评分：名称匹配 + 类型匹配 + 描述关键词 + 排名
- 阈值过滤：默认 `0.75`

工程问题与处理：
- 运行中遇到 `403 Forbidden`
- 给请求增加 `User-Agent` 和 `Accept` 头
- 增加重试机制与单条失败不中断

最终结果：
```
Input rows: 57
Linked: 43
Unlinked: 14
```

## 8. 终表构建（nodes / relations）

`scripts\build_graph_tables.py`

目标：把已链接实体与结构化关系合并，生成最终可入库表

输入：
`data/processed/entities_linked.csv`
`data/processed/nodes.csv`
`data/processed/relations.csv`

处理逻辑：
- 按链接分数过滤（默认 `>=0.85`）
- 过滤泛词节点（如 Alan / Turing 等）
- 按 QID 去重合并节点
- 关系仅保留两端节点都存在的边

输出：
`data/final/nodes_final.csv`
`data/final/relations_final.csv`

结果：
```
Final nodes: 53
Final relations: 29
```
