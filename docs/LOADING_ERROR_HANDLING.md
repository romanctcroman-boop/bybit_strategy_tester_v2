# Loading States & Error Boundaries - Implementation Guide

## Overview
Реализована полная система обработки ошибок и loading states для production readiness.

## Компоненты

### 1. ErrorBoundary (`components/ErrorBoundary.tsx`)
**Назначение:** Перехват JavaScript ошибок в дереве компонентов.

**Использование:**
```tsx
import ErrorBoundary from './components/ErrorBoundary';

// Wrap any component tree
<ErrorBoundary
  onError={(error, errorInfo) => {
    // Log to Sentry, Datadog, etc.
    console.error('Error caught:', error);
  }}
  resetKeys={[userId, backtestId]} // Reset on key change
>
  <YourComponent />
</ErrorBoundary>

// Custom fallback
<ErrorBoundary
  fallback={(error, errorInfo) => (
    <div>Custom error UI: {error.message}</div>
  )}
>
  <YourComponent />
</ErrorBoundary>
```

**Features:**
- ✅ Production-ready error boundary
- ✅ TypeScript interfaces
- ✅ Custom fallback UI support
- ✅ Error logging callback
- ✅ Automatic reset on prop changes
- ✅ Development mode stack traces

---

### 2. Loading Skeletons (`components/LoadingSkeletons.tsx`)
**Назначение:** Skeleton loaders для различных типов контента.

**Компоненты:**
- `TableSkeleton` - для data grids
- `ChartSkeleton` - для графиков (Plotly, TradingView)
- `CardSkeleton` - для карточек
- `ListSkeleton` - для списков
- `MetricsSkeleton` - для метрик/статистики
- `BacktestListSkeleton` - для списка бэктестов

**Использование:**
```tsx
import { ChartSkeleton, BacktestListSkeleton } from './components/LoadingSkeletons';

{isLoading ? (
  <ChartSkeleton height={400} />
) : (
  <PlotlyChart data={data} />
)}

{loading ? (
  <BacktestListSkeleton count={5} />
) : (
  <BacktestList backtests={backtests} />
)}
```

---

### 3. Global Axios Interceptor (`services/apiInterceptor.ts`)
**Назначение:** Глобальная обработка ошибок API + toast notifications.

**Features:**
- ✅ Автоматические toast уведомления для ошибок
- ✅ Обработка 401 (auth errors)
- ✅ Обработка 422 (validation errors)
- ✅ Обработка 5xx (server errors)
- ✅ Network error detection
- ✅ Request/response logging (dev mode)
- ✅ Retry logic с exponential backoff

**Автоматическая инициализация:**
Импортируется в `main.tsx` перед рендером:
```tsx
import './services/apiConfig';
```

**Manual usage:**
```tsx
import { setupAxiosInterceptors, setupRetryLogic } from './services/apiInterceptor';
import api from './services/api';

// Setup interceptors
setupAxiosInterceptors(api);
setupRetryLogic(api, 3); // 3 retries
```

---

### 4. Toast Notifications (notistack)
**Назначение:** Глобальная система toast notifications.

**Зависимость:**
```bash
npm install notistack
```

**Интеграция через GlobalProviders:**
```tsx
import GlobalProviders from './components/GlobalProviders';

<GlobalProviders>
  <App />
</GlobalProviders>
```

**Manual usage в компонентах:**
```tsx
import { enqueueSnackbar } from 'notistack';

// Success
enqueueSnackbar('Данные сохранены', { variant: 'success' });

// Error
enqueueSnackbar('Ошибка загрузки', { variant: 'error' });

// Warning
enqueueSnackbar('Внимание: данные устарели', { variant: 'warning' });

// Info
enqueueSnackbar('Обработка может занять время', { variant: 'info' });
```

---

### 5. GlobalProviders (`components/GlobalProviders.tsx`)
**Назначение:** Wrapper для всех глобальных провайдеров.

**Включает:**
- ErrorBoundary (top-level)
- SnackbarProvider (notistack)
- NotificationsProvider (existing custom)

**Использование:**
```tsx
// App.tsx
import GlobalProviders from './components/GlobalProviders';

const App = () => (
  <GlobalProviders>
    {/* Your app content */}
  </GlobalProviders>
);
```

---

## Интеграция в существующие страницы

### BacktestsPage.tsx
```tsx
import { BacktestListSkeleton } from '../components/LoadingSkeletons';
import ErrorBoundary from '../components/ErrorBoundary';

const BacktestsPage = () => {
  const [loading, setLoading] = useState(true);
  const [backtests, setBacktests] = useState([]);

  return (
    <ErrorBoundary>
      {loading ? (
        <BacktestListSkeleton count={5} />
      ) : (
        <BacktestList data={backtests} />
      )}
    </ErrorBoundary>
  );
};
```

### BacktestDetailPage.tsx
```tsx
import { ChartSkeleton, MetricsSkeleton } from '../components/LoadingSkeletons';
import ErrorBoundary from '../components/ErrorBoundary';

const BacktestDetailPage = () => {
  return (
    <ErrorBoundary resetKeys={[backtestId]}>
      <Suspense fallback={<MetricsSkeleton />}>
        <BacktestMetrics id={backtestId} />
      </Suspense>

      <Suspense fallback={<ChartSkeleton height={500} />}>
        <PlotlyEquityCurve data={chartData} />
      </Suspense>
    </ErrorBoundary>
  );
};
```

---

## Perplexity AI Recommendations

Based on consultation with Perplexity AI (via MCP Server):

### Best Practices:
1. ✅ **ErrorBoundary placement:** At route level and around critical widgets
2. ✅ **Suspense boundaries:** At logical UI boundaries, not at top level
3. ✅ **Skeleton loaders:** Match the structure of actual content
4. ✅ **Toast notifications:** Auto-dismiss in 5s, max 3 visible
5. ✅ **Retry logic:** 3 attempts with exponential backoff (1s, 2s, 4s)
6. ✅ **Error logging:** Production errors should go to external service (Sentry, Datadog)

### Production Checklist:
- [ ] Test all error scenarios (network, 401, 422, 500)
- [ ] Verify skeleton loaders match actual content layout
- [ ] Check ErrorBoundary fallback UI on all pages
- [ ] Test retry logic with intermittent failures
- [ ] Configure production error logging service
- [ ] Test toast notifications don't stack excessively
- [ ] Verify Suspense fallbacks show during code splitting

---

## Next Steps

1. **Integrate skeletons** в существующие pages:
   - BacktestsPage → BacktestListSkeleton
   - BacktestDetailPage → ChartSkeleton, MetricsSkeleton
   - Dashboard → CardSkeleton
   - AI Studio → ListSkeleton

2. **Add ErrorBoundaries** на route level:
   - Wrap each Route с ErrorBoundary
   - Add resetKeys для автоматического reset

3. **Test error scenarios:**
   - Network disconnect
   - API 500 errors
   - Component crashes
   - Retry logic

4. **Configure Sentry** (optional):
   ```bash
   npm install @sentry/react
   ```
   ```tsx
   import * as Sentry from '@sentry/react';

   Sentry.init({
     dsn: 'YOUR_SENTRY_DSN',
     environment: import.meta.env.MODE,
   });
   ```

---

## Architecture Diagram

```
┌─────────────────────────────────────────┐
│         GlobalProviders                  │
│  ┌────────────────────────────────────┐ │
│  │      ErrorBoundary (top-level)     │ │
│  │  ┌──────────────────────────────┐  │ │
│  │  │   SnackbarProvider           │  │ │
│  │  │  ┌────────────────────────┐  │  │ │
│  │  │  │ NotificationsProvider  │  │  │ │
│  │  │  │  ┌──────────────────┐  │  │  │ │
│  │  │  │  │   App Component  │  │  │  │ │
│  │  │  │  │                  │  │  │  │ │
│  │  │  │  │  - Routes        │  │  │  │ │
│  │  │  │  │  - Suspense      │  │  │  │ │
│  │  │  │  │  - Lazy pages    │  │  │  │ │
│  │  │  │  └──────────────────┘  │  │  │ │
│  │  │  └────────────────────────┘  │  │ │
│  │  └──────────────────────────────┘  │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘

API Flow:
┌──────────┐     ┌──────────────────┐     ┌──────────┐
│ Component│ ──> │ Axios Interceptor│ ──> │ Backend  │
│          │     │ - Request log    │     │   API    │
│          │     │ - Auth token     │     │          │
│          │ <── │ - Error toast    │ <── │          │
│          │     │ - Retry logic    │     │          │
└──────────┘     └──────────────────┘     └──────────┘
```

---

## Status: ✅ COMPLETED

- ✅ ErrorBoundary component created
- ✅ Loading Skeletons library created
- ✅ Global Axios interceptor configured
- ✅ notistack toast system integrated
- ✅ GlobalProviders wrapper created
- ✅ API configuration initialized in main.tsx
- ✅ App.tsx updated with GlobalProviders
- ✅ Suspense fallbacks improved
- ✅ All TypeScript errors resolved

**Ready for integration into existing pages! 🎉**
