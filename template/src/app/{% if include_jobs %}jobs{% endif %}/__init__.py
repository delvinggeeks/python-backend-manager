"""Background jobs + scheduler (arq).

arq is the queue and arq's built-in cron is the scheduler — used directly, NOT hidden behind a
runtime port (that abstraction is reserved for swappable vendors like payments/email, not for an
infrastructure choice). Call sites enqueue work through :func:`app.jobs.queue.enqueue` so they
never import arq; the worker process (``arq app.jobs.worker.WorkerSettings``) runs the registered
task functions and the cron schedule. Requires the `worker` extra (arq) + a reachable REDIS_URL.
"""

from __future__ import annotations
