/**
 * SRI Hash Generator Script
 * Generates Subresource Integrity hashes for built files
 * and updates HTML files with the correct hashes
 */

import { createHash } from 'crypto';
import { readFileSync, writeFileSync, readdirSync, existsSync } from 'fs';
import { join, dirname, extname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const DIST_DIR = join(__dirname, '..', 'dist');
const ASSETS_DIR = join(DIST_DIR, 'assets');

/**
 * Generate SRI hash for a file
 * @param {string} filePath - Path to the file
 * @returns {string} - SRI hash in format 'sha384-...'
 */
function generateSRIHash(filePath) {
    const content = readFileSync(filePath);
    const hash = createHash('sha384').update(content).digest('base64');
    return `sha384-${hash}`;
}

/**
 * Get all assets with their hashes
 * @returns {Object} - Map of asset names to their SRI hashes
 */
function getAssetHashes() {
    if (!existsSync(ASSETS_DIR)) {
        console.warn('⚠️  No assets directory found. Run build first.');
        return {};
    }

    const hashes = {};
    const files = readdirSync(ASSETS_DIR);

    for (const file of files) {
        const ext = extname(file).toLowerCase();
        if (ext === '.js' || ext === '.css') {
            const filePath = join(ASSETS_DIR, file);
            const hash = generateSRIHash(filePath);
            hashes[file] = hash;
            console.log(`✅ ${file}: ${hash.substring(0, 30)}...`);
        }
    }

    return hashes;
}

/**
 * Update HTML files in dist with SRI attributes
 */
function updateHTMLWithSRI(hashes) {
    if (!existsSync(DIST_DIR)) {
        console.error('❌ Dist directory not found!');
        return;
    }

    const htmlFiles = readdirSync(DIST_DIR).filter(f => f.endsWith('.html'));
    let updatedCount = 0;

    for (const htmlFile of htmlFiles) {
        const htmlPath = join(DIST_DIR, htmlFile);
        let content = readFileSync(htmlPath, 'utf-8');
        let modified = false;

        // Update script tags
        for (const [assetName, hash] of Object.entries(hashes)) {
            if (assetName.endsWith('.js')) {
                const regex = new RegExp(
                    `(<script[^>]*src="[^"]*${assetName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}"[^>]*)>`,
                    'g'
                );
                const replacement = `$1 integrity="${hash}" crossorigin="anonymous">`;

                if (regex.test(content) && !content.includes(`integrity="${hash}"`)) {
                    content = content.replace(regex, replacement);
                    modified = true;
                }
            }
        }

        // Update link tags
        for (const [assetName, hash] of Object.entries(hashes)) {
            if (assetName.endsWith('.css')) {
                const regex = new RegExp(
                    `(<link[^>]*href="[^"]*${assetName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}"[^>]*)>`,
                    'g'
                );
                const replacement = `$1 integrity="${hash}" crossorigin="anonymous">`;

                if (regex.test(content) && !content.includes(`integrity="${hash}"`)) {
                    content = content.replace(regex, replacement);
                    modified = true;
                }
            }
        }

        if (modified) {
            writeFileSync(htmlPath, content);
            console.log(`📝 Updated: ${htmlFile}`);
            updatedCount++;
        }
    }

    console.log(`\n✅ Updated ${updatedCount} HTML files with SRI hashes`);
}

/**
 * Generate SRI manifest file for reference
 */
function generateManifest(hashes) {
    const manifest = {
        generated: new Date().toISOString(),
        algorithm: 'sha384',
        assets: hashes
    };

    const manifestPath = join(DIST_DIR, 'sri-manifest.json');
    writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
    console.log('📋 Manifest saved: sri-manifest.json');
}

// Main execution
console.log('🔐 Generating SRI Hashes...\n');

const hashes = getAssetHashes();

if (Object.keys(hashes).length > 0) {
    console.log('\n🔄 Updating HTML files...\n');
    updateHTMLWithSRI(hashes);
    generateManifest(hashes);
    console.log('\n✅ SRI generation complete!');
} else {
    console.log('⚠️  No assets found to hash.');
}
