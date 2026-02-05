/**
 * Debug script for symbol picker
 * Добавьте этот скрипт после загрузки strategy-builder.html
 */
(function () {
    console.log('=== Symbol Picker Debug ===');

    // Проверка элементов
    const input = document.getElementById('backtestSymbol');
    const dropdown = document.getElementById('backtestSymbolDropdown');
    const marketEl = document.getElementById('builderMarketType');

    console.log('Elements found:', {
        input: !!input,
        dropdown: !!dropdown,
        marketEl: !!marketEl
    });

    if (input) {
        console.log('Input value:', input.value);
        console.log('Input visible:', input.offsetParent !== null);
        console.log('Input computed style display:', getComputedStyle(input).display);

        // Добавить обработчик для отладки
        input.addEventListener('focus', () => {
            console.log('[DEBUG] Input focused!');
        });
        input.addEventListener('click', () => {
            console.log('[DEBUG] Input clicked!');
        });
    }

    if (dropdown) {
        console.log('Dropdown classes:', dropdown.className);
        console.log('Dropdown children:', dropdown.children.length);
        console.log('Dropdown aria-hidden:', dropdown.getAttribute('aria-hidden'));
        console.log('Dropdown computed display:', getComputedStyle(dropdown).display);
        console.log('Dropdown innerHTML preview:', dropdown.innerHTML.substring(0, 200));
    }

    if (marketEl) {
        console.log('Market type value:', marketEl.value);
    }

    // Проверка кэша (если доступен)
    if (typeof bybitSymbolsCache !== 'undefined') {
        console.log('bybitSymbolsCache:', {
            linear: (bybitSymbolsCache.linear || []).length,
            spot: (bybitSymbolsCache.spot || []).length
        });
    } else {
        console.log('bybitSymbolsCache not accessible (in module scope)');
    }

    // Тестовый запрос к API
    fetch('/api/v1/marketdata/symbols-list?category=linear')
        .then(r => r.json())
        .then(data => {
            console.log('API test - symbols count:', (data.symbols || []).length);
            console.log('API test - first 5:', (data.symbols || []).slice(0, 5));
        })
        .catch(e => {
            console.error('API test failed:', e);
        });

    console.log('=== End Symbol Picker Debug ===');
})();
