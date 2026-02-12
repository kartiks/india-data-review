# India Budget App

## Overview

This is a mobile-first application built with **Expo (React Native)** and an **Express.js** backend that visualizes India's Union Budget data. The app presents budget information across multiple dimensions — revenue/receipts, expenditure/spending, deficit trends, and sector-wise allocations — using interactive charts (line, bar, donut) and cards. It supports multi-year budget data comparison with Budget Estimates (BE), Revised Estimates (RE), and Actual figures.

The app runs as a cross-platform Expo app (iOS, Android, Web) with a Node.js/Express API server that serves budget data. Data is currently served from in-memory static data files rather than a database, though Drizzle ORM and PostgreSQL are configured for future use.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend (Expo / React Native)

- **Framework**: Expo SDK 54 with expo-router v6 for file-based routing
- **Navigation**: Tab-based layout with 4 main tabs: Overview, Revenue, Spending, and Trends. Uses `expo-router` with typed routes enabled.
- **State Management**: TanStack React Query (v5) for server state — all API data is fetched and cached through query hooks
- **Fonts**: Inter font family (Google Fonts) loaded via `@expo-google-fonts/inter`
- **Charts**: Custom SVG chart components built with `react-native-svg` — LineChart, BarChart, and DonutChart in `components/charts/`
- **Styling**: Plain React Native StyleSheet with a centralized color system in `constants/colors.ts`
- **Platform Support**: iOS, Android, and Web. Uses platform-specific adaptations (e.g., `KeyboardAwareScrollViewCompat` for web vs native, blur effects for tab bar)
- **Key UI Components**: `BudgetCard`, `SectionHeader`, `YearSelector`, `ErrorBoundary`

### File-based Routing Structure

```
app/
├── _layout.tsx          # Root layout with providers (QueryClient, GestureHandler, Keyboard)
├── +not-found.tsx       # 404 screen
├── +native-intent.tsx   # Deep link redirect
├── (tabs)/              # Tab navigator group
│   ├── _layout.tsx      # Tab bar configuration (supports native liquid glass + classic)
│   ├── index.tsx        # Overview/Home tab
│   ├── revenue.tsx      # Revenue/Receipts tab
│   ├── expenditure.tsx  # Expenditure/Spending tab
│   └── trends.tsx       # Trends & Deficit tab
└── sector/
    └── [id].tsx         # Dynamic route for sector detail view
```

### Backend (Express.js)

- **Server**: Express v5 running on Node.js, entry point at `server/index.ts`
- **API Design**: RESTful JSON API with routes defined in `server/routes.ts`
- **Data Source**: Static in-memory budget data defined in `server/data/budget-data.ts`. This contains structured multi-year India budget data with receipts, expenditure, deficit, GDP, and sector-wise allocations.
- **CORS**: Dynamic CORS configuration supporting Replit dev/deploy domains and localhost for Expo web development
- **Build**: Server is bundled with esbuild for production (`server_dist/`)

### API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/budget/years` | List all available budget years |
| `GET /api/budget/year/:year` | Get full budget data for a specific year |
| `GET /api/budget/all` | Get all years' budget data |
| `GET /api/budget/sectors` | List all sectors |
| `GET /api/budget/sector/:id` | Time series data for a specific sector |
| `GET /api/budget/receipts` | Receipts time series |
| `GET /api/budget/expenditure` | Expenditure time series |
| `GET /api/budget/deficit` | Deficit time series |

### Data Layer

- **Current**: In-memory static data (`MemStorage` class in `server/storage.ts`, budget data in `server/data/budget-data.ts`)
- **Schema**: Drizzle ORM schema defined in `shared/schema.ts` with a `users` table (PostgreSQL). This is scaffolding — currently only used for user CRUD that isn't wired into the budget flows.
- **Database Config**: `drizzle.config.ts` points to PostgreSQL via `DATABASE_URL` environment variable. Run `npm run db:push` to push schema.
- **Validation**: Zod schemas generated from Drizzle schemas via `drizzle-zod`

### Development Workflow

- **Dev Mode**: Run `npm run expo:dev` (Expo) and `npm run server:dev` (Express) concurrently. The Expo app proxies API requests through the Replit dev domain.
- **Production Build**: `npm run expo:static:build` builds the web bundle, `npm run server:build` bundles the server, `npm run server:prod` runs production.
- **Database**: `npm run db:push` pushes Drizzle schema to PostgreSQL

### Key Architectural Decisions

1. **Custom SVG Charts vs Chart Library**: Charts are hand-built with `react-native-svg` instead of using a charting library. This gives full control over styling and cross-platform compatibility but requires more code for each chart type.

2. **Static Data vs Database**: Budget data is hardcoded in TypeScript files rather than stored in a database. This simplifies deployment and ensures fast responses but means data updates require code changes. The database schema exists but is only set up for user management.

3. **Shared Schema Directory**: The `shared/` directory contains schemas accessible to both frontend and backend via TypeScript path aliases (`@shared/*`).

4. **React Query for Data Fetching**: All API calls go through TanStack React Query with a centralized `queryClient` and `getQueryFn` helper that handles base URL resolution for the Replit environment.

## External Dependencies

### Infrastructure
- **PostgreSQL**: Configured via `DATABASE_URL` environment variable (Drizzle ORM + `pg` driver). Currently minimally used — schema exists but budget data is in-memory.
- **Replit**: Deployment platform. Environment variables like `REPLIT_DEV_DOMAIN`, `REPLIT_DOMAINS`, `EXPO_PUBLIC_DOMAIN` control CORS and API URL resolution.

### Key NPM Packages
- **expo** (~54.0.27): Core framework
- **expo-router** (~6.0.17): File-based routing
- **express** (^5.0.1): Backend API server
- **drizzle-orm** (^0.39.3) + **drizzle-zod**: ORM and schema validation
- **@tanstack/react-query** (^5.83.0): Data fetching and caching
- **react-native-svg** (15.12.1): Custom chart rendering
- **react-native-reanimated** (~4.1.1): Animations
- **react-native-gesture-handler** (~2.28.0): Gesture support
- **http-proxy-middleware**: Dev proxy for API requests
- **patch-package**: Applied via postinstall for dependency patches