# U7-L: Paper2Slides-ready cited research brief

U7-L exports the already validated `ResearchSynthesis` as a deterministic
Markdown artifact. Paper2Slides documents Markdown as an accepted document
input; this slice prepares that input without running its model-based planning
or media-generation pipeline.

## Use

Every workflow run that produces cited research now also stores a
`research-brief` artifact beside its JSON artifacts. Inspect the run to find
the local artifact path:

```text
market-os inspect <run-id>
market-os inspect <run-id> --resource research-brief
```

To render a standalone Markdown file from a validated cited-research JSON
artifact:

```text
market-os research-brief --source market_os/tests/fixtures/research/u7_l_cited_research.json --markdown output/u7-l/research-brief.md --json output/u7-l/research-brief-evidence.json
```

The output retains supported claims, exact supporting quotes, citation IDs,
source references, coverage, synthesis fingerprints, and source artifact
lineage. The Markdown artifact is content-addressed and indexed as
`text/markdown`; inspection checks its location, SHA-256, and lineage before
returning it. Markdown control characters in labels are escaped, while source
quotes are kept verbatim inside dynamically sized code fences.

## Source and boundary

Paper2Slides is referenced at commit
`0785051d1f52814097e94c44751e3f12b83f7c8a`; its README documents Markdown input.
Its pipeline is not invoked here. The checked-in input and CI output are
synthetic, private, paper-only, read-only, network-disabled, and
execution-disabled. The export makes no provider requests and does not mutate
portfolio state.

Evidence schema: `market-os.u7-l-research-brief-evidence@v1`. CI uploads the
Markdown artifact and JSON evidence manifest. Paper2Slides LLM planning, image
or video generation, credentials, and live execution remain deferred.
