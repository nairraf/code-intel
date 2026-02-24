Code-Intel Tool Evaluation Report
Executive Summary
A comprehensive evaluation of the code-intel MCP tools was performed on the selos project to assess their readiness and reliability.

The Verdict: The tools are highly capable for exploration and jumping to definitions across both Python and Dart. However, reference tracking (Knowledge Graph reverse edges) remains a weak point, especially for Dart.
Recommendation: I recommend dedicating 10-15% of effort toward improving the code-intel tool's reference tracking (specifically for Dart and AST-based Python referencers), while the remaining 85-90% of effort should be focused on building the selos project. The tool as it stands is more than sufficient to accelerate development, but fixing reference edges will make large-scale refactors safer.
Evaluation Details & Cross-Referenced Accuracy
1. mcp_code-intel_refresh_index
Action: Executed full rebuild via force_full_scan=True.
Result: Successfully scanned 83 files (0 skipped) generating 220 chunks.
Accuracy: Perfect. Handled the transition seamlessly without blocking or crashing.
2. mcp_code-intel_get_stats
Result: Accurately reported project distribution.
Dart: 100 chunks
Python: 47 chunks
C++: 32 chunks
Highlighted correct dependency hubs (flutter/material.dart, auth_providers.dart).
Accuracy: Perfect. Accurate mapping of highest complexity files and missing tests (index_bible).
3. mcp_code-intel_search_code
Input: "middleware and decorators in the codebase"
Result: Retrieved 10 highly relevant chunks including:
CORSMiddleware in 
selos_api/main.py
.
AuthGate ConsumerWidget in Dart.
Accuracy: High. The semantic representation accurately linked the concepts of "middleware" to both Python standard middleware and Flutter Riverpod concepts.
4. mcp_code-intel_find_definition
Python Middleware Test: Checked verify_firebase_token inside a FastAPI Depends() function in 
selos_api/app/routers/analysis.py
 (Line 15).
Result: Jumped accurately to 
selos_api/app/middleware/firebase_auth.py
. Accuracy: 100%.
Dart Widget Test: Checked LoginScreen() invocation inside 
selos_app/lib/features/auth/auth_gate.dart
 (Line 19).
Result: Jumped accurately to the widget definition in login_screen.dart. Accuracy: 100%.
5. mcp_code-intel_find_references (The Weakness)
Python Test: Tracked references for verify_firebase_token.
Result: Found the reference in 
analysis.py
, however it reported: (Low Confidence: name_match).
Issue: The AST parser or the knowledge graph did not formalize this as a structural edge, resorting to regex/string fallback.
Dart Test: Tracked references for LoginScreen.
Result: Returned: Symbol 'LoginScreen' found... but no references were discovered in the knowledge graph.
Issue: The reference from 
auth_gate.dart
 to LoginScreen was entirely missed by the reference graph. The Dart indexer is currently failing to emit structural USED_BY edges for widget instantiations.

---

Actionable Feedback for Code-Intel Agents
If you take this to the agent/team working on code-intel, provide them with this specific feedback:

Enhance Dart Reference Parsing: The Knowledge Graph currently drops or fails to parse structural usages of Dart classes/Widgets when instantiated. find_references returns empty even when definitions exist and are actively called.
Elevate Python Reference Confidence: Middleware and decorators (like FastAPI Depends) are correctly jumped to, but reverse-tracking relies on name_match instead of structural AST edges. The Tree-sitter query for Python needs to identify arguments passed to Depends() as explicit reference edges.