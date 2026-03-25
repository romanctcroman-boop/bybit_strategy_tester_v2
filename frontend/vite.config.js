/**
 * ⚡ Vite Configuration - Bybit Strategy Tester v2
 *
 * Build configuration for frontend assets including:
 * - JavaScript bundling and minification
 * - CSS processing and optimization
 * - Multi-page application support
 * - Subresource Integrity (SRI) hash generation
 *
 * @version 1.0.0
 * @date 2025-12-21
 */
/* eslint-env node */

import { defineConfig } from 'vite';
import { resolve } from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';
import { readdirSync, statSync, writeFileSync } from 'fs';
import { createHash } from 'crypto';

// ESM equivalent of __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Plugin to generate SRI hashes after build
function sriPlugin() {
    return {
        name: 'sri-generator',
        writeBundle(options, bundle) {
            const sriHashes = {};

            for (const [fileName, chunk] of Object.entries(bundle)) {
                if (chunk.type === 'chunk' || fileName.endsWith('.css')) {
                    const content = chunk.type === 'chunk' ? chunk.code : chunk.source;
                    const hash = createHash('sha384')
                        .update(content)
                        .digest('base64');

                    sriHashes[fileName] = {
                        integrity: `sha384-${hash}`,
                        size: content.length
                    };
                }
            }

            // Write SRI hashes to JSON file
            const outputPath = resolve(options.dir, 'sri-manifest.json');
            writeFileSync(outputPath, JSON.stringify(sriHashes, null, 2));

            console.log(`\n🔒 SRI Manifest generated: ${Object.keys(sriHashes).length} files`);
        }
    };
}

// Get all HTML files for multi-page build
function getHtmlEntries() {
    const htmlDir = resolve(__dirname);
    const entries = {};

    readdirSync(htmlDir).forEach(file => {
        if (file.endsWith('.html')) {
            const name = file.replace('.html', '');
            entries[name] = resolve(htmlDir, file);
        }
    });

    return entries;
}

// Get all JS entry points
function getJsEntries() {
    const jsDir = resolve(__dirname, 'js');
    const pagesDir = resolve(jsDir, 'pages');
    const entries = {};

    // Main JS files
    ['api', 'utils', 'security', 'navigation'].forEach(name => {
        const path = resolve(jsDir, `${name}.js`);
        try {
            statSync(path);
            entries[`js/${name}`] = path;
        } catch (_e) { /* File not found, skip */ }
    });

    // Page-specific JS files
    try {
        readdirSync(pagesDir).forEach(file => {
            if (file.endsWith('.js')) {
                const name = file.replace('.js', '');
                entries[`js/pages/${name}`] = resolve(pagesDir, file);
            }
        });
    } catch (_e) { /* Directory not found */ }

    return entries;
}

// Get all CSS entry points
function getCssEntries() {
    const cssDir = resolve(__dirname, 'css');
    const entries = {};

    try {
        readdirSync(cssDir).forEach(file => {
            if (file.endsWith('.css')) {
                const name = file.replace('.css', '');
                entries[`css/${name}`] = resolve(cssDir, file);
            }
        });
    } catch (_e) { /* Directory not found */ }

    return entries;
}

export default defineConfig(({ command, mode }) => {
    const isDev = command === 'serve';
    const isProd = mode === 'production';

    return {
        // Base path for assets
        base: '/frontend/',

        // Root directory
        root: __dirname,

        // Public directory for static assets
        publicDir: 'assets',

        // Development server config
        server: {
            port: 3000,
            open: false,
            cors: true,
            proxy: {
                '/api': {
                    target: 'http://localhost:8000',
                    changeOrigin: true
                }
            }
        },

        // Build configuration
        build: {
            // Output directory
            outDir: 'dist',

            // Assets directory inside outDir
            assetsDir: 'assets',

            // Generate source maps in dev
            sourcemap: !isProd,

            // Minify in production
            minify: isProd ? 'terser' : false,

            // Terser options
            terserOptions: isProd ? {
                compress: {
                    drop_console: false,  // Keep console for debugging
                    drop_debugger: true,
                    pure_funcs: ['console.debug']
                },
                format: {
                    comments: false
                }
            } : undefined,

            // CSS code splitting
            cssCodeSplit: true,

            // Rollup options
            rollupOptions: {
                // External libraries (UMD scripts not bundled)
                external: [
                    /libs\/lightweight-charts\.js/,
                    /libs\/bootstrap\.bundle\.min\.js/
                ],
                input: {
                    // HTML pages
                    ...getHtmlEntries(),
                    // JavaScript modules
                    ...getJsEntries(),
                    // CSS files
                    ...getCssEntries()
                },
                output: {
                    // Chunk file naming
                    chunkFileNames: 'js/chunks/[name]-[hash].js',

                    // Entry file naming
                    entryFileNames: (chunkInfo) => {
                        if (chunkInfo.name.startsWith('js/')) {
                            return '[name].js';
                        }
                        return 'js/[name].js';
                    },

                    // Asset file naming
                    assetFileNames: (assetInfo) => {
                        const name = assetInfo.name || '';
                        if (name.endsWith('.css')) {
                            if (name.includes('pages/') || name.includes('css/')) {
                                return '[name][extname]';
                            }
                            return 'css/[name][extname]';
                        }
                        return 'assets/[name]-[hash][extname]';
                    },

                    // Manual chunks for better caching
                    manualChunks: (id) => {
                        // Vendor chunks
                        if (id.includes('node_modules')) {
                            if (id.includes('chart.js')) {
                                return 'vendor-charts';
                            }
                            return 'vendor';
                        }

                        // Shared utilities
                        if (id.includes('/js/api.js') ||
                            id.includes('/js/utils.js') ||
                            id.includes('/js/security.js')) {
                            return 'shared';
                        }
                    }
                }
            },

            // Report compressed size
            reportCompressedSize: true,

            // Chunk size warning limit (500kb)
            chunkSizeWarningLimit: 500
        },

        // CSS configuration
        css: {
            // Dev source maps
            devSourcemap: true,

            // PostCSS plugins (add autoprefixer etc. if needed)
            postcss: {
                plugins: []
            }
        },

        // Plugin configuration
        plugins: [
            // SRI hash generator
            sriPlugin()
        ],

        // Optimization configuration
        optimizeDeps: {
            include: [
                // Pre-bundle these dependencies
            ],
            exclude: [
                // Don't pre-bundle these
            ]
        },

        // Preview server (for production preview)
        preview: {
            port: 4173,
            open: true
        },

        // Environment variables
        define: {
            __DEV__: isDev,
            __PROD__: isProd,
            __VERSION__: JSON.stringify('2.0.0'),
            __BUILD_DATE__: JSON.stringify(new Date().toISOString())
        }
    };
});
