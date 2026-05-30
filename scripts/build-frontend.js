const fs = require('fs');
const path = require('path');

const indexHtmlPath = path.join(__dirname, '../StitchUIDesign/index.html');
let content = fs.readFileSync(indexHtmlPath, 'utf8');

// Read the Vercel environment variable
const backendUrl = process.env.BACKEND_URL || '';

if (backendUrl) {
    // Replace the default Railway domain with the Vercel env variable value
    content = content.replace(
        /https:\/\/zomato-recommender-backend\.up\.railway\.app/g,
        backendUrl
    );
    fs.writeFileSync(indexHtmlPath, content, 'utf8');
    console.log(`Successfully injected BACKEND_URL: "${backendUrl}" into index.html`);
} else {
    console.log("No BACKEND_URL environment variable found. Using default fallback.");
}
