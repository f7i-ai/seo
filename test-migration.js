import * as prismic from '@prismicio/client';
import { readFile } from 'fs/promises';
import { join } from 'path';
import { config } from 'dotenv';

// Load environment variables
config();

const PRISMIC_API_KEY = process.env.PRISMIC_API_KEY;
const REPOSITORY_NAME = 'factory-ai';

if (!PRISMIC_API_KEY) {
  throw new Error('PRISMIC_API_KEY environment variable is required');
}

// Function to convert markdown to rich text (simplified for testing)
function markdownToRichText(markdown) {
  const content = markdown.replace(/^---[\s\S]*?---\n/, '');
  const lines = content.split('\n');
  const richText = [];
  
  let currentParagraph = [];
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    
    if (!line) {
      if (currentParagraph.length > 0) {
        richText.push({
          type: 'paragraph',
          text: currentParagraph.join(' '),
          spans: []
        });
        currentParagraph = [];
      }
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

// Test migration with a single document
async function testMigration() {
  try {
    console.log('Testing migration with a single document...');
    
    // Use the air-compressor-maintenance as test document
    const testFile = 'air-compressor-maintenance';
    const jsonPath = join('./generated_content', `${testFile}.json`);
    const mdPath = join('./generated_content', `${testFile}.md`);
    
    // Read JSON metadata
    const jsonContent = await readFile(jsonPath, 'utf8');
    const metadata = JSON.parse(jsonContent);
    
    // Read markdown content
    const mdContent = await readFile(mdPath, 'utf8');
    
    // Convert markdown to rich text
    const richText = markdownToRichText(mdContent);
    
    console.log(`Title: ${metadata.title}`);
    console.log(`Rich text blocks: ${richText.length}`);
    
    // Create document slug
    const slug = createSlug(metadata.title);
    console.log(`Slug: ${slug}`);
    
    // For testing, let's skip image upload and use a placeholder
    const featuredImage = metadata.hero_image ? {
      url: metadata.hero_image.url,
      alt: metadata.hero_image.alt,
      dimensions: {
        width: 1200,
        height: 800
      }
    } : null;
    
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
    
    console.log('Document structure created successfully');
    console.log('Document UID:', document.uid);
    console.log('Slices:', document.data.slices.length);
    
    // Create migration
    const migration = prismic.createMigration();
    
    // Create write client
    const writeClient = prismic.createWriteClient(REPOSITORY_NAME, {
      writeToken: PRISMIC_API_KEY,
    });
    
    // Add document to migration
    migration.createDocument(document, metadata.title);
    
    // Run migration
    console.log('Running test migration...');
    const migrationResult = await writeClient.migrate(migration, {
      reporter: (event) => console.log(`Migration event: ${event.type}`),
    });
    
    console.log('Test migration completed successfully!');
    console.log('Migration result:', migrationResult);
    
  } catch (error) {
    console.error('Test migration failed:', error);
    if (error.response) {
      console.error('Response status:', error.response.status);
      console.error('Response data:', error.response.data);
    }
  }
}

// Run the test
testMigration();