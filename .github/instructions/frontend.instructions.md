---
applyTo: "**/frontend/**/*.js"
---

# Frontend JavaScript Rules

## Architecture

- All frontend files are static HTML/JS/CSS served by FastAPI
- No build step — vanilla JavaScript with ES6+ modules
- Charts: TradingView Lightweight Charts library
- API calls: `fetch()` with `async/await`

## Code Patterns

### API Call Pattern

```javascript
async function fetchData(endpoint, options = {}) {
    try {
        const response = await fetch(`/api/v1/${endpoint}`, {
            headers: { "Content-Type": "application/json" },
            ...options,
        });
        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`Failed to fetch ${endpoint}:`, error);
        showNotification(`Error: ${error.message}`, "error");
        throw error;
    }
}
```

### Event Handling

```javascript
// Use event delegation for dynamic content
document.getElementById("container").addEventListener("click", (e) => {
    const target = e.target.closest("[data-action]");
    if (!target) return;
    handleAction(target.dataset.action, target.dataset);
});
```

## Critical Rules

1. **NEVER** hardcode API URLs — always use relative paths `/api/v1/...`
2. **ALWAYS** handle loading states and errors in UI
3. **ALWAYS** validate user input before sending to API
4. **Commission rate display**: Always show as `0.07%` (matching backend 0.0007)
5. **Timeframes**: Only show the 9 valid timeframes in dropdowns
6. **strategy_builder.js** is ~3000 lines — be careful with edits, use grep to find sections

## Testing

- Use browser console for debugging
- Test with `test_frontend.py` script
- Check responsive design at 1024px, 768px, 375px widths
