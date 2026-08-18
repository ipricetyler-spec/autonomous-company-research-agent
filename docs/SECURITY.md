# Security and trust boundaries

## Protected assets

- model API credentials and database credentials;
- integrity of queue/checkpoint/result state;
- source attribution and research objective;
- the host running the worker.

## External page text is untrusted

The live research tool treats pages only as data. It can request a small fixed path allowlist on
the imported official domain. Page content cannot add tools, change the company/group objective,
read environment variables, or cause shell execution. Redirects are handled manually and must
pass the complete network policy before the next request is sent.

The model system instruction explicitly tells the extractor to ignore instructions in page text.
Only supplied source URLs may appear in validated results. This is a useful defense boundary, not
a claim that prompt injection is fully solved.

## Secret handling

- Secrets are read from environment variables.
- `.env`, databases, logs, generated exports, and demo artifacts are ignored by Git.
- Authorization headers are constructed only for the configured model endpoint.
- Logs contain IDs, state, timings, and sanitized errors; they do not intentionally include
  request headers, environment values, prompts, or page bodies.
- `.env.example` contains placeholders only.

## Network boundary

Live collection applies all of these checks before every initial or redirected request:

- absolute `http`/`https` URL;
- no URL-embedded credentials;
- only ports 80 and 443;
- hostname remains the imported host or its subdomain;
- every resolved IPv4/IPv6 address is globally routable; mixed public/private DNS answers fail
  closed.

When HTTPX exposes the connected socket peer, that address is checked again before response data
is processed. Automatic redirect following is disabled, so a redirect to localhost or another
domain is rejected before the follow-up request.

Application filtering does not replace network isolation. DNS can change between validation and
connection on platforms where the peer address is unavailable, and HTTP proxies may resolve names
outside the process. A public multi-tenant deployment should additionally enforce the same policy
through a sandboxed egress proxy or firewall.

## Operational recommendations

- Use a dedicated low-privilege PostgreSQL role and rotate nonlocal credentials.
- Set provider spend/rate limits.
- Keep request timeout below the worker lease duration.
- Review the selected official domains before a large live run.
- Run dependency and secret scanning in the publishing workflow.
- Do not add arbitrary browser automation or shell tools to prompts.

## Known limitations

The local Ollama run verifies live execution, citation allowlisting, retries, and field isolation;
its current exact-match report uses authored reference labels that have not been independently
adjudicated. Robots and site terms remain operator responsibilities for each imported domain. The
deterministic replay contains small authored facts and URLs, not bulk scraped or proprietary
content. Network-level egress controls remain required for a public multi-tenant deployment.

