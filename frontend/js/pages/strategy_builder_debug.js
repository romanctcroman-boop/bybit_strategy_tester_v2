/**
 * Debug helper for Strategy Builder
 * Проверяет наличие всех необходимых элементов на странице
 */

document.addEventListener("DOMContentLoaded", function() {
  console.log("=== Strategy Builder Debug Check ===");
  
  // Проверка элементов Navbar
  const navbarElements = {
    "btnTemplates": "#btnTemplates",
    "btnValidate": "#btnValidate",
    "btnGenerateCode": "#btnGenerateCode",
    "btnSave": "#btnSave",
    "btnBacktest": "#btnBacktest",
    "strategyName": "#strategyName"
  };
  
  console.log("\n--- Navbar Elements ---");
  for (const [name, selector] of Object.entries(navbarElements)) {
    const el = document.querySelector(selector);
    console.log(`${name}: ${el ? "✅ Found" : "❌ Missing"}`);
    if (el) {
      console.log(`  - Visible: ${el.offsetParent !== null}`);
      console.log(`  - Enabled: ${!el.disabled}`);
    }
  }
  
  // Проверка Properties Panel
  console.log("\n--- Properties Panel ---");
  const propertiesPanel = document.getElementById("propertiesPanel");
  console.log(`Properties Panel: ${propertiesPanel ? "✅ Found" : "❌ Missing"}`);
  
  const panes = document.querySelectorAll(".properties-tab-pane");
  const spines = document.querySelectorAll(".properties-tab-spine");
  console.log(`Properties Tabs: ${spines.length} spines, ${panes.length} panes`);
  spines.forEach((spine, index) => {
    const title = spine.title || spine.textContent?.trim() || `Tab ${index + 1}`;
    const isActive = spine.classList.contains("active");
    console.log(`  ${index + 1}. ${title}: ${isActive ? "Active" : "Inactive"}`);
  });
  
  // Проверка Block Library
  console.log("\n--- Block Library ---");
  const blockCategories = document.getElementById("blockCategories");
  console.log(`Block Categories Container: ${blockCategories ? "✅ Found" : "❌ Missing"}`);
  
  const categories = document.querySelectorAll(".block-category");
  console.log(`Block Categories: ${categories.length}`);
  
  // Проверка Canvas
  console.log("\n--- Canvas ---");
  const canvasContainer = document.getElementById("canvasContainer");
  console.log(`Canvas Container: ${canvasContainer ? "✅ Found" : "❌ Missing"}`);
  
  const blocksContainer = document.getElementById("blocksContainer");
  console.log(`Blocks Container: ${blocksContainer ? "✅ Found" : "❌ Missing"}`);
  
  const connectionsCanvas = document.getElementById("connectionsCanvas");
  console.log(`Connections Canvas: ${connectionsCanvas ? "✅ Found" : "❌ Missing"}`);
  
  // Проверка Templates Modal
  console.log("\n--- Templates Modal ---");
  const templatesModal = document.getElementById("templatesModal");
  console.log(`Templates Modal: ${templatesModal ? "✅ Found" : "❌ Missing"}`);
  if (templatesModal) {
    console.log(`  - Has 'active' class: ${templatesModal.classList.contains("active")}`);
    console.log(`  - Display style: ${window.getComputedStyle(templatesModal).display}`);
    console.log(`  - Visibility: ${window.getComputedStyle(templatesModal).visibility}`);
    console.log(`  - Opacity: ${window.getComputedStyle(templatesModal).opacity}`);
  }
  
  const templatesGrid = document.getElementById("templatesGrid");
  console.log(`Templates Grid: ${templatesGrid ? "✅ Found" : "❌ Missing"}`);
  
  // Проверка загруженных скриптов
  console.log("\n--- Scripts Check ---");
  const scripts = document.querySelectorAll("script[src]");
  console.log(`Total scripts: ${scripts.length}`);
  scripts.forEach((script, index) => {
    console.log(`  ${index + 1}. ${script.src || script.getAttribute("src")}`);
  });
  
  // Проверка ошибок в консоли
  console.log("\n--- Error Check ---");
  const originalError = console.error;
  let errorCount = 0;
  console.error = function(...args) {
    errorCount++;
    originalError.apply(console, args);
  };
  
  setTimeout(() => {
    console.log(`Errors detected: ${errorCount}`);
    console.error = originalError;
  }, 1000);
  
  console.log("\n=== Debug Check Complete ===");
});
