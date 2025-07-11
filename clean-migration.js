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

// Function to create a unique slug from title
function createUniqueSlug(title) {
  const timestamp = Date.now();
  const baseSlug = title
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .trim('-')
    .substring(0, 50); // Limit length
  
  return `${baseSlug}-${timestamp}`;
}

// Function to read and process all content files
async function processCleanContentFiles(migration) {
  const contentDir = './generated_content';
  const files = await readdir(contentDir);
  
  // Filter for JSON files
  const jsonFiles = files.filter(file => file.endsWith('.json'));
  
  const documents = [];
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
      
      // Create unique document slug
      const slug = createUniqueSlug(metadata.title);
      
      // Create document data with working slice structure
      const document = {
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
      
      documents.push(document);
      processed++;
      
      console.log(`✅ [${processed}/${jsonFiles.length}] ${metadata.title}`);
      console.log(`   📝 Rich text blocks: ${richText.length}`);
      console.log(`   🆔 UID: ${slug}`);
      
    } catch (error) {
      console.error(`❌ Error processing ${jsonFile}: ${error.message}`);
    }
  }
  
  return documents;
}

// Main clean migration function
async function runCleanMigration() {
  try {
    console.log('🧹 Starting CLEAN migration process...');
    console.log(`📊 Repository: ${REPOSITORY_NAME}`);
    console.log(`🔑 API Key configured: ${PRISMIC_API_KEY ? 'Yes' : 'No'}`);
    console.log(`⏰ Timestamp: ${new Date().toISOString()}`);
    
    // Create migration first
    const migration = prismic.createMigration();
    
    // Process all content files with migration instance
    const documents = await processCleanContentFiles(migration);
    
    console.log(`\n📊 MIGRATION SUMMARY:`);
    console.log(`   📄 Documents processed: ${documents.length}`);
    console.log(`   🎯 All documents have unique UIDs with timestamps`);
    console.log(`   📝 All documents contain TitleAndBody + ProfileTim slices`);
    
    if (documents.length === 0) {
      console.log('⚠️  No documents to migrate. Exiting...');
      return;
    }
    
    // Add documents to migration
    console.log('\n📤 Adding documents to migration...');
    for (const doc of documents) {
      migration.createDocument(doc, doc.data.meta_title || 'Untitled Document');
      console.log(`   ➕ Added: ${doc.uid}`);
    }
    
    // Run migration
    console.log('\n🚀 Running clean migration to Prismic...');
    const migrationResult = await writeClient.migrate(migration, {
      reporter: (event) => {
        if (event.type === 'documents:creating') {
          console.log(`   🔄 Creating documents...`);
        } else if (event.type === 'documents:created') {
          console.log(`   ✅ Documents created successfully!`);
        } else {
          console.log(`   📋 ${event.type}`);
        }
      },
    });
    
    console.log('\n🎉 CLEAN MIGRATION COMPLETED SUCCESSFULLY!');
    console.log(`📊 Result:`, migrationResult || 'Migration completed');
    
    console.log('\n✅ NEXT STEPS:');
    console.log('   1. Check your Prismic repository');
    console.log('   2. All documents now have complete slices with content');
    console.log('   3. Each document has TitleAndBody slice with rich text content');
    console.log('   4. Each document has ProfileTim slice with author info');
    console.log('   5. You can now publish these documents in Prismic!');
    
  } catch (error) {
    console.error('❌ Clean migration failed:', error);
    if (error.response) {
      console.error('📄 Response status:', error.response.status);
      console.error('📄 Response data:', error.response.data);
    }
    process.exit(1);
  }
}

// Run the clean migration
runCleanMigration();