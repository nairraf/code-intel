import re
from typing import List
from pathlib import Path
from ..models import CodeChunk

class FirestoreRulesParser:
    """Specialized parser for firestore.rules files."""
    
    def parse(self, filepath: str) -> List[CodeChunk]:
        """Extracts match blocks and rules as semantic chunks."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            chunks = []
            # Heuristic: Find 'match' statements and their subsequent blocks
            # We look for match /path/ { ... }
            # This is a simplified regex-based approach for the initial version
            pattern = re.compile(r'(match\s+([^{]+)\s*\{)')
            
            lines = content.splitlines()
            
            for match in pattern.finditer(content):
                full_match = match.group(1)
                path = match.group(2).strip()
                start_index = match.start()
                
                # Find matching closing brace
                brace_count = 0
                end_index = -1
                for i in range(start_index, len(content)):
                    if content[i] == '{':
                        brace_count += 1
                    elif content[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_index = i + 1
                            break
                
                if end_index != -1:
                    block_content = content[start_index:end_index]
                    
                    # Calculate line numbers
                    before_content = content[:start_index]
                    start_line = before_content.count('\n') + 1
                    end_line = start_line + block_content.count('\n')
                    
                    chunks.append(CodeChunk(
                        id=f"firestore:{filepath}:{start_line}",
                        filename=filepath,
                        start_line=start_line,
                        end_line=end_line,
                        content=block_content,
                        type="firestore_match",
                        language="firestore",
                        symbol_name=path,
                        signature=f"match {path}"
                    ))
            
            # If no matches found, return one big chunk for the whole file
            if not chunks and content.strip():
                chunks.append(CodeChunk(
                    id=f"firestore:{filepath}:1",
                    filename=filepath,
                    start_line=1,
                    end_line=len(lines),
                    content=content,
                    type="firestore_file",
                    language="firestore"
                ))
                
            return chunks
        except Exception:
            return []
