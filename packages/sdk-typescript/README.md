# packages/sdk-typescript

The Verum TypeScript SDK — `npm install @verum/sdk`.

**Status:** Phase 0 stub. The high-level API ships in Phase 3 (F-3.9), with full parity to the Python SDK.

## Planned API

```typescript
import { Verum } from "@verum/sdk";

const verum = new Verum({ apiKey: "...", projectId: "..." });

const response = await verum.chat({
  model: "grok-2-1212",
  messages: [...],
  deploymentId: "...",
});

const chunks = await verum.retrieve({
  query: "...",
  collection: "arcana-tarot-knowledge",
  topK: 5,
});

await verum.feedback({ traceId: "...", score: 1 });
```

See [docs/ARCHITECTURE.md §6](../../docs/ARCHITECTURE.md#6-sdk-surface) for the full SDK surface.
