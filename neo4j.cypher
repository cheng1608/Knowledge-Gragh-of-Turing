// Neo4j helpers for Turing KG (CSV produced by scripts/graph/build_graph_tables.py).
// Run from Neo4j Browser after copying CSV into Neo4j `import` directory, or adjust file URLs.

// --- Constraints (run once) ---
// CREATE CONSTRAINT node_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE;

// --- Import nodes (id, label, name, source, confidence, wikidata_description) ---
// LOAD CSV WITH HEADERS FROM 'file:///nodes_final.csv' AS row
// MERGE (n:Entity {id: row.id})
// SET n.label = row.label,
//     n.name = row.name,
//     n.source = row.source,
//     n.confidence = toFloat(row.confidence),
//     n.description = row.wikidata_description;

// --- Import relations (start_id, relation, end_id, year, role, source, confidence, evidence, source_url) ---
// LOAD CSV WITH HEADERS FROM 'file:///relations_final.csv' AS row
// MATCH (a:Entity {id: row.start_id})
// MATCH (b:Entity {id: row.end_id})
// CALL apoc.create.relationship(a, row.relation, b, {
//   year: row.year,
//   role: row.role,
//   source: row.source,
//   confidence: toFloat(row.confidence),
//   evidence: row.evidence,
//   source_url: row.source_url
// }) YIELD rel
// RETURN count(rel);
// (If APOC is unavailable, use FOREACH with a static type — see Neo4j docs for dynamic rel types.)

// --- Sample queries ---
MATCH (n) RETURN count(n) AS nodes;
MATCH ()-[r]->() RETURN count(r) AS rels;

// One-hop neighborhood of Alan Turing (Q7251)
MATCH (t:Entity {id: 'Q7251'})-[r]->(n)
RETURN type(r) AS rel, n.id AS nid, n.name AS name
LIMIT 50;

// Two-hop paths from Turing to any Concept
MATCH p = (t:Entity {id: 'Q7251'})-[*1..2]->(c:Entity)
WHERE c.label = 'Concept'
RETURN p LIMIT 25;
