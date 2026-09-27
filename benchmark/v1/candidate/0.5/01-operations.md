# Operating Scale

Correct financial results must remain usable as an ordinary tenant grows. The
evaluation runtime provides two CPU cores and 4 GiB memory, with PostgreSQL on the
same isolated runtime. No particular schema, cache or computation strategy is
required. Use your own tests and profiling; you may populate your own test database
directly if that is convenient. Only the evaluator uses public operations for setup.

Support a tenant with 128 customers, each having an accepted, activated annual
subscription with one monthly flat charge, using a shared catalog. Most background
customers have no invoices or complicated histories. The focal customer has a
billed subscription; the final release also corrects its price. Adding unrelated customers must
not alter a focal customer's financial results.

At this size, a customer statement, one subscription's revenue-unit list, a
single-customer bill preview and a single receipt creation must each complete
within five seconds. The complete response and its normal financial semantics are
required; an empty response or a held operation is not a performance optimization.
Later releases retain these requirements. Requests are serial, not concurrent load.

We measure sizes 1, 16, 64 and 128, reporting preparation separately from the focal
operations. At sizes 16 and 128, three successful samples per focal operation are
compared using their median. Each receipt has its own key; reads/previews use a
fixed business horizon. Timing evaluation is serial and separate from model work.
Host health latency is recorded; infrastructure stalls are investigated, not scored
as business mistakes. A timed-out request is not retried indefinitely. Performance
and functional results are separate, including when setup prevents later measurements.

The supplied protocol.schema.json describes common envelopes and selected foundation
inputs, not the complete business contract. smoke.py checks basic HTTP shapes and
the omitted optional revenue_presentation default. It does not evaluate financial
correctness and is not a substitute for your tests. Run it against a disposable
development database: python3 requests/smoke.py --base-url http://localhost:4000
--secret "$BILLING_AUTH_SECRET".
