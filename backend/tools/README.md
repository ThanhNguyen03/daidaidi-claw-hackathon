# Agent Skills & Knowledge — Ingest & RAG

## How it works

```
App startup
    └─► tools/ingest.py :: ingest_all_agents()
            └─► walks backend/agents/<name>/{skills,knowledge}/*.md
            └─► chunks each file at H2/H3 headings
            └─► indexes chunks into LanceDB with metadata {agent, type, source}
            └─► skips unchanged files (MD5 hash check via data/ingest_state.json)

Per request (inside agent.run())
    └─► await self.build_rag_context(user_message)
            ├─► retrieve_skill(query)   → top-1 relevant skill chunk
            └─► retrieve_knowledge(query) → top-3 relevant knowledge chunks
            → returns formatted context string (~300-1500 tokens)
```

**Token cost:** only retrieved chunks are sent to the LLM — not all files. A
typical call injects < 1500 tokens regardless of how many files exist.

**No disk reads per request:** LanceDB caches the table in-process. After
startup, all retrieval is in-memory vector search. Embeddings are produced by
the configured provider, which defaults to GreenNode-hosted `baai/bge-m3`.

---

## Adding a new skill or knowledge file

1. Drop the `.md` file into the correct agent folder:

   ```
   backend/agents/<agent_name>/skills/<my-new-skill>.md
   backend/agents/<agent_name>/knowledge/<my-new-fact>.md
   ```

2. Restart the server. `ingest_all_agents()` runs at startup and picks it up
   automatically. Unchanged files are skipped (hash check), so startup stays fast.

3. Done — the agent's `retrieve_skill()` / `retrieve_knowledge()` will now find
   it when the query is relevant.

---

## Removing a file

1. Delete the `.md` file.
2. Restart the server. On the next startup, if the file's source key is in
   `data/ingest_state.json` but the file no longer exists, it will **not** be
   re-indexed. The old LanceDB entries remain but will naturally stop being
   retrieved (no matching source hash → `delete_by_source` is called when the
   file is updated, but not on delete).

   To force-remove stale entries, run:
   ```
   python -m tools.ingest --force --agent <name>
   ```
   This re-indexes all current files for that agent (removing stale chunks
   because `delete_by_source` is called before each file is re-added).

---

## Force re-index

```bash
# Re-index everything (all agents, all files)
python -m tools.ingest --force

# Re-index one agent only
python -m tools.ingest --agent compliance --force
```

---

## Agent lookup contract

Every `retrieve_skill` / `retrieve_knowledge` call filters by:
- `agent` = the calling agent's name (e.g. `"compliance"`)
- `type` = `"skill"` or `"knowledge"`

So agents only ever retrieve their own files. No cross-agent leakage.

---

## File layout reference

```
backend/agents/
├── sales_orchestrator_agent/
│   ├── skills/          ← orchestrator.md, skill_feedback.md
│   └── reference/       ← orchestrator workflow, proposal assembler, data masking, legacy skill refs
├── requirement_elicitation_agent/
│   ├── skills/          ← requirement-elicitor.md
│   └── reference/       ← requirement elicitation reference material
├── market_strategy_agent/
│   ├── skills/          ← strategy-skill.md, case-study-advisor.md
│   └── reference/       ← case studies, strategy consultant, objection handling
├── product_solution_agent/
│   ├── skills/          ← product-advisor.md, solution-designer.md, miniapp-specialist.md, integration-advisor.md
│   └── reference/       ← pricing, domain knowledge, integration, platform references
├── compliance_policy_agent/
│   ├── skills/          ← compliance-skill.md
│   └── reference/       ← compliance policies and legal references
├── client_simulator_agent/
│   ├── skills/          ← objection-bank.md
│   └── reference/       ← objection handling and battlecard references
└── design/
    └── skills/          ← design system / wireframe helpers
```
