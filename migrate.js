import * as prismic from '@prismicio/client';
import { readdir, readFile } from 'fs/promises';
import { join } from 'path';
import { config } from 'dotenv';

// Load environment variables
config();

const PRISMIC_API_KEY = process.env.PRISMIC_API_KEY;
const REPOSITORY_NAME = 'factory-ai';

if (!PRISMIC_API_KEY) {
  throw new Error('PRISMIC_API_KEY environment variable is required');
}

// Create Prismic write client
const writeClient = prismic.createWriteClient(REPOSITORY_NAME, {
  writeToken: PRISMIC_API_KEY,
});

// Function to convert markdown to rich text
function markdownToRichText(markdown) {
  // Remove the frontmatter from markdown
  const content = markdown.replace(/^---[\s\S]*?---\n/, '');
  
  // Split content into sections for better processing
  const lines = content.split('\n');
  const richText = [];
  
  let currentList = null;
  let currentParagraph = [];
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    
    if (!line) {
      // Empty line - end current paragraph or list
      if (currentParagraph.length > 0) {
        richText.push({
          type: 'paragraph',
          text: currentParagraph.join(' '),
          spans: []
        });
        currentParagraph = [];
      }
      currentList = null;
      continue;
    }
    
    // Handle headings
    if (line.startsWith('#')) {
      if (currentParagraph.length > 0) {
        richText.push({
          type: 'paragraph',
          text: currentParagraph.join(' '),
          spans: []
        });
        currentParagraph = [];
      }
      
      const level = line.match(/^#+/)[0].length;
      const text = line.replace(/^#+\s*/, '');
      
      richText.push({
        type: `heading${Math.min(level, 6)}`,
        text: text,
        spans: []
      });
      continue;
    }
    
    // Handle list items
    if (line.match(/^[\*\-\+]\s/) || line.match(/^\d+\.\s/)) {
      if (currentParagraph.length > 0) {
        richText.push({
          type: 'paragraph',
          text: currentParagraph.join(' '),
          spans: []
        });
        currentParagraph = [];
      }
      
      const isOrdered = line.match(/^\d+\.\s/);
      const text = line.replace(/^[\*\-\+\d]+[\.\s]*/, '');
      
      richText.push({
        type: isOrdered ? 'o-list-item' : 'list-item',
        text: text,
        spans: []
      });
      continue;
    }
    
    // Handle bold text
    if (line.startsWith('**') && line.endsWith('**')) {
      if (currentParagraph.length > 0) {
        richText.push({
          type: 'paragraph',
          text: currentParagraph.join(' '),
          spans: []
        });
        currentParagraph = [];
      }
      
      const text = line.replace(/^\*\*/, '').replace(/\*\*$/, '');
      richText.push({
        type: 'paragraph',
        text: text,
        spans: [{
          start: 0,
          end: text.length,
          type: 'strong'
        }]
      });
      continue;
    }
    
    // Regular paragraph text
    currentParagraph.push(line);
  }
  
  // Add any remaining paragraph
  if (currentParagraph.length > 0) {
    richText.push({
      type: 'paragraph',
      text: currentParagraph.join(' '),
      spans: []
    });
  }
  
  return richText;
}

// Function to create a slug from title
function createSlug(title) {
  return title
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .trim('-');
}

// Function to create asset in migration (skip for now due to expired URLs)
function createImageAsset(migration, imageUrl, alt, filename) {
  try {
    console.log(`Skipping expired image asset: ${filename}`);
    // Skip image assets for now since OpenAI DALL-E URLs are expired
    // Images can be added manually in Prismic later or regenerated
    return null;
  } catch (error) {
    console.error(`Error creating asset: ${error.message}`);
    return null;
  }
}

// Function to read and process all content files
async function processContentFiles(migration) {
  const contentDir = './generated_content';
  const files = await readdir(contentDir);
  
  // Filter for JSON files
  const jsonFiles = files.filter(file => file.endsWith('.json'));
  
  const documents = [];
  
  for (const jsonFile of jsonFiles) {
    try {
      const baseName = jsonFile.replace('.json', '');
      const jsonPath = join(contentDir, jsonFile);
      const mdPath = join(contentDir, `${baseName}.md`);
      
      // Read JSON metadata
      const jsonContent = await readFile(jsonPath, 'utf8');
      const metadata = JSON.parse(jsonContent);
      
      // Read markdown content
      const mdContent = await readFile(mdPath, 'utf8');
      
      // Convert markdown to rich text
      const richText = markdownToRichText(mdContent);
      
      // Create featured image asset
      let featuredImage = null;
      if (metadata.hero_image && metadata.hero_image.url) {
        const filename = `${baseName}-hero.png`;
        featuredImage = createImageAsset(migration, metadata.hero_image.url, metadata.hero_image.alt, filename);
      }
      
      // Create document slug
      const slug = createSlug(metadata.title);
      
      // Create document data
      const document = {
        type: 'blog',
        uid: slug,
        lang: 'en-us',
        data: {
          meta_title: metadata.meta_title,
          meta_description: metadata.meta_description,
          meta_image: featuredImage,
          slices: [
            {
              slice_type: 'title_and_body',
              variation: 'default',
              primary: {
                title: [{ type: 'heading1', text: metadata.title, spans: [] }],
                category: metadata.keyword,
                featuredimage: featuredImage,
                main_body: richText
              }
            },
            {
              slice_type: 'profile_tim',
              variation: 'default',
              primary: {
                tim1: 'Tim Cheung, CTO and Co-Founder of Factory AI'
              }
            }
          ]
        }
      };
      
      documents.push(document);
      console.log(`Processed: ${metadata.title}`);
      
    } catch (error) {
      console.error(`Error processing ${jsonFile}: ${error.message}`);
    }
  }
  
  return documents;
}

// Main migration function
async function runMigration() {
  try {
    console.log('Starting migration process...');
    console.log(`Repository: ${REPOSITORY_NAME}`);
    console.log(`API Key configured: ${PRISMIC_API_KEY ? 'Yes' : 'No'}`);
    
    // Create migration first
    const migration = prismic.createMigration();
    
    // Process all content files with migration instance
    const documents = await processContentFiles(migration);
    
    console.log(`Successfully processed ${documents.length} documents`);
    
    if (documents.length === 0) {
      console.log('No documents to migrate. Exiting...');
      return;
    }
    
    // Add documents to migration
    console.log('Adding documents to migration...');
    for (const doc of documents) {
      migration.createDocument(doc, doc.data.meta_title || 'Untitled Document');
      console.log(`Added document: ${doc.uid}`);
    }
    
    // Run migration
    console.log('Running migration to Prismic...');
    const migrationResult = await writeClient.migrate(migration, {
      reporter: (event) => console.log(`Migration event: ${event.type}`),
    });
    
    console.log('Migration completed successfully!');
    console.log(`Migration result:`, migrationResult);
    
  } catch (error) {
    console.error('Migration failed:', error);
    if (error.response) {
      console.error('Response status:', error.response.status);
      console.error('Response data:', error.response.data);
    }
    process.exit(1);
  }
}

// Run the migration
runMigration();