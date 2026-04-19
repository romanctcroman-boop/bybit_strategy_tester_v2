/**
 * Debug Symbol Picker - вставьте в консоль браузера для отладки
 */
(async function debugSymbolPicker() {
    console.log('=== SYMBOL PICKER DEBUG START ===');

    // 1. Check elements
    const input = document.getElementById('backtestSymbol');
    const dropdown = document.getElementById('backtestSymbolDropdown');
    const marketEl = document.getElementById('builderMarketType');

    console.log('1. Elements:', {
        input: !!input,
        dropdown: !!dropdown,
        marketEl: !!marketEl,
        marketValue: marketEl?.value
    });

    // 2. Test API directly
    console.log('2. Testing API...');
    try {
        const res = await fetch('/api/v1/marketdata/symbols-list?category=linear');
        const data = await res.json();
        console.log('   API Response:', {
            status: res.status,
            symbolsCount: data.symbols?.length || 0,
            first5: data.symbols?.slice(0, 5) || []
        });
    } catch (e) {
        console.error('   API Error:', e);
    }

    // 3. Test local symbols API
    console.log('3. Testing local symbols API...');
    try {
        const res = await fetch('/api/v1/marketdata/symbols/local');
        const data = await res.json();
        console.log('   Local symbols:', {
            count: data.symbols?.length || 0,
            symbols: data.symbols || []
        });
    } catch (e) {
        console.error('   Local API Error:', e);
    }

    // 4. Check dropdown content
    if (dropdown) {
        console.log('4. Dropdown state:', {
            classList: dropdown.className,
            childrenCount: dropdown.children.length,
            innerHTML: dropdown.innerHTML.substring(0, 200) + '...'
        });
    }

    // 5. Try to trigger dropdown manually
    console.log('5. Triggering focus on input...');
    if (input) {
        input.focus();
        await new Promise(r => setTimeout(r, 1000)); // Wait 1 second
        console.log('   After focus - dropdown children:', dropdown?.children.length);
        console.log('   Dropdown classList:', dropdown?.className);
    }

    console.log('=== SYMBOL PICKER DEBUG END ===');
})();
