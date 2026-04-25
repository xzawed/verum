# Verum 테스트 관례 (Patterns)

## Python (apps/api)

### 필수 설정 (pyproject.toml)

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"                  # @pytest.mark.asyncio 불필요
asyncio_default_fixture_loop_scope = "function"
markers = [
  "requires_db: test requires a real Postgres connection (auto-skipped without DATABASE_URL)",
]
```

### `requires_db` 마커 판정 기준

| 조건 | 결론 |
|------|------|
| SQLAlchemy session 사용 | requires_db |
| `async_db_session` fixture 사용 | requires_db |
| PostgreSQL LISTEN/NOTIFY | requires_db |
| AsyncMock으로 session 스텁 | 마커 불필요 (unit) |
| respx로 httpx mock | 마커 불필요 (unit) |

### `async_db_session` fixture (conftest.py L91 근처에 정의됨)

```python
# 사용법 — 이미 정의된 fixture를 인자로 받기만 하면 됨
@pytest.mark.requires_db
async def test_something_with_db(async_db_session):
    # async_db_session은 AsyncSession
    result = await async_db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1
```

### AsyncMock 패턴 (DB 없이 스텁)

```python
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=lambda: []))))
    session.commit = AsyncMock()
    session.add = MagicMock()
    return session

async def test_something(mock_session):
    result = await my_repository.get_all(mock_session)
    assert result == []
```

### Anthropic/OpenAI mock

```python
from unittest.mock import AsyncMock, MagicMock, patch

with patch("src.loop.infer.engine.anthropic.AsyncAnthropic") as mock_cls:
    mock_client = AsyncMock()
    mock_cls.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text='{"domain": "tarot"}')]
    )
    # ... test ...
```

### respx로 httpx mock (HARVEST 크롤링 등)

```python
import respx
import httpx

@respx.mock
async def test_crawler_fetches_page():
    respx.get("https://example.com/tarot").mock(
        return_value=httpx.Response(200, text="<html>타로 정보</html>")
    )
    result = await crawler.fetch("https://example.com/tarot")
    assert "타로" in result
```

---

## TypeScript (apps/dashboard)

### Jest 설정 (jest.config.ts)

```typescript
preset: "ts-jest/presets/default-esm"  // 또는 ts-jest
testEnvironment: "node"
moduleNameMapper: { "^@/(.*)$": "<rootDir>/src/$1" }
```

### DB mock — `makeSelectChain` 패턴

`apps/dashboard/src/lib/db/__tests__/queries.test.ts` 에서 정의된 헬퍼:

```typescript
// 재사용 패턴 (import하거나 로컬로 복사)
jest.mock("@/lib/db/client");
import { db } from "@/lib/db/client";

const mockDb = db as jest.Mocked<typeof db>;

// select chain mock
const makeSelectChain = (returnValue: unknown[] = []) => {
  const chain: Record<string, jest.Mock> = {};
  ["select", "from", "where", "limit", "orderBy", "leftJoin", "innerJoin"].forEach(
    (m) => (chain[m] = jest.fn().mockReturnValue(chain))
  );
  chain["then"] = jest.fn().mockImplementation((resolve) => resolve(returnValue));
  // Promise-like
  Object.defineProperty(chain, Symbol.iterator, { value: [][Symbol.iterator].bind([]) });
  return chain;
};

(mockDb.select as jest.Mock).mockImplementation(() => makeSelectChain([{ id: "1" }]));
```

### Auth mock

```typescript
jest.mock("@/auth", () => ({
  auth: jest.fn().mockResolvedValue({
    user: { id: "test-user-1", github_access_token: "tok" },
  }),
}));
```

### Route handler 테스트 구조

```typescript
import { NextRequest } from "next/server";
import { GET, POST } from "@/app/api/repos/[id]/status/route";

describe("GET /api/repos/[id]/status", () => {
  const params = Promise.resolve({ id: "repo-123" });

  it("returns 401 when not authenticated", async () => {
    const { auth } = await import("@/auth");
    (auth as jest.Mock).mockResolvedValueOnce(null);
    const req = new NextRequest("http://localhost/api/repos/repo-123/status");
    const res = await GET(req, { params });
    expect(res.status).toBe(401);
  });

  it("returns job status for owner", async () => {
    (mockDb.select as jest.Mock).mockImplementationOnce(() =>
      makeSelectChain([{ status: "done", repoId: "repo-123" }])
    );
    const req = new NextRequest("http://localhost/api/repos/repo-123/status");
    const res = await GET(req, { params });
    const body = await res.json();
    expect(body.status).toBe("done");
  });
});
```

---

## Playwright E2E

### Auth 우회

```typescript
// 각 spec 파일 상단 또는 beforeEach
test.beforeEach(async ({ page }) => {
  await page.goto("/test/login");
  await page.waitForURL("/repos");
});
```

### storageState 재사용 (로그인 캐시)

```typescript
// playwright.config.ts
use: {
  storageState: "e2e/.auth/user.json",  // 있으면 재사용
}

// global-setup.ts
import { chromium } from "@playwright/test";
export default async function globalSetup() {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto("http://localhost:3000/test/login");
  await page.context().storageState({ path: "e2e/.auth/user.json" });
  await browser.close();
}
```

### data-testid 관례

새 컴포넌트에 testid가 필요하면 이 패턴으로 추가:
```tsx
<div data-testid={`status-${label.toLowerCase()}`}>
<button data-testid="register-repo-btn">
<a data-testid={`repo-link-${repo.id}`}>
```

---

## 커버리지 도구 동기화 규칙

### Sonar exclusions ↔ Jest `collectCoverageFrom` 반드시 쌍으로 관리

`sonar.coverage.exclusions`(sonar-project.properties)와 Jest의 `collectCoverageFrom`(jest.config.ts)은 각각 독립적으로 커버리지 분모를 계산한다. 한 쪽만 추가하면:
- Sonar에서는 제외됐는데 Jest에서는 미커버로 잡혀 `coverageThreshold` 실패
- Jest에서는 제외됐는데 Sonar에서는 분모에 포함돼 수치 괴리 발생

**규칙:** 파일을 어느 한 쪽에 추가할 때는 반드시 다른 쪽에도 추가한다.

### `# pragma: no cover`와 Codecov patch gate

`coverage.py`가 `# pragma: no cover`를 처리하면 해당 라인이 `coverage.xml`에서 **완전히 사라진다** (excluded로 마킹되는 게 아님). Codecov의 patch analysis는 PR에서 추가된 라인을 coverage.xml과 대조하는데, 없는 라인은 "미커버"로 카운트한다.

**증상:** 로컬 `pytest --cov`에서는 100%지만 Codecov patch gate가 실패.

**해결:** pragma가 모듈 레벨에 있는 파일 전체를 `.codecov.yml → ignore`에 추가:
```yaml
ignore:
  - "packages/sdk-python/src/verum/anthropic.py"
  - "packages/sdk-python/src/verum/openai.py"
```
