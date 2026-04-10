# UI Reference — Agentic Ebook Platform V3

Design decisions, local dev setup, component map, and testing guide for the two frontend applications.

---

## Applications

| App | Path | Stack | Served by |
|---|---|---|---|
| Admin SPA | `apps/admin-site/` | React 19 + Vite 8 + TypeScript 6 | AWS Amplify Hosting |
| Public site | `apps/public-site/` | Astro (M7) | AWS Amplify Hosting |

---

## Admin SPA (`apps/admin-site/`)

### Technology choices

| Concern | Library | Reason |
|---|---|---|
| Build | Vite 8 | Fast HMR, native ESM, zero config |
| UI framework | React 19 | Component model, first-class TS support |
| Routing | React Router v7 | File-style routing, nested layouts |
| Server state | TanStack Query v5 | Caching, background refetch, mutation state |
| Auth | AWS Amplify Auth v6 | Official Cognito SDK, handles token refresh |
| Auth store | Zustand | Minimal global state for JWT token + email |
| HTTP client | Axios | Interceptors for JWT attach + 401 auto-refresh |
| Drag-and-drop | @dnd-kit | Accessible, pointer-friendly, composable |
| Styles | CSS Modules | Scoped styles, no runtime overhead |

No UI component library is used — plain HTML + CSS Modules keeps the bundle small and avoids version conflicts.

---

### Directory structure

```
apps/admin-site/src/
  main.tsx              ← Amplify config, QueryClient, BrowserRouter, app mount
  App.tsx               ← Route tree + ProtectedRoute guard
  index.css             ← Global tokens (CSS variables), base styles, utility classes
  types.ts              ← TypeScript types mirroring the API response shapes

  api/
    client.ts           ← Axios instance, JWT interceptor, 401 refresh + redirect
    topics.ts           ← All /admin/topics API calls

  store/
    authStore.ts        ← Zustand store: token, email, login(), logout(), refreshToken()

  components/
    Layout.tsx          ← Sidebar + <Outlet> shell for authenticated pages
    Layout.module.css

  pages/
    LoginPage.tsx       ← Email/password Cognito sign-in form
    LoginPage.module.css
    TopicListPage.tsx   ← Topic list with drag-to-reorder, run trigger, delete
    TopicListPage.module.css
    TopicFormPage.tsx   ← Create/edit form with schedule config
    TopicFormPage.module.css
```

---

### Design decisions

**CSS Modules over Tailwind / CSS-in-JS:**
Keeps styles co-located with components without runtime cost or class-name purging complexity. Global utility classes (`btn-primary`, `card`, `badge-*`, `spin`) are in `index.css` and available everywhere.

**CSS custom properties for theming:**
All colours and spacing come from `:root` variables in `index.css`. Changing the palette means editing one file.

**TanStack Query for all server state:**
Topic list, individual topic, and mutation state are all managed by React Query. Components never call `useState` for fetched data — they use `useQuery` and `useMutation`. Cache invalidation on mutation ensures the list always reflects the latest state.

**Optimistic drag-and-drop order:**
When the user drags a topic row, the local list order updates immediately (via `localOrder` state) while the `PUT /admin/topics/reorder` mutation runs in the background. If the mutation fails, the query invalidation restores the server-side order.

**ProtectedRoute pattern:**
`App.tsx` wraps authenticated routes in `<ProtectedRoute>` which reads the Zustand token. No token → redirect to `/login`. Token persists in `localStorage` via Zustand's `persist` middleware so the user stays logged in across page refreshes.

**JWT auto-refresh:**
The Axios response interceptor catches 401s, calls `Amplify.fetchAuthSession({ forceRefresh: true })`, retries the original request with the new token. If refresh fails (session expired), it redirects to `/login`.

---

### Environment variables

Stored in `apps/admin-site/.env.local` (gitignored). Copy from `.env.example`:

| Variable | Description |
|---|---|
| `VITE_API_BASE_URL` | API base URL (`http://localhost:8000` locally, AWS API GW endpoint in prod) |
| `VITE_COGNITO_USER_POOL_ID` | From Terraform output `cognito_user_pool_id` |
| `VITE_COGNITO_CLIENT_ID` | From Terraform output `cognito_client_id` |
| `VITE_AWS_REGION` | AWS region (default: `us-east-1`) |

Dev values are pre-filled in `.env.local` after `terraform apply`.

---

### Running locally

```bash
# 1. Start the backend API server (in a separate terminal)
cd services/api
pip install -r requirements.txt
uvicorn local_dev_server:app --reload --port 8000

# 2. Start the admin SPA
cd apps/admin-site
npm install        # first time only
npm run dev        # starts on http://localhost:3000
```

The Vite dev server proxies `/admin/*` and `/public/*` requests to `localhost:8000` (configured in `vite.config.ts`), so no CORS issues during local dev.

**Login credentials (dev):**
- Email: `vaibhavmaurya1986@gmail.com`
- Password: `EbookAdmin2026!`

---

### Building for production

```bash
cd apps/admin-site
npm run build
# output in dist/ — deployed to Amplify via the Amplify console or CI
```

The Amplify build spec in `infra/terraform/modules/amplify_admin_site/main.tf` runs this automatically when a branch is deployed.

---

### Deploying to AWS Amplify (manual)

```bash
cd apps/admin-site
npm run build

# Install Amplify CLI if needed
npm install -g @aws-amplify/cli

# Deploy to the Amplify app provisioned by Terraform
aws amplify start-deployment \
  --app-id d200xw9mmlu4wj \
  --branch-name dev \
  --source-url s3://... # or use the console manual deploy
```

For day-to-day development, use `npm run dev` locally — Amplify deploys are only needed when testing the production-like hosted version.

---

### Pages and routes

| Route | Component | Description |
|---|---|---|
| `/login` | `LoginPage` | Cognito email/password sign-in |
| `/topics` | `TopicListPage` | All active topics, drag-to-reorder, run trigger, delete |
| `/topics/new` | `TopicFormPage` | Create topic form |
| `/topics/:topicId/edit` | `TopicFormPage` | Edit existing topic |
| `/*` | — | Redirects to `/topics` |

Future milestones add:
- `/topics/:topicId/review/:runId` — M5 draft review screen
- `/topics/:topicId/runs` — M8 run history
- `/feedback` — M8 feedback list

---

### Planned pages (upcoming milestones)

| Milestone | Page | Notes |
|---|---|---|
| M5 | Review queue | List of drafts pending admin approval |
| M5 | Draft review | Staged draft viewer + diff + approve/reject |
| M8 | Run history | Per-topic run list with cost totals |
| M8 | Run detail | Stage-by-stage trace event timeline |
| M8 | Feedback list | Reader comments grouped by topic |

---

## Testing the Admin SPA

### Manual smoke test checklist (local)

Run through these after any significant change:

- [ ] `/login` — sign in with dev credentials, verify redirect to `/topics`
- [ ] `/login` — wrong password, verify error message
- [ ] `/topics` — list loads, topics display with status badges
- [ ] `+ New topic` — create a topic with all fields, verify it appears in the list
- [ ] Drag a topic row to a new position — verify order updates
- [ ] Click **Edit** on a topic — verify form pre-fills with existing values
- [ ] Save edit — verify changes reflected in the list
- [ ] Click **Delete** — verify confirm dialog, topic removed from list
- [ ] Click **Run** — verify toast appears with run ID
- [ ] Sign out — verify redirect to login, protected routes inaccessible

### Verifying against real AWS (not local API)

Change `VITE_API_BASE_URL` in `.env.local` to the Terraform `api_endpoint` output:
```
VITE_API_BASE_URL=https://gcqq4kkov1.execute-api.us-east-1.amazonaws.com
```
Then restart `npm run dev`. All API calls now hit the real Lambda + DynamoDB.

### Type checking

```bash
cd apps/admin-site
npx tsc --noEmit   # type-check without building
```

### Linting

```bash
cd apps/admin-site
npm run lint
```

---

## Public Site (`apps/public-site/`)

**Status: Milestone 7 — not yet implemented.**

Stack: Astro with static export. Will be scaffolded in M7 with:
- Home page (table of contents)
- Per-topic chapter pages
- Lunr.js client-side search
- Text highlight + comment widget
- Release notes page

Design decisions for the public site will be added to this document when M7 begins.
