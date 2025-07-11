import * as prismic from '@prismicio/client';
import { readFile } from 'fs/promises';
import { join } from 'path';
import { config } from 'dotenv';

config();

const PRISMIC_API_KEY = process.env.PRISMIC_API_KEY;
const REPOSITORY_NAME = 'factory-ai';

const client = prismic.createClient(REPOSITORY_NAME);
const writeClient = prismic.createWriteClient(REPOSITORY_NAME, {
  writeToken: PRISMIC_API_KEY,
});

async function readAndUpdate() {
  try {
    console.log('📖 First, let\'s read an existing document...');
    
    // Pick a document that shows "Slices: 3" but no content
    const targetUID = 'the-first-10-steps-roadmap-of-a-predictive-maintenance-pilot';
    
    console.log(`🔍 Reading document: ${targetUID}`);
    
    // Read the document first to see its structure
    const doc = await client.getByUID('blog', targetUID);
    
    console.log('📄 Document found!');
    console.log(`   ID: ${doc.id}`);
    console.log(`   UID: ${doc.uid}`);
    console.log(`   Type: ${doc.type}`);
    console.log(`   Title: ${doc.data.meta_title || 'No title'}`);
    console.log(`   Slices: ${doc.data.slices ? doc.data.slices.length : 0}`);
    
    if (doc.data.slices) {
      console.log('\n🧩 Current slice structure:');
      doc.data.slices.forEach((slice, i) => {
        console.log(`   ${i + 1}. ${slice.slice_type} (${slice.variation})`);
        if (slice.slice_type === 'title_and_body') {
          const bodyLength = slice.primary?.main_body?.length || 0;
          console.log(`      - Main body: ${bodyLength} blocks`);
          if (bodyLength === 0) {
            console.log(`      - ❌ EMPTY - needs content!`);
          }
        }
        if (slice.slice_type === 'profile_tim') {
          const hasContent = slice.primary?.tim1;
          console.log(`      - Profile content: ${hasContent ? 'Has content' : 'Empty'}`);
        }
      });
    }
    
    console.log('\n💡 Now I understand the document structure.');
    console.log('🔧 Let me try to update it using the document ID instead of UID...');
    
    // Read our content
    const jsonPath = join('./generated_content', 'air-compressor-maintenance.json');
    const mdPath = join('./generated_content', 'air-compressor-maintenance.md');
    
    const jsonContent = await readFile(jsonPath, 'utf8');
    const metadata = JSON.parse(jsonContent);
    
    const mdContent = await readFile(mdPath, 'utf8');
    
    // Simple rich text conversion for testing
    const content = mdContent.replace(/^---[\s\S]*?---\n/, '');
    const paragraphs = content.split('\n\n').filter(p => p.trim()).slice(0, 10); // First 10 paragraphs
    
    const richText = paragraphs.map(p => ({
      type: 'paragraph',
      text: p.replace(/\n/g, ' ').trim(),
      spans: []
    }));
    
    console.log(`📝 Prepared ${richText.length} content blocks`);
    
    // Try updating with the document ID
    console.log(`🚀 Attempting update with document ID: ${doc.id}`);
    
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
    
    const result = await writeClient.updateDocument(doc.id, updateData);
    
    console.log('✅ UPDATE SUCCESSFUL!');
    console.log('📊 Result:', result);
    
  } catch (error) {
    console.error('❌ Error:', error);
    console.error('Details:', error.response || error.message);
    
    if (error.message.includes('doesn\'t exist')) {
      console.log('\n💡 The document ID approach didn\'t work either.');
      console.log('🤔 This suggests there might be a permissions or API configuration issue.');
    }
  }
}

readAndUpdate();