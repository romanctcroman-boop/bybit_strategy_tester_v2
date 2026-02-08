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
            // Add class to body to indicate a floating window is open
            document.body.classList.add('floating-window-open');
        } else {
            // Закрыть это окно
            win.classList.add('floating-window-collapsed');
            // Check if any window is still open
            const anyOpen = windowIds.some(function (id) {
                const w = document.getElementById(id);
                return w && !w.classList.contains('floating-window-collapsed');
            });
            if (!anyOpen) {
                document.body.classList.remove('floating-window-open');
            }
        }

        // Обновить видимость закладок после изменения состояния
        updateSpinesVisibility();

        // Dispatch custom event for other components to react
        document.dispatchEvent(new CustomEvent('floatingWindowToggle', {
            detail: { windowId: win.id, isOpen: !win.classList.contains('floating-window-collapsed') }
        }));
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

    // ========================================
    // LEFT SIDEBAR (Library) Toggle
    // ========================================
    const sidebarLeft = document.getElementById('sidebarLeft');
    const toggleLeftBtn = document.getElementById('toggleLeftSidebarBtn');

    if (sidebarLeft && toggleLeftBtn) {
        // Start collapsed by default
        sidebarLeft.classList.add('collapsed');
        const arrow = toggleLeftBtn.querySelector('.tab-arrow');
        if (arrow) {
            arrow.style.transform = 'rotate(180deg)';
        }

        toggleLeftBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            sidebarLeft.classList.toggle('collapsed');

            // Rotate arrow icon
            const arrowIcon = toggleLeftBtn.querySelector('.tab-arrow');
            if (arrowIcon) {
                if (sidebarLeft.classList.contains('collapsed')) {
                    arrowIcon.style.transform = 'rotate(180deg)';
                } else {
                    arrowIcon.style.transform = 'rotate(0deg)';
                }
            }
        });
    }

    // ========================================
    // CATEGORY HEADERS Toggle (collapsible sections)
    // ========================================
    const blockCategories = document.getElementById('blockCategories');

    if (blockCategories) {
        // Event delegation for category headers
        blockCategories.addEventListener('click', function (e) {
            const header = e.target.closest('.category-header');
            if (!header) return;

            // Skip if inside a category group - handled separately
            if (header.closest('.block-category-group')) {
                return; // Let strategy_builder.js handle group subcategories
            }

            e.preventDefault();
            e.stopPropagation();

            const category = header.closest('.block-category');
            if (!category) return;

            const wasCollapsed = category.classList.contains('collapsed');
            const blockList = category.querySelector('.block-list');
            const icon = header.querySelector('i');

            // Toggle collapsed state with animation
            if (wasCollapsed) {
                // Opening - expand
                category.classList.remove('collapsed');
                if (icon) {
                    icon.classList.remove('bi-chevron-right');
                    icon.classList.add('bi-chevron-down');
                }

                // Animate block list
                if (blockList) {
                    blockList.style.display = 'flex';
                    blockList.style.maxHeight = '0';
                    blockList.style.opacity = '0';

                    // Force reflow
                    blockList.offsetHeight;

                    // Animate to full height
                    blockList.style.maxHeight = blockList.scrollHeight + 'px';
                    blockList.style.opacity = '1';

                    // After animation, remove max-height constraint
                    setTimeout(function () {
                        blockList.style.maxHeight = 'none';
                    }, 300);
                }

                // Scroll category into view
                setTimeout(function () {
                    const container = category.closest('.block-categories');
                    if (container) {
                        const categoryTop = category.offsetTop - container.offsetTop;
                        container.scrollTo({
                            top: categoryTop,
                            behavior: 'smooth'
                        });
                    }
                }, 50);
            } else {
                // Closing - collapse
                if (icon) {
                    icon.classList.remove('bi-chevron-down');
                    icon.classList.add('bi-chevron-right');
                }

                // Animate block list
                if (blockList) {
                    blockList.style.maxHeight = blockList.scrollHeight + 'px';
                    blockList.style.opacity = '1';

                    // Force reflow
                    blockList.offsetHeight;

                    // Animate to zero
                    blockList.style.maxHeight = '0';
                    blockList.style.opacity = '0';

                    // After animation, add collapsed class and hide
                    setTimeout(function () {
                        category.classList.add('collapsed');
                        blockList.style.display = 'none';
                    }, 300);
                } else {
                    category.classList.add('collapsed');
                }
            }
        });

        // Initialize ALL categories as collapsed by default
        const categories = blockCategories.querySelectorAll('.block-category');
        categories.forEach(function (cat) {
            // All categories start collapsed
            cat.classList.add('collapsed');
            const icon = cat.querySelector('.category-header i');
            if (icon) {
                icon.classList.remove('bi-chevron-down');
                icon.classList.add('bi-chevron-right');
            }
            const blockList = cat.querySelector('.block-list');
            if (blockList) {
                blockList.style.display = 'none';
                blockList.style.maxHeight = '0';
                blockList.style.opacity = '0';
            }
        });
    }

    // ========================================
    // REFRESH LIBRARY BUTTON
    // ========================================
    const refreshLibraryBtn = document.getElementById('refreshLibraryBtn');
    if (refreshLibraryBtn) {
        refreshLibraryBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();

            // Add spinning animation
            refreshLibraryBtn.classList.add('spinning');

            // Re-render block library (if function exists in global scope)
            if (typeof window.renderBlockLibrary === 'function') {
                window.renderBlockLibrary();
            }

            // Remove spinning after animation
            setTimeout(function () {
                refreshLibraryBtn.classList.remove('spinning');

                // Re-initialize ALL categories as collapsed
                const blockCategories = document.getElementById('blockCategories');
                if (blockCategories) {
                    const categories = blockCategories.querySelectorAll('.block-category');
                    categories.forEach(function (cat) {
                        const blockList = cat.querySelector('.block-list');
                        const icon = cat.querySelector('.category-header i');

                        // All collapsed
                        cat.classList.add('collapsed');
                        if (icon) {
                            icon.classList.remove('bi-chevron-down');
                            icon.classList.add('bi-chevron-right');
                        }
                        if (blockList) {
                            blockList.style.display = 'none';
                            blockList.style.maxHeight = '0';
                            blockList.style.opacity = '0';
                        }
                    });
                }
            }, 500);
        });
    }
});
