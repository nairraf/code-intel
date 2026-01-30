# Overview

Local cognee MCP tool to give cloud based AI's access to project based memory.

# local environment
- DEV IDE: antigravity
- GPU: AMD Radeon RX 7800XT with 16GB VRAM
- ollama

# Current Status

there was a small POC performed with init_memory.py, this was a small test on a specific repository. This worked but needs to be expanded to a MCP tool which antigravity (or any local MCP aware system can call). The current attempt is with mcp_cognee.py.

# TODO

- [ ] local memory system should be project aware. 
- [ ] there should be a central way to store all local cognee databases
- [ ] confirm the best local models to use, POC was with qwen2.5-coder:7b and bge-small-en-v1.5. cognee did not work with bge-m3 in the POC
 
