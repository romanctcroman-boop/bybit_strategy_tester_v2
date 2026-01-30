/**
 * Sidebar Toggle Script
 * CSP-compliant (no inline scripts)
 */

document.addEventListener('DOMContentLoaded', function () {
    // Timers
    let autoCloseTimer = null;
    let sidebarInactivityTimer = null;
    let lastOpenedSection = null;

    // Constants
    const SECTION_AUTO_CLOSE_DELAY = 1000;
    const SIDEBAR_INACTIVITY_DELAY = 1000;

    const sidebar = document.getElementById('sidebarRight');
    const toggleBtn = document.getElementById('toggleRightSidebarBtn');

    if (sidebar) {
        sidebar.classList.add('collapsed');
        const allSections = sidebar.querySelectorAll('.properties-section');
        allSections.forEach(function (section, index) {
            if (index === 0) {
                section.classList.remove('collapsed');
            } else {
                section.classList.add('collapsed');
            }
        });
    }

    function resetInactivityTimer() {
        if (sidebarInactivityTimer) {
            clearTimeout(sidebarInactivityTimer);
        }
        if (sidebar && !sidebar.classList.contains('collapsed')) {
            sidebarInactivityTimer = setTimeout(function () {
                collapseSidebar();
            }, SIDEBAR_INACTIVITY_DELAY);
        }
    }

    function collapseSidebar() {
        if (!sidebar || sidebar.classList.contains('collapsed')) return;
        sidebar.classList.add('collapsed');
        const allSections = sidebar.querySelectorAll('.properties-section');
        allSections.forEach(function (section) {
            section.classList.add('collapsed');
        });
        if (autoCloseTimer) {
            clearTimeout(autoCloseTimer);
            autoCloseTimer = null;
        }
        if (sidebarInactivityTimer) {
            clearTimeout(sidebarInactivityTimer);
            sidebarInactivityTimer = null;
        }
        lastOpenedSection = null;
    }

    let isMouseOverSidebar = false;

    if (sidebar) {
        sidebar.addEventListener('mouseleave', function (e) {
            const rect = sidebar.getBoundingClientRect();
            const isReallyOutside = e.clientX < rect.left || e.clientX > rect.right || e.clientY < rect.top || e.clientY > rect.bottom;
            if (isReallyOutside) {
                isMouseOverSidebar = false;
                if (sidebarInactivityTimer) clearTimeout(sidebarInactivityTimer);
                if (!sidebar.classList.contains('collapsed')) {
                    sidebarInactivityTimer = setTimeout(function () {
                        if (!isMouseOverSidebar) collapseSidebar();
                    }, SIDEBAR_INACTIVITY_DELAY);
                }
            }
        });

        sidebar.addEventListener('mouseenter', function () {
            isMouseOverSidebar = true;
            if (sidebarInactivityTimer) {
                clearTimeout(sidebarInactivityTimer);
                sidebarInactivityTimer = null;
            }
        });

        sidebar.addEventListener('mousemove', function () {
            isMouseOverSidebar = true;
            if (sidebarInactivityTimer) {
                clearTimeout(sidebarInactivityTimer);
                sidebarInactivityTimer = null;
            }
        });

        sidebar.addEventListener('scroll', function () {
            if (sidebarInactivityTimer) {
                clearTimeout(sidebarInactivityTimer);
                sidebarInactivityTimer = null;
            }
        }, true);

        sidebar.addEventListener('click', function () {
            if (sidebarInactivityTimer) {
                clearTimeout(sidebarInactivityTimer);
                sidebarInactivityTimer = null;
            }
        }, true);
    }

    if (toggleBtn) {
        toggleBtn.addEventListener('click', function () {
            if (!sidebar) return;
            const isCollapsed = sidebar.classList.contains('collapsed');
            if (isCollapsed) {
                sidebar.classList.remove('collapsed');
            } else {
                collapseSidebar();
            }
        });
    }

    const leftSidebar = document.getElementById('sidebarLeft');
    const toggleLeftBtn = document.getElementById('toggleLeftSidebarBtn');
    let leftSidebarInactivityTimer = null;
    const LEFT_SIDEBAR_INACTIVITY_DELAY = 1000;

    function resetLeftInactivityTimer() {
        if (leftSidebarInactivityTimer) clearTimeout(leftSidebarInactivityTimer);
        if (leftSidebar && !leftSidebar.classList.contains('collapsed')) {
            leftSidebarInactivityTimer = setTimeout(function () {
                collapseLeftSidebarInternal();
            }, LEFT_SIDEBAR_INACTIVITY_DELAY);
        }
    }

    function collapseLeftSidebarInternal() {
        if (!leftSidebar || leftSidebar.classList.contains('collapsed')) return;
        leftSidebar.classList.add('collapsed');
        if (leftSidebarInactivityTimer) {
            clearTimeout(leftSidebarInactivityTimer);
            leftSidebarInactivityTimer = null;
        }
    }

    let isMouseOverLeftSidebar = false;

    if (leftSidebar) {
        leftSidebar.addEventListener('mouseleave', function (e) {
            const rect = leftSidebar.getBoundingClientRect();
            const isReallyOutside = e.clientX < rect.left || e.clientX > rect.right || e.clientY < rect.top || e.clientY > rect.bottom;
            if (isReallyOutside) {
                isMouseOverLeftSidebar = false;
                if (leftSidebarInactivityTimer) clearTimeout(leftSidebarInactivityTimer);
                if (!leftSidebar.classList.contains('collapsed')) {
                    leftSidebarInactivityTimer = setTimeout(function () {
                        if (!isMouseOverLeftSidebar) collapseLeftSidebar();
                    }, LEFT_SIDEBAR_INACTIVITY_DELAY);
                }
            }
        });

        leftSidebar.addEventListener('mouseenter', function () {
            isMouseOverLeftSidebar = true;
            if (leftSidebarInactivityTimer) {
                clearTimeout(leftSidebarInactivityTimer);
                leftSidebarInactivityTimer = null;
            }
        });

        leftSidebar.addEventListener('mousemove', function () {
            isMouseOverLeftSidebar = true;
            if (leftSidebarInactivityTimer) {
                clearTimeout(leftSidebarInactivityTimer);
                leftSidebarInactivityTimer = null;
            }
        });

        leftSidebar.addEventListener('scroll', function () {
            if (leftSidebarInactivityTimer) {
                clearTimeout(leftSidebarInactivityTimer);
                leftSidebarInactivityTimer = null;
            }
        }, true);

        leftSidebar.addEventListener('click', function () {
            if (leftSidebarInactivityTimer) {
                clearTimeout(leftSidebarInactivityTimer);
                leftSidebarInactivityTimer = null;
            }
        }, true);
    }

    if (toggleLeftBtn) {
        toggleLeftBtn.addEventListener('click', function () {
            if (!leftSidebar) return;
            const isCollapsed = leftSidebar.classList.contains('collapsed');
            if (isCollapsed) {
                leftSidebar.classList.remove('collapsed');
            } else {
                collapseLeftSidebar();
            }
        });
    }

    const sectionHeaders = document.querySelectorAll('.properties-section-header');
    sectionHeaders.forEach(function (header) {
        header.addEventListener('click', function () {
            const section = this.closest('.properties-section');
            if (!section) return;
            resetInactivityTimer();
            const isCurrentlyCollapsed = section.classList.contains('collapsed');
            if (isCurrentlyCollapsed) {
                section.classList.remove('collapsed');
                if (lastOpenedSection && lastOpenedSection !== section) {
                    if (autoCloseTimer) clearTimeout(autoCloseTimer);
                    const sectionToClose = lastOpenedSection;
                    autoCloseTimer = setTimeout(function () {
                        sectionToClose.classList.add('collapsed');
                    }, SECTION_AUTO_CLOSE_DELAY);
                }
                lastOpenedSection = section;
            } else {
                section.classList.add('collapsed');
                if (lastOpenedSection === section) {
                    if (autoCloseTimer) {
                        clearTimeout(autoCloseTimer);
                        autoCloseTimer = null;
                    }
                    lastOpenedSection = null;
                }
            }
        });
    });

    let categoryAutoCloseTimer = null;
    let lastOpenedCategory = null;

    document.addEventListener('click', function (e) {
        const header = e.target.closest('.category-header');
        if (!header) return;
        e.stopPropagation();
        const category = header.closest('.block-category');
        if (!category) return;
        resetLeftInactivityTimer();
        const isCurrentlyCollapsed = category.classList.contains('collapsed');
        if (isCurrentlyCollapsed) {
            category.classList.remove('collapsed');
            if (lastOpenedCategory && lastOpenedCategory !== category) {
                if (categoryAutoCloseTimer) clearTimeout(categoryAutoCloseTimer);
                const categoryToClose = lastOpenedCategory;
                categoryAutoCloseTimer = setTimeout(function () {
                    categoryToClose.classList.add('collapsed');
                }, SECTION_AUTO_CLOSE_DELAY);
            }
            lastOpenedCategory = category;
        } else {
            category.classList.add('collapsed');
            if (lastOpenedCategory === category) {
                if (categoryAutoCloseTimer) {
                    clearTimeout(categoryAutoCloseTimer);
                    categoryAutoCloseTimer = null;
                }
                lastOpenedCategory = null;
            }
        }
    });

    function collapseAllCategories() {
        const allCategories = document.querySelectorAll('.block-category');
        allCategories.forEach(function (cat) {
            cat.classList.add('collapsed');
        });
        if (categoryAutoCloseTimer) {
            clearTimeout(categoryAutoCloseTimer);
            categoryAutoCloseTimer = null;
        }
        lastOpenedCategory = null;
    }

    function collapseLeftSidebar() {
        collapseLeftSidebarInternal();
        collapseAllCategories();
    }
});
