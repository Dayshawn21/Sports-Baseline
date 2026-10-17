# Feature: Admin-only login

**From build-plan:** feature 37a (first sub-item of 37, public read-only demo)
**Status:** complete (2026-10-15)

## Goal

Let the owner use the Admin page on a server that has `ADMIN_API_KEY` set. The
owner signs in once per browser tab with that key; the web app then sends it on
admin requests only. Anonymous visitors never see an Admin nav entry, and a
visitor who opens `/admin` sees a sign-in card and nothing else.

Today the API guards every `/admin` route (fix `api-hardening`), but the web
sends no key, so the Admin page breaks the moment a key is set.

## Design reference

No mockup. The sign-in card reuses Ant Design's `Card`, `Input.Password` and
`Button` under the app theme (`web/src/index.css`), centered on the Admin page.
No new visual design.

## In scope

- `GET /admin/session`: confirms a key, behind the existing admin guard, with
  the heavy rate limit.
- A sessionStorage-held key, attached as `X-API-Key` to `/admin` requests only,
  and cleared when an admin request answers 401.
- A sign-in card, sign-out, and the error states on the Admin page.
- The Admin nav entry shown only when signed in, or in a Vite dev build.

## Out of scope

- Passwords, server sessions, cookies or tokens: the credential is
  `ADMIN_API_KEY` itself (see Notes for why).
- More than one account, sign-up, or any per-user data (`project-plan.md` §2).
- Guarding any non-admin route: every other page stays public and read-only.
- Production hosting concerns (web and API origins, proxying `/api`): 37d.
- Changes to what the Admin page does once signed in.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - `GET /admin/session`** - an endpoint on the admin router (so
  `require_api_key` already guards it) returning `AdminSessionResponse`
  (`keyRequired: bool`, true when the server has a key). Add `/admin/session`
  to `HEAVY_PATHS` in `app/core/rate_limits.py`, so key guesses get 10 a
  minute per client.
  - *Done when:* tests show 401 without a key and with a wrong key when one is
    set; 200 with `{"keyRequired": true}` with the right key; 200 with
    `{"keyRequired": false}` when none is set; and `rule_for_path` gives the
    heavy limit for `/admin/session`. `pytest` passes.
- [x] **Step 2 - Web key handling** - `web/src/utils/adminAuth.ts` (pure, the
  storage passed in):
  - `readAdminKey`, `storeAdminKey` (trims; an empty key is not stored),
    `clearAdminKey` over a `Storage`, each wrapped in try/catch; storage that
    throws reads as signed out
  - `adminKeyHeaders(url, key)`: `{ 'X-API-Key': key }` only for a URL
    starting `/admin`, else `{}`
  - `isAdminRejection(url, status)`: true for a 401 on an `/admin` URL

  Request and response interceptors in `web/src/api/client.ts` use them on
  `sessionStorage` (attach the header; clear the key on a rejection). Add
  `fetchAdminSession()` to `web/src/api/admin.ts` and `AdminSession` to
  `web/src/types/admin.ts`.
  - *Done when:* `adminAuth.test.ts` covers an admin URL with and without a
    key, a public URL with a key (no header), trimming and the empty key,
    store, read and clear, storage that throws, and `isAdminRejection` for 401
    versus 403, 429 and public URLs; `npm run build` and `npm run test` pass.
    No visible change yet.
- [x] **Step 3 - Sign-in gate on the Admin page** - `useAdminSession` in
  `web/src/hooks/useAdmin.ts`: a `useSyncExternalStore` over the stored key
  (so every reader updates together) plus the session query, keyed
  `['admin', 'session', { signedIn }]`, `staleTime` 5 minutes, no refetch on
  window focus, no retry on 401 or 429. `AdminPage` shows:
  - **401:** a sign-in card (password input, Sign in disabled while empty);
    after a rejected attempt, "That key was not accepted."
  - **429:** "Too many attempts. Try again in N s." from `Retry-After`
  - **any other error:** the shared `ErrorState` with retry
  - **loading:** the shared `LoadingState`
  - **200:** the existing page plus a "Sign out" button when `keyRequired` is
    true; with no server key, the page opens straight away and shows no button

  An admin request answering 401 mid-session returns to the card (step 2's
  interceptor clears the key, which re-renders the gate).
  - *Done when:* `npm run build` and `npm run test` pass; with `ADMIN_API_KEY`
    set locally, screenshots show the sign-in card, the rejected-key message,
    the signed-in page with flagged players loaded, and the card again after
    Sign out; with no key set, `/admin` opens with no card and no Sign out.
- [x] **Step 4 - Admin nav entry for the owner only** -
  `visibleNavItems(items, adminVisible)` in `sportNav.ts` drops `/admin`
  unless `adminVisible`; `App.tsx` passes signed-in or `import.meta.env.DEV`,
  for both the desktop menu and the mobile drawer. `navKeyForPath` keeps
  reading the full `NAV_ITEMS`, so `/admin` still highlights correctly.
  - *Done when:* `sportNav.test.ts` covers both cases; `npm run build` and
    `npm run test` pass; a `vite preview` build (not dev) shows no Admin entry
    while signed out, and shows it after signing in at `#/admin`, on desktop
    and in the mobile drawer.

## Files / areas

- `api/app/routers/admin.py`, `api/app/schemas/admin.py`, `api/app/core/rate_limits.py`
- `api/tests/test_admin_session.py` (new)
- `web/src/utils/adminAuth.ts` (+ test), `web/src/api/client.ts`, `web/src/api/admin.ts`,
  `web/src/types/admin.ts`, `web/src/hooks/useAdmin.ts` (new),
  `web/src/pages/AdminPage.tsx`, `web/src/utils/sportNav.ts` (+ test), `web/src/App.tsx`

## Data / contracts

No schema change, no migration.

**Load-bearing:**
- **`GET /admin/session`** returns 200 `{"keyRequired": bool}` when the caller
  may use admin routes, 401 when not, and 429 past the heavy limit. 37d's smoke
  test and any later admin feature check sign-in through it.
- **The header rule:** the web sends `X-API-Key` only on requests whose URL
  starts `/admin`. Never on public routes, never in a URL or query string, and
  never logged.
- **Storage:** sessionStorage key `sportapp.adminKey`. Closing the tab signs
  the owner out; rotating `ADMIN_API_KEY` signs them out on the next admin
  request.

## Testing

Test gate on.

- **Step 1:** route tests through `TestClient` (the pattern of
  `tests/test_write_route_guard.py`), and a `rule_for_path` test.
- **Step 2:** `adminAuth.test.ts`, with a stub `Storage` rather than the real
  `sessionStorage`.
- **Step 4:** `visibleNavItems` in `sportNav.test.ts`.
- **Steps 3 and 4 UI:** screenshots plus the build, per the standards (no
  component tests).

## Notes for the AI

- **Why the key itself, not a password and cookie session:** one owner, one
  secret that already exists and is already enforced at 32+ characters in
  production. A cookie session would add a session secret, CSRF handling, and
  cross-site cookie rules for 37d's separate web and API origins, for no gain
  with one user. Revisit only if accounts ever arrive (`project-plan.md` §2).
- **sessionStorage, not localStorage:** the key leaves when the tab closes. The
  page loads no third-party scripts, and React escapes rendered text, which is
  the XSS exposure that matters here.
- **Dev stays frictionless:** with no server key, `keyRequired` is false and
  the page opens straight away. Production cannot run without a key (the
  hardening fix's startup check), so a production visitor always hits the card.
- **Rate limit:** the session check is the only route a guesser needs, so it
  takes the heavy limit. A 32+ character key is not guessable anyway; the limit
  keeps the logs quiet. The 5-minute `staleTime` keeps the owner well under 10
  checks a minute.
- `useSyncExternalStore` needs a subscribe function. Dispatch a custom window
  event on store and clear, since the `storage` event only fires in other tabs.
- The Admin page calls `~/api/admin` directly through react-query today. Keep
  that, and put only the new session hook in `useAdmin.ts`; moving the existing
  calls into hooks is out of scope.
- Start the API with the Windows selector event loop for live checks (plain
  `uvicorn` fails on this machine with psycopg async).
- No UI text under 11px. No em dashes in new text.

## Outcome (2026-10-15)

- **Checks:** `pytest` 2567 passed (4 new session tests, `/admin/session` in
  the heavy-route test); `npm run build` succeeded; `npm run test` passed 44
  files and 527 tests (`adminAuth`, `httpError` and `visibleNavItems` tests).
- **Live (Playwright in Edge, test API with a key on port 8010):**
  - dev build: sign-in card with Sign in disabled while empty; a wrong key
    shows "That key was not accepted." and stores nothing; the right key loads
    the flagged players; navigating away and back stays signed in; Sign out
    returns to the card with no key stored; no public request carried
    `X-API-Key`
  - no server key: `/admin` opens with no card and no Sign out
  - `vite preview` build: the Admin entry is hidden while signed out, shown
    after sign-in, hidden after Sign out, on desktop and in the mobile drawer
- **Departures from the spec:**
  - the admin URL test is `/admin` exactly or `/admin/...`, so a path like
    `/administrators` never gets the key
  - added `web/src/vite-env.d.ts` (Vite's standard client types), which the
    project lacked, so `import.meta.env.DEV` typechecks
  - the sign-in card lives in `web/src/components/admin/AdminSignIn.tsx`, and
    `httpStatus`, `retryAfterSeconds` and `retryUnlessAuthOrLimited` joined
    `web/src/utils/httpError.ts`
- **Noted:** a wrong key costs two session checks (the rejected check clears
  the key, then the gate re-checks without one), so about 5 wrong attempts fit
  in the 10-a-minute limit.
- **Playwright's bundled Chromium is not installed** on this machine; the checks
  used the system Edge (`channel="msedge"`).
- **Interview guide:** the public-access answer now describes the owner-only
  sign-in.
