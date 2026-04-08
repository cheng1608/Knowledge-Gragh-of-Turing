MATCH (n) RETURN count(n);
MATCH (n:Entity) RETURN count(n);
MATCH p = ()-[:REL]->() RETURN p LIMIT 25;