# 图灵知识图谱本体

## 1. 项目范围

- 人物：图灵及核心关联人物
- 机构：学校、研究机构、项目机构
- 作品：代表论文与重要文章
- 概念：图灵机、可计算性、图灵测试
- 事件：关键历史节点
- 地点：出生地、工作地

---

## 2. 实体类型（6类）

### `Person`（人物）
- 必填：`id`, `name`
- 选填：`birthYear`, `deathYear`, `aliases`（别名，便于实体链接与展示）
- 选填：`birthPlace`, `deathPlace`（若与 `Place` 节点连边，可二选一：仅属性或仅边）
- 选填：`occupation`（短标签，如 mathematician）

### `Organization`（机构）
- 必填：`id`, `name`
- 选填：`type`, `country`

### `Work`（作品）
- 必填：`id`, `title`
- 选填：`year`, `doi`, `publicationVenue`

### `Concept`（概念）
- 必填：`id`, `name`
- 选填：`description`

### `Event`（事件）
- 必填：`id`, `name`
- 选填：`year`（单点时间）、`startYear` / `endYear`（区间事件时推荐使用二者；若只用 `year`，表示主要发生年或近似年）
- 选填：`description`

### `Place`（地点）
- 必填：`id`, `name`
- 选填：`country`

---

## 3. 关系类型（8类）

- `Person -[AUTHORED]-> Work`（写了什么）
- `Person -[AFFILIATED_WITH]-> Organization`（在哪学习/工作）
- `Person -[PROPOSED]-> Concept`（提出了什么）
- `Work -[INTRODUCES]-> Concept`（作品介绍了什么概念）
- `Person -[PARTICIPATED_IN]-> Event`（参与了什么事件）
- `Event -[OCCURRED_IN]-> Place`（事件发生在哪里）
- `Organization -[LOCATED_IN]-> Place`（机构位于哪里）
- `Person -[INFLUENCED]-> Person`（影响了谁）

### 补边阶段可能出现的扩展关系（非种子必须，但终表中可能存在）

由 Wikidata 属性映射或文本共现产生，用于增密图或溯源演示；答辩时应说明其与核心 8 类关系的区别。

- `Person -[BORN_IN]-> Place`（出生地）
- `Person -[DIED_IN]-> Place`（逝世地）
- `Person -[RESIDED_IN]-> Place`（居住地，与机构隶属不同）
- `Work|Organization|Place -[LOCATED_IN]-> Place`（作品/机构/地点位于某地）
- `* -[RELATED_TO]-> *`（`role` 中可存 Wikidata PID，如 `P31`，表示未映射到上表的直接属性）
- `* -[CO_MENTIONED]-> *`（传记文本同句共现；`role` 常为 `co_mentions=k`；置信度通常低于结构化边）

---

## 3.1 关系表字段（`relations_final.csv`）

除 `start_id`, `relation`, `end_id`, `year`, `role`, `source` 外，建议统一包含：

- `confidence`：0–1 之间的小数字符串；缺失时由构建脚本按 `source` 类型补默认。
- `evidence`：短文本摘录或句子级引用（尤其对 `CO_MENTIONED`）。
- `source_url`：可点击的出处（Wikidata 实体页、MacTutor 传记 URL 等）。

---

## 4. 简单约束

- 每个节点都要有唯一 `id`
- 每条关系尽量有来源（如维基/教材）
- 先保证关系正确，再扩展数量
- `Person.name` 和 `Work.title` 尽量避免重复

---

## 5. 示例三元组

1. `(Alan Turing)-[PROPOSED]->(Turing Machine)`
2. `(Alan Turing)-[AUTHORED]->(On Computable Numbers)`
3. `(On Computable Numbers)-[INTRODUCES]->(Computability)`
4. `(Alan Turing)-[AFFILIATED_WITH]->(University of Cambridge)`
5. `(Alan Turing)-[PROPOSED]->(Turing Test)`
6. `(Alan Turing)-[PARTICIPATED_IN]->(WWII Codebreaking Project)`
7. `(WWII Codebreaking Project)-[OCCURRED_IN]->(Bletchley Park)`
8. `(University of Cambridge)-[LOCATED_IN]->(Cambridge)`

---


