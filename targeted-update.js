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

async function updateExistingDocument() {
  try {
    console.log('🎯 Targeted Update Test...');
    
    // Pick an existing document UID that appears to be empty (has slices but no content blocks listed)
    // From the list, I'll use one that shows "Slices: 3" but no "- TitleAndBody: X blocks"
    const targetUID = 'the-first-10-steps-roadmap-of-a-predictive-maintenance-pilot';
    
    console.log(`📝 Targeting document: ${targetUID}`);
    
    // Read our sample content
    const jsonPath = join('./generated_content', 'air-compressor-maintenance.json');
    const mdPath = join('./generated_content', 'air-compressor-maintenance.md');
    
    const jsonContent = await readFile(jsonPath, 'utf8');
    const metadata = JSON.parse(jsonContent);
    
    const mdContent = await readFile(mdPath, 'utf8');
    const richText = markdownToRichText(mdContent);
    
    console.log(`📚 Content prepared:`);
    console.log(`   Title: ${metadata.title}`);
    console.log(`   Rich text blocks: ${richText.length}`);
    console.log(`   Meta title: ${metadata.meta_title}`);
    
    // Update data structure
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
    
    console.log('\n🚀 Attempting to update document...');
    
    const result = await writeClient.updateDocument(targetUID, updateData);
    
    console.log('✅ UPDATE SUCCESSFUL!');
    console.log(`📊 Result:`, result);
    
    console.log('\n🎉 SUCCESS! The document has been updated with content.');
    console.log('💡 Now we can use this approach for all remaining empty documents.');
    
  } catch (error) {
    console.error('❌ Update failed:', error);
    console.error('Error details:', error.response || error.message);
  }
}

updateExistingDocument();