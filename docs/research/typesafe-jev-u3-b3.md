# TypeSafe / Jev facts used by U3/B3

Checked against first-party TypeSafe documentation on 2026-10-18. These facts
are recorded only to define the offline contract; U3/B3 makes no provider
request and does not install or import a TypeSafe SDK.

## Facts

- Jev is evaluated through TypeSafe's System One endpoint, and requests name a
  model. The current model page lists versioned IDs `jev-1.14.0` and
  `jev-1.13.0`, while aliases such as `jev-latest` can move between releases.
  U3/B3 therefore records provider, model, and resolved model version rather
  than treating an alias as a stable experiment identity.
- A `Choice` question returns a selected choice, probabilities across the
  declared options, and confidence. U3/B3 validates that shape in recorded
  responses and stores the raw response fingerprint.
- TypeSafe documents confidence as a statistic derived from the answer's
  probability distribution. It is not treated as a calibrated probability of
  a future BTC return.
- TypeSafe's documented customization boundary is state/question design rather
  than customer fine-tuning or LoRA weights. U3/B3 consequently tests only a
  typed recorded assessment and does not claim model adaptation.

## Sources

- [TypeSafe Models](https://docs.typesafe.ai/models)
- [TypeSafe Introduction](https://docs.typesafe.ai/introduction)
- [TypeSafe Primitives](https://docs.typesafe.ai/primitives)
- [TypeSafe Confidence](https://docs.typesafe.ai/confidence)
- [TypeSafe API reference](https://docs.typesafe.ai/api)

## Boundary

The executable benchmark uses deterministic JSON fixtures only. It has no
`TYPESAFE_API_KEY`, provider SDK, HTTP client, socket, retry, network, or
credential path. Any future provider integration would require a separate
decision and live-transport gate.
