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
- 选填：`birthYear`, `deathYear`

### `Organization`（机构）
- 必填：`id`, `name`
- 选填：`type`, `country`

### `Work`（作品）
- 必填：`id`, `title`
- 选填：`year`

### `Concept`（概念）
- 必填：`id`, `name`
- 选填：`description`

### `Event`（事件）
- 必填：`id`, `name`
- 选填：`year`, `description`

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


