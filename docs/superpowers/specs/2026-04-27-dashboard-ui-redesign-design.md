# Dashboard UI Redesign — Design Spec

**Date:** 2026-04-27  
**Status:** Approved  
**Scope:** Full dashboard redesign — global layout, all major pages

---

## 1. Design Direction

**Style:** Clean Light SaaS (Notion / Retool / Supabase influence)  
**Navigation:** Icon sidebar (slim, 56px, left-anchored — Linear / Notion style)  
**Landing (unauthenticated):** Minimal centered login card  
**Dark mode:** Out of scope for this iteration  

---

## 2. Design Tokens

### Colors

| Token | Value | Usage |
|-------|-------|-------|
| `primary` | `#6366f1` (indigo-500) | Buttons, active nav, links |
| `primary-dark` | `#4f46e5` (indigo-600) | Hover states |
| `primary-subtle` | `#ede9fe` (indigo-100) | Active nav bg, hover bg |
| `page-bg` | `#f8fafc` (slate-50) | Page background |
| `card-bg` | `#ffffff` | Card / panel background |
| `border` | `#e2e8f0` (slate-200) | Card borders, dividers |
| `text-primary` | `#0f172a` (slate-900) | Headings, primary text |
| `text-secondary` | `#334155` (slate-700) | Body text |
| `text-muted` | `#64748b` (slate-500) | Labels, descriptions |
| `text-placeholder` | `#94a3b8` (slate-400) | Placeholder, disabled |

### Stage Colors (Verum Loop)

| Stage | Background | Border / Text |
|-------|-----------|---------------|
| ANALYZE | `#dcfce7` | `#22c55e` / `#16a34a` |
| INFER | `#ede9fe` | `#7c3aed` |
| HARVEST | `#fef3c7` | `#f59e0b` / `#b45309` |
| GENERATE | `#fee2e2` | `#ef4444` / `#dc2626` |
| DEPLOY | `#dbeafe` | `#3b82f6` / `#1d4ed8` |
| OBSERVE | `#f0fdf4` | `#22c55e` / `#16a34a` |
| EXPERIMENT | `#fdf4ff` | `#d946ef` / `#a21caf` |
| EVOLVE | `#ecfdf5` | `#10b981` / `#059669` |

### Typography

- **Body / UI text:** `system-ui, -apple-system, sans-serif`  
- **Code / technical data** (file paths, SDK names, model names, repo slugs): `monospace`  
- **Scale:** 9px labels → 10px small → 11px body → 13px default → 15–16px page titles

### Shadows

- **Card:** `0 1px 3px rgba(0,0,0,.06)` — subtle lift  
- **Login card:** `0 4px 24px rgba(99,102,241,.08)` — indigo-tinted glow  

### Border radius

- **Cards / panels:** `10–12px`  
- **Buttons:** `7px`  
- **Badges / pills:** `12px` (fully rounded)  
- **Small elements (icons, avatars):** `6–8px`

---

## 3. Global Layout

### Shell structure

```
┌──────────────────────────────────────────────┐
│  56px sidebar  │  flex-1 main content         │
│  (white, fixed)│  (slate-50 bg, scrollable)   │
└──────────────────────────────────────────────┘
```

### Icon Sidebar (56px wide, `bg-white`, `border-r border-slate-200`)

Top to bottom:
1. **Logo badge** — 32×32px indigo square with "V", `border-radius: 8px`, 16px bottom margin
2. **Nav items** (36×36px icon buttons, `border-radius: 8px`):
   - Repos — grid icon
   - Observe — eye icon  
   - Docs — file icon
3. **Spacer** (`flex: 1`)
4. **User avatar** — 28×28px circle, initials, bottom of sidebar

**Active state:** `background: #ede9fe`, icon stroke `#6366f1`  
**Hover state:** `background: #f8fafc`  
**Tooltip:** native `title` attribute on each icon button

### Implementing the layout

Create or update `apps/dashboard/src/app/layout.tsx` (Next.js App Router root layout) to:
- Checks auth (redirect to `/login` if unauthenticated)
- Renders the sidebar + `{children}` shell
- Excludes `/login` route from the shell (login page has its own full-page layout)

---

## 4. Login Page (`/login`)

**Layout:** Full viewport, `bg-slate-50`, centered card  

**Card spec:**
- Width: `max-w-sm` (384px), white bg, `border border-slate-200`, `rounded-xl`, indigo-tinted shadow
- Logo: 32×32px indigo badge + "Verum" wordmark (`font-bold`, `text-slate-900`)
- Headline: "Welcome back" (`font-semibold`, `text-slate-900`)
- Subtext: "Connect your repo. Auto-evolve your AI." (`text-slate-500`, `text-sm`)
- GitHub button: `bg-[#24292f]`, GitHub SVG icon + "Continue with GitHub", `rounded-lg`
- Disclaimer: `text-slate-300`, `text-xs`, below divider line at card bottom

---

## 5. Repos Page (`/repos`)

**Page header:**
- Title: "Repositories" (h1) + subtitle "Connect a repo to start the Verum Loop"
- CTA: "+ Connect Repo" button (indigo, top-right)

**Section: Connected repos**
- Section label: uppercase muted text "CONNECTED (N)"
- Each repo = white card, `border border-slate-200`, `rounded-xl`, `p-4`:
  - Left: GitHub icon badge (36×36, slate-100 bg)
  - Center: repo name (`font-semibold text-slate-900`) + slug (`font-mono text-slate-400 text-xs`)
  - Right: stage pills (colored, rounded-full) + chevron icon
  - Pulse dot on active/running stages

**Section: Add from GitHub**
- Section label: "ADD FROM GITHUB"
- White card with search input (magnifier icon + placeholder) + scrollable repo list
- Each item: GitHub icon + `font-mono` repo slug

**Empty state:** Centered illustration placeholder + "No repos connected yet" + "+ Connect Repo" CTA

---

## 6. Repo Detail Page (`/repos/[id]`)

**Breadcrumb:** `Repos / RepoName` — "RepoName" in indigo

**Page header:**
- Left: GitHub icon badge + repo name + `font-mono` slug + branch
- Right: "Re-analyze" (outline button) + "Activate SDK" (indigo primary button)

**Verum Loop Progress Stepper:**
- 8 circles connected by lines, horizontal, full width
- Completed: filled color circle with checkmark
- Active: colored circle with white dot + pulse animation
- Pending: slate-100 bg + slate-200 border + number
- Connector lines: colored for completed segments, slate-200 for pending

**Active Stage Card:**
- Left border accent in stage color (`border-l-4`)
- Badge (stage name) + pulse dot + status text
- Progress bar (gradient in stage color)
- Elapsed time (right-aligned, muted)

**Quick Stats Row (3 cards):**
- Call Sites: count + SDK names in monospace
- Domain: inferred domain in violet + confidence score
- Chunks: collected / target

**Below the fold:** Existing stage-specific detail sections (StagesView, ObserveSection, ExperimentSection, ActivationCard) — apply the new card/typography tokens to each.

---

## 7. Implementation Notes

### No new dependencies
All changes use existing Tailwind CSS v4 + React. No new packages.

### Migration strategy: Layout First
1. Add root `layout.tsx` with sidebar shell (affects all authenticated pages at once)
2. Restyle `/login` (isolated, no layout shell)
3. Restyle `/repos` within the new shell
4. Restyle `/repos/[id]` — stepper + active stage card + quick stats
5. Apply token cleanup to remaining pages (analyses, infer, harvest, generate, deploy)

### Inline styles → Tailwind
Replace all hardcoded inline `style={{}}` color/spacing props with Tailwind utility classes using the token mapping above.

### Existing components to update
- `StagesView.tsx` — adopt stepper UI, active stage card pattern
- `ActivationCard.tsx` — adopt new card tokens
- `ObserveSection.tsx` — keep dark recharts, wrap in white card with new header
- `ExperimentSection.tsx` — adopt new card tokens

---

## 8. Out of Scope

- Dark mode
- Mobile responsiveness (desktop-first for now)
- Animation beyond CSS transitions and pulse dots
- New features — this is purely visual rework
