/// <reference types="vitest" />
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // Test environment
    environment: 'happy-dom',
    
    // Global test setup
    globals: true,
    
    // Setup files
    setupFiles: ['./tests/setup.js'],
    
    // Include patterns
    include: ['./tests/**/*.{test,spec}.{js,mjs,ts}'],
    
    // Exclude patterns
    exclude: ['node_modules', 'dist'],
    
    // Coverage configuration
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/**/*.js', 'tests/**/*.js'],
      exclude: ['node_modules', 'dist']
    },
    
    // Reporter
    reporters: ['verbose'],
    
    // Timeout
    testTimeout: 10000
  }
});
