/**
 * Sidebar Toggle Script
 * CSP-compliant (no inline scripts)
 *
 * Floating Windows — каждое окно открывается/закрывается по клику на spine.
 * Zoom controls — панель zoom перетаскивается по оси X.
 *
 * ЛОГИКА ЗАКЛАДОК:
 * - Когда окно открыто — закладки других окон скрыты/неактивны
 * - Когда все окна закрыты — все закладки видны и активны
 */

document.addEventListener('DOMContentLoaded', function () {
    // Все плавающие окна
    const windowIds = [
        'floatingWindowBasic',
        'floatingWindowEvaluation',
        'floatingWindowOptimization',
        'floatingWindowDatabase',
        'floatingWindowResults'
    ];

    // Проверить, есть ли открытое окно
    function getOpenWindowId() {
        for (let i = 0; i < windowIds.length; i++) {
            const win = document.getElementById(windowIds[i]);
            if (win && !win.classList.contains('floating-window-collapsed')) {
                return windowIds[i];
            }
        }
        return null;
    }

    // Обновить видимость всех spine (закладок)
    function updateSpinesVisibility() {
        const openWindowId = getOpenWindowId();

        windowIds.forEach(function (id) {
            const win = document.getElementById(id);
            if (!win) return;

            const spine = win.querySelector('.floating-window-spine');
            if (!spine) return;

            if (openWindowId === null) {
                // Все окна закрыты — все закладки видны и активны
                spine.classList.remove('spine-hidden');
            } else if (id === openWindowId) {
                // Это открытое окно — его закладка видна
                spine.classList.remove('spine-hidden');
            } else {
                // Другие окна — их закладки скрыты
                spine.classList.add('spine-hidden');
            }
        });
    }

    // Закрыть все окна кроме указанного
    function closeOtherWindows(exceptId) {
        windowIds.forEach(function (id) {
            if (id !== exceptId) {
                const win = document.getElementById(id);
                if (win && !win.classList.contains('floating-window-collapsed')) {
                    win.classList.add('floating-window-collapsed');
                }
            }
        });
    }

    // Переключить окно
    function toggleWindow(win) {
        if (!win) return;

        const isCollapsed = win.classList.contains('floating-window-collapsed');

        if (isCollapsed) {
            // Открыть это окно, закрыть другие
            closeOtherWindows(win.id);
            win.classList.remove('floating-window-collapsed');
        } else {
            // Закрыть это окно
            win.classList.add('floating-window-collapsed');
        }

        // Обновить видимость закладок после изменения состояния
        updateSpinesVisibility();
    }

    // Навесить обработчики на все spine
    windowIds.forEach(function (id) {
        const win = document.getElementById(id);
        if (!win) return;

        const spine = win.querySelector('.floating-window-spine');
        if (!spine) return;

        spine.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            toggleWindow(win);
        });
    });

    // Инициализировать видимость при загрузке (с небольшой задержкой для гарантии)
    updateSpinesVisibility();
    setTimeout(updateSpinesVisibility, 100);

    // Вспомогательная функция для парсинга translateX
    function parseTranslateX(el) {
        const t = (el.style.transform || '').match(/translateX\((-?\d+(?:\.\d+)?)px\)/);
        return t ? parseFloat(t[1]) : 0;
    }

    // Zoom controls — перетаскивание по оси X
    const zoomPanel = document.querySelector('.zoom-controls');
    if (zoomPanel) {
        const container = zoomPanel.closest('.canvas-area') || zoomPanel.closest('.canvas-container');
        const zoomDrag = { active: false, startX: 0, offsetX: 0 };

        zoomPanel.addEventListener('mousedown', function (e) {
            if (e.button !== 0 || e.target.closest('.zoom-btn')) return;
            e.preventDefault();
            zoomPanel.classList.add('zoom-controls-dragging');
            zoomDrag.active = true;
            zoomDrag.startX = e.clientX;
            zoomDrag.offsetX = parseTranslateX(zoomPanel);
        });

        document.addEventListener('mousemove', function (e) {
            if (!zoomDrag.active || !container) return;
            let delta = e.clientX - zoomDrag.startX;
            const rect = zoomPanel.getBoundingClientRect();
            const cRect = container.getBoundingClientRect();
            const deltaMin = cRect.left - rect.left;
            const deltaMax = cRect.right - rect.right;
            delta = Math.max(deltaMin, Math.min(deltaMax, delta));
            zoomDrag.startX = e.clientX;
            zoomDrag.offsetX += delta;
            zoomPanel.style.transform = 'translateX(' + zoomDrag.offsetX + 'px)';
        });

        document.addEventListener('mouseup', function () {
            if (zoomDrag.active) {
                zoomPanel.classList.remove('zoom-controls-dragging');
                zoomDrag.active = false;
            }
        });
    }
});
