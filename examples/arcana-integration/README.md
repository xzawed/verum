# examples/arcana-integration

First dogfood target: ArcanaInsight integration with The Verum Loop.

**Status:** Not started. Populated in Phase 3 (F-3.10) when the Python SDK injection lands.

## What this will show

A complete before/after of ArcanaInsight's tarot consultation service:

1. **Before Verum**: ArcanaInsight calls Grok directly with a static hand-written prompt.
2. **After Verum**: ArcanaInsight calls `verum.chat()`, which routes through a Verum-generated Chain-of-Thought prompt, retrieves context from the `arcana-tarot-knowledge` collection, and traces everything to the dashboard.
3. **After one EVOLVE cycle**: The prompt has been auto-improved based on A/B test results — with no manual prompt engineering.

## Related roadmap items

- F-1.3, F-1.4: ANALYZE detects ArcanaInsight's Grok calls
- F-2.1: INFER classifies ArcanaInsight as `divination/tarot`
- F-2.4: HARVEST collects 1,000+ tarot knowledge chunks
- F-3.10: SDK integrated; tarot endpoint using `verum.chat()` + `verum.retrieve()`
- F-4.11: First auto-evolution cycle completes
