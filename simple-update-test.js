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

// Simple rich text converter
function markdownToRichText(markdown) {
  const content = markdown.replace(/^---[\s\S]*?---\n/, '');
  const paragraphs = content.split('\n\n').filter(p => p.trim()).slice(0, 5); // Just first 5 paragraphs for testing
  
  return paragraphs.map(paragraph => {
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

async function testDirectUpdate() {
  try {
    console.log('🧪 Testing direct document update...');
    
    // Read one sample file
    const jsonPath = join('./generated_content', 'air-compressor-maintenance.json');
    const mdPath = join('./generated_content', 'air-compressor-maintenance.md');
    
    const jsonContent = await readFile(jsonPath, 'utf8');
    const metadata = JSON.parse(jsonContent);
    
    const mdContent = await readFile(mdPath, 'utf8');
    const richText = markdownToRichText(mdContent);
    
    console.log(`Title: ${metadata.title}`);
    console.log(`Rich text blocks: ${richText.length}`);
    
    // Document UID that should exist
    const docUID = 'strategic-air-compressor-maintenance-the-complete-guide-to-maximizing-performance-and-minimizing-costs';
    
    console.log(`Attempting to update document: ${docUID}`);
    
    // Try to update the document directly
    const updateData = {
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
    };
    
    console.log('Update data structure:');
    console.log(JSON.stringify(updateData, null, 2));
    
    const result = await writeClient.updateDocument(docUID, updateData);
    
    console.log('✅ Direct update successful!');
    console.log('Result:', result);
    
  } catch (error) {
    console.error('❌ Direct update failed:', error);
    console.error('Error details:', error.response || error.message);
  }
}

// Run test
testDirectUpdate();