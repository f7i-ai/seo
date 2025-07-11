import * as prismic from '@prismicio/client';
import { readFile } from 'fs/promises';
import { join } from 'path';
import { config } from 'dotenv';

config();

const PRISMIC_API_KEY = process.env.PRISMIC_API_KEY;
const REPOSITORY_NAME = 'factory-ai';

const writeClient = prismic.createWriteClient(REPOSITORY_NAME, {
  writeToken: PRISMIC_API_KEY,
});

// Convert markdown to rich text
function markdownToRichText(markdown) {
  const content = markdown.replace(/^---[\s\S]*?---\n/, '');
  const paragraphs = content.split('\n\n').filter(p => p.trim());
  const richText = [];
  
  for (const paragraph of paragraphs) {
    const text = paragraph.replace(/\n/g, ' ').trim();
    
    if (!text) continue;
    
    if (text.startsWith('#')) {
      const level = text.match(/^#+/)[0].length;
      const cleanText = text.replace(/^#+\s*/, '');
      richText.push({
        type: `heading${Math.min(level, 6)}`,
        text: cleanText,
        spans: []
      });
      continue;
    }
    
    if (text.match(/^[\*\-\+]\s/) || text.match(/^\d+\.\s/)) {
      const isOrdered = text.match(/^\d+\.\s/);
      const cleanText = text.replace(/^[\*\-\+\d]+[\.\s]*/, '');
      
      richText.push({
        type: isOrdered ? 'o-list-item' : 'list-item',
        text: cleanText,
        spans: []
      });
      continue;
    }
    
    if (text.startsWith('**') && text.includes('**:')) {
      const endBold = text.indexOf('**', 2);
      if (endBold > 2) {
        const boldText = text.substring(2, endBold);
        const restText = text.substring(endBold + 2);
        
        richText.push({
          type: 'paragraph',
          text: boldText + restText,
          spans: [{
            start: 0,
            end: boldText.length,
            type: 'strong'
          }]
        });
        continue;
      }
    }
    
    richText.push({
      type: 'paragraph',
      text: text,
      spans: []
    });
  }
  
  return richText;
}

async function updateWithCorrectSlices() {
  try {
    console.log('🎯 Updating with CORRECT slice types...');
    
    const targetUID = 'the-first-10-steps-roadmap-of-a-predictive-maintenance-pilot';
    
    console.log(`📝 Targeting document: ${targetUID}`);
    
    // Read our content
    const jsonPath = join('./generated_content', 'air-compressor-maintenance.json');
    const mdPath = join('./generated_content', 'air-compressor-maintenance.md');
    
    const jsonContent = await readFile(jsonPath, 'utf8');
    const metadata = JSON.parse(jsonContent);
    
    const mdContent = await readFile(mdPath, 'utf8');
    const richText = markdownToRichText(mdContent);
    
    console.log(`📚 Content prepared:`);
    console.log(`   Title: ${metadata.title}`);
    console.log(`   Rich text blocks: ${richText.length}`);
    
    // Update data using the CORRECT slice types from the existing schema
    const updateData = {
      meta_title: metadata.meta_title,
      meta_description: metadata.meta_description,
      slices: [
        {
          slice_type: 'article_header',
          variation: 'default',
          primary: {
            title: [{ type: 'heading1', text: metadata.title, spans: [] }],
            subtitle: [{ type: 'paragraph', text: metadata.meta_description, spans: [] }]
          }
        },
        {
          slice_type: 'body',
          variation: 'default',
          primary: {
            text: richText
          }
        },
        {
          slice_type: 'profile_card',
          variation: 'image_left_bio_right',
          primary: {
            name: 'Tim Cheung',
            title: 'CTO and Co-Founder of Factory AI',
            bio: [{ type: 'paragraph', text: 'Tim Cheung is the CTO and Co-Founder of Factory AI, leading the development of cutting-edge predictive maintenance solutions for industrial operations.', spans: [] }]
          }
        }
      ]
    };
    
    console.log('\n🧩 Using correct slice structure:');
    console.log('   1. article_header (default)');
    console.log('   2. body (default)');
    console.log('   3. profile_card (image_left_bio_right)');
    
    console.log('\n🚀 Attempting update...');
    
    const result = await writeClient.updateDocument(targetUID, updateData);
    
    console.log('✅ UPDATE SUCCESSFUL!');
    console.log(`📊 Document updated with ${richText.length} content blocks`);
    console.log(`🎉 The document now has proper content in the correct slice structure!`);
    
    console.log('\n💡 SUCCESS! Now we know the correct approach:');
    console.log('   - Use article_header slice for title and subtitle');
    console.log('   - Use body slice for main content');
    console.log('   - Use profile_card slice for author info');
    console.log('   - Use UID (not ID) for updates');
    
  } catch (error) {
    console.error('❌ Update failed:', error);
    console.error('Error details:', error.response || error.message);
    
    if (error.response) {
      console.log('\n🔍 API Response Details:');
      console.log(JSON.stringify(error.response, null, 2));
    }
  }
}

updateWithCorrectSlices();