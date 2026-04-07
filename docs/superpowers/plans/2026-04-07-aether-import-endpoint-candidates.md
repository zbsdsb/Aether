# Aether Import Endpoint Candidates Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the all-in-hub importer to create rule-based candidate endpoints and let Provider details prefill the existing user-auth dialog from imported credentials.

**Architecture:** Keep the current all-in-hub import split between direct plaintext keys and pending import tasks, but replace the single hard-coded endpoint path with a reusable candidate resolver. Reuse the existing provider ops / `ProviderAuthDialog` flow by adding a small backend prefill endpoint and a frontend draft handoff from `ProviderDetailDrawer` to the existing auth dialog instead of building any new credentials UI.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Pydantic, Vue 3, TypeScript, Vitest, pytest, existing provider ops architecture registry

---

## File Map

- Create: `src/services/provider_import/endpoint_candidates.py`
- Create: `tests/services/test_all_in_hub_endpoint_candidates.py`
- Create: `tests/api/test_admin_provider_ops_import_prefill.py`
- Create: `frontend/src/features/providers/utils/imported-auth-prefill.ts`
- Create: `frontend/src/features/providers/utils/__tests__/imported-auth-prefill.spec.ts`
- Modify: `src/services/provider_import/all_in_hub.py`
- Modify: `tests/services/test_all_in_hub_import.py`
- Modify: `src/api/admin/provider_ops/routes.py`
- Modify: `src/api/admin/providers/routes.py` only if importer-specific response models or helper reuse are needed
- Modify: `frontend/src/api/providerOps.ts`
- Modify: `frontend/src/features/providers/components/ProviderAuthDialog.vue`
- Modify: `frontend/src/features/providers/components/ProviderDetailDrawer.vue`
- Modify: `frontend/src/views/admin/ProviderManagement.vue`

## Chunk 1: Candidate Endpoint Resolver And Importer Wiring

### Task 1: Add candidate endpoint resolver unit tests

**Files:**
- Create: `tests/services/test_all_in_hub_endpoint_candidates.py`
- Reference: `docs/superpowers/specs/2026-04-07-aether-import-endpoint-candidates-design.md`

- [ ] **Step 1: Write failing unit tests for candidate resolution**

Add tests covering:

```python
def test_default_candidates_include_openai_triplet() -> None:
    candidates = resolve_endpoint_candidates(site_type=None, hints={})
    assert [c.api_format for c in candidates] == [
        "openai:chat",
        "openai:cli",
        "openai:compact",
    ]


def test_candidates_append_claude_when_claude_hint_present() -> None:
    candidates = resolve_endpoint_candidates(site_type="anthropic-compatible", hints={"claude": True})
    assert [c.api_format for c in candidates] == [
        "openai:chat",
        "openai:cli",
        "openai:compact",
        "claude:chat",
        "claude:cli",
    ]


def test_candidates_append_gemini_when_gemini_hint_present() -> None:
    candidates = resolve_endpoint_candidates(site_type="gemini-compatible", hints={"gemini": True})
    assert [c.api_format for c in candidates] == [
        "openai:chat",
        "openai:cli",
        "openai:compact",
        "gemini:chat",
        "gemini:cli",
    ]


def test_candidates_do_not_add_cross_family_without_hint() -> None:
    candidates = resolve_endpoint_candidates(site_type="openai-compatible", hints={})
    assert all(c.api_format not in {"claude:chat", "claude:cli", "gemini:chat", "gemini:cli"} for c in candidates)
```

- [ ] **Step 2: Run the new unit tests and confirm they fail**

Run:

```bash
uv run python -m pytest tests/services/test_all_in_hub_endpoint_candidates.py -v
```

Expected: `FAIL` because `resolve_endpoint_candidates` does not exist yet.

- [ ] **Step 3: Implement the minimal candidate resolver**

Create `src/services/provider_import/endpoint_candidates.py` with:

- a small dataclass or typed structure holding `api_format`, `api_family`, `endpoint_kind`, `reason`
- canonical default candidates:
  - `openai:chat`
  - `openai:cli`
  - `openai:compact`
- helper logic that inspects importer hints and appends:
  - `claude:chat`, `claude:cli`
  - `gemini:chat`, `gemini:cli`
- dedupe + stable ordering

Keep heuristics minimal:

- explicit `site_type` / `apiType` / model-name hints from importer input
- no active probing
- no video endpoints

- [ ] **Step 4: Re-run resolver unit tests**

Run:

```bash
uv run python -m pytest tests/services/test_all_in_hub_endpoint_candidates.py -v
```

Expected: `PASS`.

- [ ] **Step 5: Commit after approval**

```bash
git add src/services/provider_import/endpoint_candidates.py tests/services/test_all_in_hub_endpoint_candidates.py
git commit -m "feat: 增加导入候选端点解析器"
```

Only do this if the user has approved commits for this rollout.

### Task 2: Replace single-endpoint importer creation with resolver output

**Files:**
- Modify: `src/services/provider_import/all_in_hub.py`
- Modify: `tests/services/test_all_in_hub_import.py`
- Reference: `src/core/api_format/metadata.py`

- [ ] **Step 1: Add failing importer tests for multi-endpoint creation**

Extend `tests/services/test_all_in_hub_import.py` with cases like:

```python
async def test_execute_import_creates_default_openai_candidate_endpoints() -> None:
    result = await execute_all_in_hub_import(payload, db=fake_db)
    endpoint_formats = sorted(ep.api_format for ep in fake_db.endpoints)
    assert endpoint_formats == ["openai:chat", "openai:cli", "openai:compact"]


async def test_execute_import_enables_format_conversion_for_imported_custom_provider() -> None:
    await execute_all_in_hub_import(payload, db=fake_db)
    assert fake_db.providers[0].enable_format_conversion is True


async def test_execute_import_adds_claude_candidates_when_record_contains_claude_hint() -> None:
    await execute_all_in_hub_import(payload_with_claude_hint, db=fake_db)
    endpoint_formats = sorted(ep.api_format for ep in fake_db.endpoints)
    assert "claude:chat" in endpoint_formats
    assert "claude:cli" in endpoint_formats
```

- [ ] **Step 2: Run the focused importer tests and confirm failure**

Run:

```bash
uv run python -m pytest tests/services/test_all_in_hub_import.py -k "candidate_endpoints or format_conversion" -v
```

Expected: `FAIL` because importer still creates only one `openai:chat` endpoint and leaves conversion disabled.

- [ ] **Step 3: Implement importer wiring**

In `src/services/provider_import/all_in_hub.py`:

- replace `_find_existing_endpoint()` with helpers that work per `api_format`, not just `openai:chat`
- call `resolve_endpoint_candidates(...)`
- create one `ProviderEndpoint` per returned candidate
- set `body_rules` via `get_default_body_rules_for_endpoint(candidate.api_format, provider_type=provider.provider_type)` where appropriate
- keep endpoints `is_active=True` unless the existing system explicitly requires a different default
- set imported custom providers to `enable_format_conversion=True`
- ensure duplicate imports reuse existing endpoints per `provider_id + api_format`

Do not:

- add any probing
- add video endpoints
- rewrite pending task semantics

- [ ] **Step 4: Re-run importer tests**

Run:

```bash
uv run python -m pytest tests/services/test_all_in_hub_import.py -k "candidate_endpoints or format_conversion" -v
```

Expected: `PASS`.

- [ ] **Step 5: Run broader importer regression tests**

Run:

```bash
uv run python -m pytest tests/services/test_all_in_hub_import.py tests/api/test_admin_all_in_hub_import_routes.py -v
```

Expected: all relevant importer tests `PASS`.

- [ ] **Step 6: Commit after approval**

```bash
git add src/services/provider_import/all_in_hub.py tests/services/test_all_in_hub_import.py tests/api/test_admin_all_in_hub_import_routes.py
git commit -m "feat: 扩展导入器候选端点创建规则"
```

Only do this if the user has approved commits for this rollout.

## Chunk 2: Backend Bridge From Imported Credentials To Provider Auth Prefill

### Task 3: Add backend prefill endpoint tests

**Files:**
- Create: `tests/api/test_admin_provider_ops_import_prefill.py`
- Reference: `src/api/admin/provider_ops/routes.py`
- Reference: `src/models/database.py`

- [ ] **Step 1: Write failing API tests for imported auth prefill**

Add tests for:

```python
def test_get_imported_auth_prefill_returns_new_api_payload(client, seeded_import_task):
    resp = client.get(f"/api/admin/provider-ops/providers/{provider_id}/imported-auth-prefill")
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["architecture_id"] == "new_api"
    assert data["draft"]["credentials"]["cookie"] == "session=abc"
    assert data["draft"]["credentials"]["api_key"] == "tok-123"
    assert data["draft"]["credentials"]["user_id"] == "42"


def test_get_imported_auth_prefill_returns_available_false_without_import_task(client, provider_id):
    resp = client.get(f"/api/admin/provider-ops/providers/{provider_id}/imported-auth-prefill")
    assert resp.status_code == 200
    assert resp.json()["available"] is False
```

- [ ] **Step 2: Run the new backend prefill tests and confirm failure**

Run:

```bash
uv run python -m pytest tests/api/test_admin_provider_ops_import_prefill.py -v
```

Expected: `FAIL` because the route does not exist yet.

- [ ] **Step 3: Implement imported-auth prefill backend route**

Modify `src/api/admin/provider_ops/routes.py` to add:

- `GET /api/admin/provider-ops/providers/{provider_id}/imported-auth-prefill`

Route behavior:

- locate the latest relevant `ProviderImportTask` for the provider
- decrypt `credential_payload`
- read `source_metadata`
- infer best-effort architecture:
  - start with `new_api` when task metadata or site type matches New API style
  - allow future extension for other architectures, but keep scope minimal now
- return a draft payload shaped for the existing frontend save flow:
  - `available`
  - `architecture_id`
  - `base_url`
  - `connector.auth_type`
  - `connector.config`
  - `connector.credentials`
  - lightweight source summary for UI labels

Keep it read-only:

- do not save config
- do not mutate tasks
- do not expose credentials unless admin-authenticated and explicitly requested through this route

- [ ] **Step 4: Re-run backend prefill tests**

Run:

```bash
uv run python -m pytest tests/api/test_admin_provider_ops_import_prefill.py -v
```

Expected: `PASS`.

- [ ] **Step 5: Run provider ops regression tests**

Run:

```bash
uv run python -m pytest tests/services/test_provider_ops_service_verify_auth.py tests/api/test_admin_provider_ops_import_prefill.py -v
```

Expected: `PASS`.

- [ ] **Step 6: Commit after approval**

```bash
git add src/api/admin/provider_ops/routes.py tests/api/test_admin_provider_ops_import_prefill.py
git commit -m "feat: 增加导入凭证预填充接口"
```

Only do this if the user has approved commits for this rollout.

## Chunk 3: Frontend Draft Mapping And Detail-Drawer Handoff

### Task 4: Add frontend imported-auth prefill utility tests

**Files:**
- Create: `frontend/src/features/providers/utils/imported-auth-prefill.ts`
- Create: `frontend/src/features/providers/utils/__tests__/imported-auth-prefill.spec.ts`

- [ ] **Step 1: Write failing utility tests**

Add tests like:

```ts
it('maps imported new_api draft into dialog form shape', () => {
  const draft = buildImportedAuthDraft({
    architecture_id: 'new_api',
    base_url: 'https://demo.example',
    connector: {
      auth_type: 'api_key',
      config: {},
      credentials: { cookie: 'session=abc', api_key: 'tok-123', user_id: '42' },
    },
  })

  expect(draft.formData.base_url).toBe('https://demo.example')
  expect(draft.formData.cookie).toBe('session=abc')
  expect(draft.formData.api_key).toBe('tok-123')
  expect(draft.formData.user_id).toBe('42')
})
```

- [ ] **Step 2: Run frontend utility tests and confirm failure**

Run:

```bash
cd frontend && npm run test:run -- imported-auth-prefill.spec.ts
```

Expected: `FAIL` because the utility does not exist yet.

- [ ] **Step 3: Implement the utility**

In `frontend/src/features/providers/utils/imported-auth-prefill.ts`:

- normalize backend prefill payload into a simple draft object for `ProviderAuthDialog`
- preserve architecture id, auth type, base URL, and credentials
- avoid any schema-specific mutation that already belongs in `ProviderAuthDialog`

- [ ] **Step 4: Re-run frontend utility tests**

Run:

```bash
cd frontend && npm run test:run -- imported-auth-prefill.spec.ts
```

Expected: `PASS`.

- [ ] **Step 5: Commit after approval**

```bash
git add frontend/src/features/providers/utils/imported-auth-prefill.ts frontend/src/features/providers/utils/__tests__/imported-auth-prefill.spec.ts
git commit -m "feat: 增加导入凭证预填充前端工具"
```

Only do this if the user has approved commits for this rollout.

### Task 5: Wire Provider detail drawer to existing auth dialog

**Files:**
- Modify: `frontend/src/api/providerOps.ts`
- Modify: `frontend/src/features/providers/components/ProviderAuthDialog.vue`
- Modify: `frontend/src/features/providers/components/ProviderDetailDrawer.vue`
- Modify: `frontend/src/views/admin/ProviderManagement.vue`

- [ ] **Step 1: Add failing frontend interaction coverage or focused utility-level assertions**

If there is no existing component-test harness for these components, add a small test at the API/helper layer and capture the interaction in manual verification steps. Minimum automated coverage:

- `providerOps.ts` exports a `getImportedAuthPrefill(providerId)` function
- imported draft utility can be consumed without mutating saved config

- [ ] **Step 2: Run existing frontend type check before edits**

Run:

```bash
cd frontend && npm exec --yes vue-tsc -- --noEmit
```

Expected: `PASS` before modifications.

- [ ] **Step 3: Add API client method for imported-auth prefill**

In `frontend/src/api/providerOps.ts`:

- add response type for imported prefill
- add `getImportedAuthPrefill(providerId)`

- [ ] **Step 4: Extend `ProviderAuthDialog` to accept a one-shot external draft**

Modify `frontend/src/features/providers/components/ProviderAuthDialog.vue` to accept an optional prop such as:

- `prefillDraft?: ImportedAuthPrefillDraft | null`

Behavior:

- when dialog opens with a draft, load the draft into `selectedArchitectureId`, `selectedAuthType`, and `formData`
- keep existing saved-config loading behavior for normal opens
- treat prefill as editable draft, not persisted state
- do not auto-save or auto-verify

- [ ] **Step 5: Add Provider detail action**

Modify `frontend/src/features/providers/components/ProviderDetailDrawer.vue` to:

- fetch imported-auth prefill availability when loading provider detail
- show a small action such as `使用导入凭证填充用户认证`
- emit an event upward with the fetched draft when clicked

Suggested event:

```ts
emit('openImportedAuthPrefill', { providerId, draft })
```

- [ ] **Step 6: Connect Provider detail event to existing dialog**

Modify `frontend/src/views/admin/ProviderManagement.vue` to:

- listen for the new drawer event
- keep using the existing `ProviderAuthDialog`
- pass the imported draft into the dialog
- open the dialog without creating a second auth UI path

- [ ] **Step 7: Re-run frontend tests and type check**

Run:

```bash
cd frontend && npm run test:run -- imported-auth-prefill.spec.ts
cd frontend && npm exec --yes vue-tsc -- --noEmit
```

Expected: `PASS`.

- [ ] **Step 8: Commit after approval**

```bash
git add frontend/src/api/providerOps.ts frontend/src/features/providers/components/ProviderAuthDialog.vue frontend/src/features/providers/components/ProviderDetailDrawer.vue frontend/src/views/admin/ProviderManagement.vue
git commit -m "feat: 在提供商详情复用导入凭证填充用户认证"
```

Only do this if the user has approved commits for this rollout.

## Chunk 4: End-To-End Verification

### Task 6: Verify backend + frontend behavior together

**Files:**
- Test: `tests/services/test_all_in_hub_endpoint_candidates.py`
- Test: `tests/services/test_all_in_hub_import.py`
- Test: `tests/api/test_admin_all_in_hub_import_routes.py`
- Test: `tests/api/test_admin_provider_ops_import_prefill.py`
- Test: `frontend/src/features/providers/utils/__tests__/imported-auth-prefill.spec.ts`

- [ ] **Step 1: Run backend focused suite**

Run:

```bash
uv run python -m pytest \
  tests/services/test_all_in_hub_endpoint_candidates.py \
  tests/services/test_all_in_hub_import.py \
  tests/api/test_admin_all_in_hub_import_routes.py \
  tests/api/test_admin_provider_ops_import_prefill.py -v
```

Expected: `PASS`.

- [ ] **Step 2: Run frontend focused suite**

Run:

```bash
cd frontend && npm run test:run -- imported-auth-prefill.spec.ts
cd frontend && npm exec --yes vue-tsc -- --noEmit
```

Expected: `PASS`.

- [ ] **Step 3: Manual smoke verification**

Verify in the browser:

1. Import an OpenAI-only all-in-hub payload.
2. Open the provider detail drawer.
3. Confirm endpoint chips include `openai:chat`, `openai:cli`, `openai:compact`.
4. Confirm format conversion toggle is enabled for imported custom providers.
5. If imported credentials exist, click `使用导入凭证填充用户认证`.
6. Confirm the existing `用户认证` dialog opens with `New API` fields prefilled:
   - `站点地址`
   - `Cookie`
   - `访问令牌 (API KEY)`
   - `用户 ID`
7. Confirm save still goes through the existing provider ops flow.

- [ ] **Step 4: Optional final commit after approval**

```bash
git status --short
git add src/services/provider_import/endpoint_candidates.py src/services/provider_import/all_in_hub.py src/api/admin/provider_ops/routes.py tests/services/test_all_in_hub_endpoint_candidates.py tests/services/test_all_in_hub_import.py tests/api/test_admin_all_in_hub_import_routes.py tests/api/test_admin_provider_ops_import_prefill.py frontend/src/api/providerOps.ts frontend/src/features/providers/components/ProviderAuthDialog.vue frontend/src/features/providers/components/ProviderDetailDrawer.vue frontend/src/views/admin/ProviderManagement.vue frontend/src/features/providers/utils/imported-auth-prefill.ts frontend/src/features/providers/utils/__tests__/imported-auth-prefill.spec.ts
git commit -m "feat: 扩展导入候选端点并复用导入凭证填充认证"
```

Only do this if the user explicitly approves committing at that stage.

