const fs = require('fs');
const path = require('path');

const srcPath = path.join(__dirname, '../StitchUIDesign/index.html');
const destDir = path.join(__dirname, '../public');
const destPath = path.join(destDir, 'index.html');

// Create public directory if not exists
if (!fs.existsSync(destDir)) {
    fs.mkdirSync(destDir, { recursive: true });
}

let content = fs.readFileSync(srcPath, 'utf8');

// Read the Vercel environment variable
const backendUrl = process.env.BACKEND_URL || '';

if (backendUrl) {
    // Replace either default Railway domain with the Vercel env variable value
    content = content.replace(
        /https:\/\/(zomato-recommender-backend|zomato-production-79e2)\.up\.railway\.app/g,
        backendUrl
    );
    console.log(`Injected BACKEND_URL: "${backendUrl}"`);
} else {
    console.log("No BACKEND_URL environment variable found. Using default fallback.");
}

// Write to public/index.html
fs.writeFileSync(destPath, content, 'utf8');
console.log(`Successfully generated public/index.html`);
