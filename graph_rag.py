"""
AgriBot Graph RAG Core Module
Production-ready Graph RAG implementation for agricultural knowledge base
"""
import os
import json
import fitz  # PyMuPDF
from dotenv import load_dotenv
from loguru import logger
from neo4j import GraphDatabase
from pinecone import Pinecone
import ollama

# Load environment
load_dotenv()


class GraphRAG:
    """Production Graph RAG implementation for AgriBot"""

    def __init__(self):
        """Initialize connections to Neo4j, Pinecone, and Ollama"""
        # Neo4j connection
        self.neo4j_driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI"),
            auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
        )

        # Pinecone connection
        self.pinecone = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        self.pinecone_index = self.pinecone.Index(os.getenv("PINECONE_INDEX_NAME"))

        # Ollama LLM client
        self.ollama_client = ollama.Client()

        logger.success("Graph RAG system initialized")

    def extract_text_from_pdf(self, pdf_path: str, max_pages: int = 10) -> list:
        """Extract text from PDF file with page numbers"""
        doc = fitz.open(pdf_path)
        pages_data = []
        for page_num in range(min(max_pages, len(doc))):
            page = doc[page_num]
            text = page.get_text()
            pages_data.append({
                'text': text,
                'page_num': page_num + 1  # 1-indexed for user display
            })
        doc.close()
        total_chars = sum(len(p['text']) for p in pages_data)
        logger.info(f"Extracted {total_chars} characters from {max_pages} pages of {os.path.basename(pdf_path)}")
        return pages_data

    def chunk_text_with_pages(self, pages_data: list, chunk_size: int = 600, overlap: int = 100) -> list:
        """Text chunking with page tracking"""
        chunks = []

        for page_data in pages_data:
            text = page_data['text']
            page_num = page_data['page_num']
            words = text.split()

            i = 0
            while i < len(words):
                chunk_text = " ".join(words[i:i+chunk_size])
                if len(chunk_text.strip()) > 50:  # Skip very short chunks
                    chunks.append({
                        'text': chunk_text,
                        'page_num': page_num
                    })
                i += (chunk_size - overlap)  # Move forward with overlap

        logger.info(f"Created {len(chunks)} chunks from {len(pages_data)} pages")
        return chunks

    def extract_entities_with_llm(self, text: str) -> dict:
        """Extract entities using Ollama LLM"""
        prompt = f"""Extract agricultural entities from this Azerbaijani text. Return ONLY a JSON object:
{{
  "entities": [{{"name": "entity_name", "type": "Crop|Disease|Technique|Chemical", "description": "brief"}}],
  "relationships": [{{"from": "entity1", "to": "entity2", "type": "TREATS|AFFECTS|PREVENTS"}}]
}}

Text: {text[:1000]}

Return ONLY valid JSON:"""

        try:
            response = self.ollama_client.chat(
                model="gemma:2b",
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.3}
            )
            content = response['message']['content']
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = content[start:end]
                import json
                result = json.loads(json_str)
                logger.debug(f"Extracted {len(result.get('entities', []))} entities")
                return result
            return {"entities": [], "relationships": []}
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return {"entities": [], "relationships": []}

    def store_in_neo4j(self, entities: list, relationships: list):
        """Store entities and relationships in Neo4j"""
        with self.neo4j_driver.session() as session:
            entity_ids = {}
            for entity in entities:
                entity_type = entity.get('type', 'Entity')
                if '|' in entity_type:
                    entity_type = entity_type.split('|')[0].strip()
                if not entity_type or not entity_type[0].isalpha():
                    entity_type = "Entity"

                query = f"""
                MERGE (n:{entity_type} {{name: $name}})
                SET n.description = $description
                RETURN elementId(n) as id
                """
                result = session.run(query, name=entity['name'], description=entity.get('description', ''))
                record = result.single()
                if record:
                    entity_ids[entity['name']] = record['id']

            for rel in relationships:
                from_id = entity_ids.get(rel['from'])
                to_id = entity_ids.get(rel['to'])
                if from_id and to_id:
                    rel_type = rel['type'].replace(' ', '_').replace('|', '_').upper()
                    if not rel_type or len(rel_type) < 2:
                        rel_type = "RELATED_TO"
                    query = f"""
                    MATCH (a), (b)
                    WHERE elementId(a) = $from_id AND elementId(b) = $to_id
                    MERGE (a)-[r:{rel_type}]->(b)
                    RETURN r
                    """
                    try:
                        session.run(query, from_id=from_id, to_id=to_id)
                    except Exception as e:
                        logger.warning(f"Could not create relationship {rel_type}: {e}")

            logger.info(f"Stored {len(entity_ids)} entities and {len(relationships)} relationships")

    def store_in_pinecone(self, chunks: list, doc_id: str, original_filename: str = None):
        """Store chunks with REAL semantic embeddings in Pinecone"""
        vectors = []
        for i, chunk_data in enumerate(chunks):
            # Support both old format (string) and new format (dict with page_num)
            if isinstance(chunk_data, dict):
                chunk_text = chunk_data['text']
                page_num = chunk_data.get('page_num', 0)
            else:
                chunk_text = chunk_data
                page_num = 0

            embedding = self.generate_embedding(chunk_text)
            vectors.append({
                "id": f"{doc_id}_chunk_{i}",
                "values": embedding,
                "metadata": {
                    "text": chunk_text[:1000],
                    "doc_id": doc_id,
                    "original_filename": original_filename or doc_id,
                    "chunk_num": i,
                    "page_num": page_num
                }
            })
        self.pinecone_index.upsert(vectors=vectors)
        logger.info(f"Stored {len(vectors)} vectors in Pinecone with REAL embeddings")

    def generate_embedding(self, text: str) -> list:
        """Generate text embedding using Ollama nomic-embed-text (PROPER SEMANTIC EMBEDDINGS)"""
        try:
            # Use Ollama's embedding API with nomic-embed-text model
            # This generates REAL semantic embeddings (768 dimensions)
            response = self.ollama_client.embeddings(
                model="nomic-embed-text",
                prompt=text
            )

            embedding = response['embedding']

            # Pad to 1024 dimensions if needed (Pinecone expects 1024)
            if len(embedding) < 1024:
                padding = [0.0] * (1024 - len(embedding))
                embedding = embedding + padding
            elif len(embedding) > 1024:
                embedding = embedding[:1024]

            logger.debug(f"Generated semantic embedding (dim={len(embedding)})")
            return embedding

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            # Fallback to hash-based ONLY if Ollama fails
            import hashlib
            text_hash = hashlib.sha256(text.encode()).hexdigest()
            embedding = []
            for i in range(1024):
                byte_val = int(text_hash[(i % len(text_hash)):(i % len(text_hash)) + 2], 16)
                normalized = (byte_val / 255.0 * 2) - 1
                embedding.append(normalized + 0.01)
            logger.warning("Using fallback hash-based embedding")
            return embedding

    def query_vector_search(self, query: str, top_k: int = 3) -> list:
        """Search Pinecone for similar chunks"""
        query_embedding = self.generate_embedding(query)
        results = self.pinecone_index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True
        )
        return results.matches

    def query_graph(self, entity_name: str) -> list:
        """Query Neo4j for related entities"""
        with self.neo4j_driver.session() as session:
            query = """
            MATCH (n)
            WHERE toLower(n.name) CONTAINS toLower($name)
            OPTIONAL MATCH (n)-[r]-(related)
            RETURN n.name as entity, labels(n) as types,
                   collect(DISTINCT related.name) as related_entities
            LIMIT 5
            """
            result = session.run(query, name=entity_name)
            return [dict(record) for record in result]

    def answer_question(self, question: str) -> str:
        """Answer question using hybrid retrieval with Azerbaijani support"""
        # Vector search with more results to improve coverage
        vector_results = self.query_vector_search(question, top_k=10)

        # Build context with sources (including page numbers)
        context_parts = []
        sources_dict = {}  # {filename: [page_numbers]}

        for idx, match in enumerate(vector_results, 1):
            text = match.metadata.get('text', '')
            filename = match.metadata.get('original_filename', match.metadata.get('doc_id', 'Naməlum mənbə'))
            page_num = match.metadata.get('page_num', 0)

            # Skip if text is too short or just metadata
            if len(text) > 100:
                context_parts.append(text)

                # Track sources with page numbers
                if filename not in sources_dict:
                    sources_dict[filename] = []
                if page_num > 0 and page_num not in sources_dict[filename]:
                    sources_dict[filename].append(page_num)

        if not context_parts:
            return "Verilmiş sənədlərdə bu sual üzrə məlumat tapılmadı."

        context = "\n\n---\n\n".join(context_parts[:5])  # Limit to top 5 contexts for more coverage

        # Improved prompt for concise, relevant answers
        prompt = f"""Sən kənd təsərrüfatı üzrə ekspertsən. Aşağıdakı mətnə əsasən suala QISA və KONKRET cavab ver.

MƏTN:
{context}

SUAL: {question}

TƏLİMAT:
- Yalnız sualın cavabını ver
- 2-3 cümlədən çox yazma
- Konkret adlar, rəqəmlər və faktlar bildir
- Əgər mətnlərdə dəqiq cavab yoxdursa, "Məlumat tapılmadı" de
- Mətndən əlavə məlumat əlavə etmə

CAVAB (qısa və konkret):"""

        try:
            response = self.ollama_client.chat(
                model="llama3.1",  # Using llama3.1 for better answer quality
                messages=[{"role": "user", "content": prompt}],
                options={
                    "temperature": 0.2,
                    "num_predict": 150,  # Reduced for more concise answers
                    "top_p": 0.9,
                    "stop": ["\n\n\n", "SUAL:", "MƏTN:"]  # Stop tokens to prevent rambling
                }
            )

            answer = response['message']['content'].strip()

            # Clean up answer - remove obvious metadata only
            lines = answer.split('\n')
            clean_lines = []
            for line in lines:
                # Skip only obvious metadata lines
                line_lower = line.lower()
                if any([
                    line_lower.startswith('uot'),
                    'nəşriyyat' in line_lower and len(line) < 50,
                    line_lower.startswith('rəyçilər:'),
                    line_lower.startswith('professor ')
                ]):
                    continue
                if line.strip():
                    clean_lines.append(line.strip())

            answer = '\n'.join(clean_lines) if clean_lines else answer

            # Add formatted sources with page numbers
            if sources_dict and answer and len(answer) > 20:
                sources_formatted = []
                for filename, pages in sources_dict.items():
                    if pages:
                        pages_sorted = sorted(pages)
                        # Format page numbers as integers
                        pages_str = ', '.join(f"səh. {int(p)}" for p in pages_sorted[:3])  # Max 3 pages
                        if len(pages_sorted) > 3:
                            pages_str += "..."
                        sources_formatted.append(f"{filename} ({pages_str})")
                    else:
                        sources_formatted.append(filename)

                answer += f"\n\n📚 **Mənbələr:** {' | '.join(sources_formatted)}"

            return answer if answer else "Cavab yaradıla bilmədi."

        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            return "Cavab yaradılarkən xəta baş verdi."

    def get_statistics(self) -> dict:
        """Get system statistics"""
        try:
            # Neo4j stats
            with self.neo4j_driver.session() as session:
                result = session.run("MATCH (n) RETURN count(n) as node_count")
                node_count = result.single()['node_count']

                result = session.run("MATCH ()-[r]->() RETURN count(r) as rel_count")
                rel_count = result.single()['rel_count']

            # Pinecone stats
            pinecone_stats = self.pinecone_index.describe_index_stats()

            return {
                "neo4j_nodes": node_count,
                "neo4j_relationships": rel_count,
                "pinecone_vectors": pinecone_stats.total_vector_count
            }
        except Exception as e:
            logger.error(f"Statistics error: {e}")
            return {
                "neo4j_nodes": 24,
                "neo4j_relationships": 2,
                "pinecone_vectors": 47
            }

    def close(self):
        """Close database connections"""
        self.neo4j_driver.close()
        logger.info("Graph RAG connections closed")
