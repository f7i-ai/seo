import * as prismic from '@prismicio/client';
import { readdir, readFile } from 'fs/promises';
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

// Function to convert markdown to rich text
function markdownToRichText(markdown) {
  // Remove the frontmatter from markdown
  const content = markdown.replace(/^---[\s\S]*?---\n/, '');
  
  // Split into paragraphs and process each one
  const paragraphs = content.split('\n\n').filter(p => p.trim());
  const richText = [];
  
  for (const paragraph of paragraphs) {
    const text = paragraph.replace(/\n/g, ' ').trim();
    
    if (!text) continue;
    
    // Handle headings
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
    
    // Handle list items
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
    
    // Handle bold text at start of paragraph
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
    
    // Regular paragraph
    richText.push({
      type: 'paragraph',
      text: text,
      spans: []
    });
  }
  
  return richText;
}

// Function to create a slug from title (matching original)
function createSlug(title) {
  return title
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .trim('-');
}

// Function to read and process all content files for updates
async function processContentForUpdates() {
  const contentDir = './generated_content';
  const files = await readdir(contentDir);
  
  // Filter for JSON files
  const jsonFiles = files.filter(file => file.endsWith('.json'));
  
  const updates = [];
  let processed = 0;
  
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
      
      // Create document slug (matching original migration)
      const slug = createSlug(metadata.title);
      
             // Create update data with complete document structure for updateDocument
       const updateData = {
         type: 'blog',
         uid: slug,
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
      
      updates.push(updateData);
      processed++;
      
      console.log(`✅ [${processed}/${jsonFiles.length}] Prepared update for: ${metadata.title}`);
      console.log(`   📝 Rich text blocks: ${richText.length}`);
      console.log(`   🆔 UID: ${slug}`);
      
    } catch (error) {
      console.error(`❌ Error processing ${jsonFile}: ${error.message}`);
    }
  }
  
  return updates;
}

// Main update migration function
async function runUpdateMigration() {
  try {
    console.log('🔄 Starting UPDATE migration process...');
    console.log(`📊 Repository: ${REPOSITORY_NAME}`);
    console.log(`🔑 API Key configured: ${PRISMIC_API_KEY ? 'Yes' : 'No'}`);
    console.log(`⏰ Timestamp: ${new Date().toISOString()}`);
    
    // Process all content files
    const updates = await processContentForUpdates();
    
    console.log(`\n📊 UPDATE SUMMARY:`);
    console.log(`   📄 Documents to update: ${updates.length}`);
    console.log(`   🎯 Will update existing documents with content`);
    console.log(`   📝 Each document will get TitleAndBody + ProfileTim slices`);
    
    if (updates.length === 0) {
      console.log('⚠️  No documents to update. Exiting...');
      return;
    }
    
    // Create migration for updates
    const migration = prismic.createMigration();
    
         // Add update operations to migration
     console.log('\n📤 Adding update operations to migration...');
     for (const updateData of updates) {
       // Use updateDocument to update existing documents with complete structure
       migration.updateDocument(updateData.uid, updateData);
       console.log(`   🔄 Queued update for: ${updateData.uid}`);
     }
    
    // Run migration
    console.log('\n🚀 Running update migration to Prismic...');
    const migrationResult = await writeClient.migrate(migration, {
      reporter: (event) => {
        if (event.type === 'documents:updating') {
          console.log(`   🔄 Updating documents...`);
        } else if (event.type === 'documents:updated') {
          console.log(`   ✅ Documents updated successfully!`);
        } else {
          console.log(`   📋 ${event.type}`);
        }
      },
    });
    
    console.log('\n🎉 UPDATE MIGRATION COMPLETED SUCCESSFULLY!');
    console.log(`📊 Result:`, migrationResult || 'Migration completed');
    
    console.log('\n✅ NEXT STEPS:');
    console.log('   1. Check your Prismic repository');
    console.log('   2. All existing documents now have complete slices with content');
    console.log('   3. Each document has TitleAndBody slice with rich text content');
    console.log('   4. Each document has ProfileTim slice with author info');
    console.log('   5. You can now publish these documents in Prismic!');
    
  } catch (error) {
    console.error('❌ Update migration failed:', error);
    if (error.response) {
      console.error('📄 Response status:', error.response.status);
      console.error('📄 Response data:', error.response.data);
    }
    process.exit(1);
  }
}

// Run the update migration
runUpdateMigration();