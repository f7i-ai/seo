import * as prismic from '@prismicio/client';
import { readFile } from 'fs/promises';
import { join } from 'path';
import { config } from 'dotenv';

// Load environment variables
config();

const PRISMIC_API_KEY = process.env.PRISMIC_API_KEY;
const REPOSITORY_NAME = 'factory-ai';

// Create Prismic write client
const writeClient = prismic.createWriteClient(REPOSITORY_NAME, {
  writeToken: PRISMIC_API_KEY,
});

// Simple rich text converter for debugging
function markdownToSimpleRichText(markdown) {
  // Remove frontmatter
  const content = markdown.replace(/^---[\s\S]*?---\n/, '');
  
  // Create simple rich text blocks
  const paragraphs = content.split('\n\n').filter(p => p.trim());
  
  return paragraphs.slice(0, 3).map(paragraph => {
    const text = paragraph.replace(/\n/g, ' ').trim();
    
    if (text.startsWith('#')) {
      const level = text.match(/^#+/)[0].length;
      const cleanText = text.replace(/^#+\s*/, '');
      return {
        type: `heading${Math.min(level, 6)}`,
        text: cleanText,
        spans: []
      };
    }
    
    return {
      type: 'paragraph',
      text: text,
      spans: []
    };
  });
}

async function debugMigration() {
  try {
    console.log('=== DEBUG MIGRATION START ===');
    
    // Read one sample file
    const jsonPath = join('./generated_content', 'air-compressor-maintenance.json');
    const mdPath = join('./generated_content', 'air-compressor-maintenance.md');
    
    const jsonContent = await readFile(jsonPath, 'utf8');
    const metadata = JSON.parse(jsonContent);
    
    const mdContent = await readFile(mdPath, 'utf8');
    const richText = markdownToSimpleRichText(mdContent);
    
    console.log('Metadata title:', metadata.title);
    console.log('Rich text blocks:', richText.length);
    
    // Create migration
    const migration = prismic.createMigration();
    
    // Test different slice structures
    console.log('\n=== TESTING SLICE STRUCTURE ===');
    
    const testDocument = {
      type: 'blog',
      uid: 'debug-test-document',
      lang: 'en-us',
      data: {
        meta_title: metadata.meta_title,
        meta_description: metadata.meta_description,
        slices: [
          {
            slice_type: 'title_and_body',
            variation: 'default',
            primary: {
              title: [{ type: 'heading1', text: metadata.title, spans: [] }],
              category: metadata.keyword,
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
    
    console.log('Document structure:');
    console.log(JSON.stringify(testDocument, null, 2));
    
    // Add to migration
    migration.createDocument(testDocument, 'Debug Test Document');
    
    console.log('\n=== ATTEMPTING MIGRATION ===');
    
    const migrationResult = await writeClient.migrate(migration, {
      reporter: (event) => console.log(`Migration event: ${event.type}`),
    });
    
    console.log('Debug migration completed successfully!');
    console.log('Result:', migrationResult);
    
  } catch (error) {
    console.error('Debug migration failed:', error);
    console.error('Error details:', error.response || error.message);
    
    // Try alternative slice structure if first attempt fails
    if (error.response && error.response.includes('slice')) {
      console.log('\n=== TRYING ALTERNATIVE SLICE STRUCTURE ===');
      await tryAlternativeStructure();
    }
  }
}

async function tryAlternativeStructure() {
  try {
    const migration = prismic.createMigration();
    
    // Alternative structure - maybe different field names
    const altDocument = {
      type: 'blog',
      uid: 'debug-alt-test-document',
      lang: 'en-us',
      data: {
        meta_title: 'Alternative Test Document',
        meta_description: 'Testing alternative slice structure',
        slices: [
          {
            slice_type: 'TitleAndBody', // Try PascalCase
            variation: 'default',
            primary: {
              title: [{ type: 'heading1', text: 'Test Title', spans: [] }],
              body: [ // Try 'body' instead of 'main_body'
                { type: 'paragraph', text: 'Test content paragraph.', spans: [] }
              ]
            }
          }
        ]
      }
    };
    
    console.log('Alternative structure:');
    console.log(JSON.stringify(altDocument, null, 2));
    
    migration.createDocument(altDocument, 'Alternative Test Document');
    
    const migrationResult = await writeClient.migrate(migration, {
      reporter: (event) => console.log(`Alt migration event: ${event.type}`),
    });
    
    console.log('Alternative migration completed successfully!');
    
  } catch (altError) {
    console.error('Alternative migration also failed:', altError);
    console.error('Alt error details:', altError.response || altError.message);
  }
}

// Run debug migration
debugMigration();