RETURN 1 AS ok;
MATCH (n) RETURN count(n) AS n;
MATCH (n:Entity) RETURN n LIMIT 25;
MATCH p=()-[:REL]->() RETURN p LIMIT 25;
MATCH (n:Entity {id: 'Q7251'})-[r]-(m) RETURN n, r, m LIMIT 50;