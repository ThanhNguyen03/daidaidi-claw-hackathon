"""
Dedicated thread pool for LLM calls.
=====================================
Every LLM completion — planner, selectors, specialists, synthesis, the deck
extractor — reaches the provider through `run_in_executor(None, ...)`, which
uses asyncio's *default* executor. `asyncio.to_thread` (used for DB and file
I/O elsewhere in the app) draws from that same default pool.

`llm/client.py`'s `_INFLIGHT` semaphore parks a worker thread for the whole
duration of a call while it waits for a slot, and `central_agent/agent.py`'s
synthesis worker holds one for an entire token stream. On a small box the
default pool (`min(32, cpu+4)` — 6 threads on a 2-vCPU container) fills with
LLM calls, and a DB write queued behind them waits out someone else's
completion instead of running in parallel with it.

Giving LLM calls their own pool doesn't change how many can reach the
provider at once — `_INFLIGHT` still caps that at `LLM_MAX_CONCURRENCY` — it
only stops those calls from starving unrelated `to_thread` work.
"""

import atexit
import os
from concurrent.futures import ThreadPoolExecutor

# Sized above LLM_MAX_CONCURRENCY: threads can be parked waiting on _INFLIGHT,
# not just running a request, so the pool needs room for the admitted calls
# plus whatever else is queued behind the semaphore at any moment.
_MAX_WORKERS = int(os.getenv("LLM_MAX_CONCURRENCY", "3")) * 2 + 4

LLM_POOL = ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix="llm")
atexit.register(LLM_POOL.shutdown, wait=False)
