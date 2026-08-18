# Security and trust boundaries

## Protected assets

- model API credentials and database credentials;
- integrity of queue/checkpoint/result state;
- source attribution and research objective;
- the host running the worker.

## External page text is untrusted

The live research tool treats pages only as data. It can request a small fixed path allowlist on
the imported official domain. Page content cannot add tools, change the company/group objective,
read environment variables, or cause shell execution. Redirects leaving the imported domain are
discarded.

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

Live collection accepts only `http`/`https` URLs validated by Pydantic. It follows redirects but
stores a page only when the final hostname is the imported host or its subdomain. A production
deployment should add DNS/IP filtering to prevent private-network resolution and should use a
sandboxed egress proxy. Live mode should not be exposed as a public SSRF-capable service in its
current form.

## Operational recommendations

- Use a dedicated low-privilege PostgreSQL role and rotate nonlocal credentials.
- Set provider spend/rate limits.
- Keep request timeout below the worker lease duration.
- Review the selected official domains before a large live run.
- Run dependency and secret scanning in the publishing workflow.
- Do not add arbitrary browser automation or shell tools to prompts.

## Known limitations

Live provider behavior, public-web accuracy, robots/terms requirements for each imported site, and
PostgreSQL execution were not verified on the build workstation. The deterministic replay contains
small authored facts and URLs, not bulk scraped or proprietary content.

