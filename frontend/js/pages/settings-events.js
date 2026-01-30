/**
 * Settings Page Event Bindings
 *
 * Replaces inline onclick handlers with addEventListener
 * for better CSP compliance and maintainability.
 *
 * Audit Reference: P2 onclick → addEventListener migration
 */

(function () {
  "use strict";

  /**
   * Initialize all event listeners when DOM is ready
   */
  function initSettingsEvents() {
    // Header action buttons
    bindClick('[data-action="reset-settings"]', resetSettings);
    bindClick('[data-action="save-settings"]', saveSettings);

    // Theme options
    bindClickAll(".theme-option", function () {
      const theme = this.dataset.theme;
      if (theme) selectTheme(theme);
    });

    // Color options
    bindClickAll(".color-option", function () {
      const color = this.dataset.color;
      if (color) selectColor(color);
    });

    // Toggle switches
    bindClickAll(".toggle", function () {
      this.classList.toggle("active");
    });

    // API key actions
    bindClick('[data-action="toggle-api-visibility"]', toggleApiKeyVisibility);
    bindClick('[data-action="copy-api-key"]', copyApiKey);
    bindClick('[data-action="test-connection"]', testConnection);

    // Cache actions
    bindClickAll('[data-action="clear-cache"]', function () {
      const cacheType = this.dataset.cacheType;
      if (cacheType) clearCache(cacheType);
    });

    // Data management
    bindClick('[data-action="export-data"]', exportData);
    bindClick('[data-action="import-data"]', importData);

    // Danger zone
    bindClick('[data-action="reset-all-settings"]', resetAllSettings);
    bindClick('[data-action="clear-all-data"]', clearAllData);
    bindClick('[data-action="delete-account"]', deleteAccount);

    // Settings navigation
    bindClickAll(".settings-nav-item", function () {
      const section = this.dataset.section;
      if (section) switchSection(section);
    });

    console.log("[Settings] Event listeners initialized");
  }

  /**
   * Helper: Bind click event to single element
   */
  function bindClick(selector, handler) {
    const el = document.querySelector(selector);
    if (el) {
      el.addEventListener("click", handler);
    }
  }

  /**
   * Helper: Bind click event to multiple elements
   */
  function bindClickAll(selector, handler) {
    const elements = document.querySelectorAll(selector);
    elements.forEach((el) => {
      el.addEventListener("click", handler);
    });
  }

  /**
   * Switch settings section
   */
  function switchSection(sectionId) {
    // Update nav
    document.querySelectorAll(".settings-nav-item").forEach((item) => {
      item.classList.remove("active");
    });
    const activeNav = document.querySelector(
      `.settings-nav-item[data-section="${sectionId}"]`,
    );
    if (activeNav) activeNav.classList.add("active");

    // Update content
    document.querySelectorAll(".settings-section").forEach((section) => {
      section.classList.remove("active");
    });
    const activeSection = document.getElementById(sectionId);
    if (activeSection) activeSection.classList.add("active");
  }

  // Initialize on DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSettingsEvents);
  } else {
    initSettingsEvents();
  }

  // Export for testing
  window.SettingsEvents = {
    init: initSettingsEvents,
    switchSection: switchSection,
  };
})();
