import * as prismic from '@prismicio/client';
import { config } from 'dotenv';

config();

const REPOSITORY_NAME = 'factory-ai';
const client = prismic.createClient(REPOSITORY_NAME);

async function checkDocuments() {
  try {
    console.log('📋 Checking Prismic documents...');
    
    const docs = await client.getAllByType('blog');
    
    console.log(`📄 Found ${docs.length} blog documents`);
    
    docs.forEach((doc, i) => {
      console.log(`\n${i + 1}. UID: ${doc.uid}`);
      console.log(`   Title: ${doc.data.meta_title || 'No title'}`);
      console.log(`   Slices: ${doc.data.slices ? doc.data.slices.length : 0}`);
      
      if (doc.data.slices) {
        doc.data.slices.forEach(slice => {
          if (slice.slice_type === 'title_and_body') {
            const bodyLength = slice.primary?.main_body?.length || 0;
            console.log(`   - TitleAndBody: ${bodyLength} blocks`);
          }
        });
      }
    });
    
    return docs;
    
  } catch (error) {
    console.error('❌ Error:', error.message);
  }
}

checkDocuments();