#!/usr/bin/env node

import * as prismic from '@prismicio/client';
import { readdir, readFile } from 'fs/promises';
import { join } from 'path';
import { config } from 'dotenv';
import FormData from 'form-data';
import fetch from 'node-fetch';
import { createReadStream, existsSync } from 'fs';

// Load environment variables
config();

const PRISMIC_API_KEY = process.env.PRISMIC_API_KEY;
const REPOSITORY_NAME = 'factory-ai';
const DEBUG = process.env.DEBUG === 'true' || process.argv.includes('--debug');

// Debug logging utility
function debugLog(message, data = null) {
  if (DEBUG) {
    const timestamp = new Date().toISOString();
    console.log(`[DEBUG ${timestamp}] ${message}`);
    if (data) {
      console.log('  Data:', JSON.stringify(data, null, 2));
    }
  }
}

function infoLog(message, data = null) {
  const timestamp = new Date().toISOString();
  console.log(`[INFO ${timestamp}] ${message}`);
  if (data && DEBUG) {
    console.log('  Data:', JSON.stringify(data, null, 2));
  }
}

function errorLog(message, error = null, data = null) {
  const timestamp = new Date().toISOString();
  console.error(`[ERROR ${timestamp}] ${message}`);
  if (error) {
    console.error('  Error:', error);
    if (error.stack && DEBUG) {
      console.error('  Stack:', error.stack);
    }
  }
  if (data && DEBUG) {
    console.error('  Context:', JSON.stringify(data, null, 2));
  }
}

debugLog('Environment setup', {
  PRISMIC_API_KEY_EXISTS: !!PRISMIC_API_KEY,
  REPOSITORY_NAME,
  NODE_ENV: process.env.NODE_ENV,
  DEBUG_MODE: DEBUG
});

if (!PRISMIC_API_KEY) {
  errorLog('PRISMIC_API_KEY environment variable is required');
  throw new Error('PRISMIC_API_KEY environment variable is required');
}

// Create Prismic write client
debugLog('Creating Prismic write client', { REPOSITORY_NAME });
const writeClient = prismic.createWriteClient(REPOSITORY_NAME, {
  writeToken: PRISMIC_API_KEY,
});
infoLog('Prismic write client created successfully');

// Function to convert markdown to rich text
function markdownToRichText(markdown) {
  debugLog('Starting markdown to rich text conversion', { 
    markdownLength: markdown.length,
    firstLine: markdown.split('\n')[0]
  });
  
  // Remove the frontmatter from markdown
  const content = markdown.replace(/^---[\s\S]*?---\n/, '');
  debugLog('Frontmatter removed', { 
    originalLength: markdown.length,
    newLength: content.length 
  });
  
  // Split into paragraphs and process each one
  const paragraphs = content.split('\n\n').filter(p => p.trim());
  debugLog('Content split into paragraphs', { paragraphCount: paragraphs.length });
  
  const richText = [];
  
  for (let i = 0; i < paragraphs.length; i++) {
    const paragraph = paragraphs[i];
    const text = paragraph.replace(/\n/g, ' ').trim();
    
    debugLog(`Processing paragraph ${i + 1}/${paragraphs.length}`, { 
      originalText: paragraph.substring(0, 100) + (paragraph.length > 100 ? '...' : ''),
      cleanedText: text.substring(0, 100) + (text.length > 100 ? '...' : '')
    });
    
    if (!text) {
      debugLog(`Skipping empty paragraph ${i + 1}`);
      continue;
    }
    
    // Handle headings
    if (text.startsWith('#')) {
      const level = text.match(/^#+/)[0].length;
      const cleanText = text.replace(/^#+\s*/, '');
      const headingType = `heading${Math.min(level, 6)}`;
      
      debugLog(`Processing heading level ${level}`, { 
        headingType,
        originalText: text,
        cleanText 
      });
      
      richText.push({
        type: headingType,
        text: cleanText,
        spans: []
      });
      continue;
    }
    
    // Handle list items
    if (text.match(/^[\*\-\+]\s/) || text.match(/^\d+\.\s/)) {
      const isOrdered = text.match(/^\d+\.\s/);
      const cleanText = text.replace(/^[\*\-\+\d]+[\.\s]*/, '');
      const listType = isOrdered ? 'o-list-item' : 'list-item';
      
      debugLog(`Processing list item`, { 
        isOrdered,
        listType,
        originalText: text,
        cleanText 
      });
      
      richText.push({
        type: listType,
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
        
        debugLog(`Processing bold paragraph`, { 
          boldText,
          restText: restText.substring(0, 50) + (restText.length > 50 ? '...' : ''),
          boldLength: boldText.length
        });
        
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
    debugLog(`Processing regular paragraph`, { 
      textLength: text.length,
      preview: text.substring(0, 100) + (text.length > 100 ? '...' : '')
    });
    
    richText.push({
      type: 'paragraph',
      text: text,
      spans: []
    });
  }
  
  debugLog('Markdown to rich text conversion completed', { 
    totalElements: richText.length,
    elementTypes: richText.map(el => el.type)
  });
  
  return richText;
}

// Function to create a slug from title
function createSlug(title) {
  debugLog('Creating slug from title', { originalTitle: title });
  
  const slug = title
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .trim('-');
    
  debugLog('Slug created', { originalTitle: title, slug });
  return slug;
}

// Function to check if document exists by UID
async function checkDocumentExists(uid) {
  try {
    debugLog('Checking if document exists', { uid });
    
    // Create a read-only client to check existing documents
    const readClient = prismic.createClient(REPOSITORY_NAME);
    
    const document = await readClient.getByUID('blog', uid);
    debugLog('Document exists', { uid, documentId: document.id });
    return document;
  } catch (error) {
    // Handle various "not found" error patterns
    if (error.type === 'prismic-not-found' || 
        error.message === 'No documents were returned' ||
        error.constructor.name === 'NotFoundError' ||
        error.name === 'NotFoundError') {
      debugLog('Document does not exist', { uid });
      return null;
    }
    debugLog('Error checking document existence', { uid, error: error.message });
    throw error;
  }
}

// Function to upload asset to Prismic Asset API from local file
async function uploadAssetToPrismic(localPath, alt, filename) {
  debugLog('Starting asset upload to Prismic from local file', { 
    localPath,
    alt,
    filename
  });
  
  try {
    // Check if local file exists
    debugLog('Checking if local image file exists');
    if (!existsSync(localPath)) {
      throw new Error(`Local image file does not exist: ${localPath}`);
    }
    
    debugLog('Reading local image file');
    const imageStream = createReadStream(localPath);
    
    // Create form data for upload
    const formData = new FormData();
    formData.append('file', imageStream, {
      filename: filename,
      contentType: 'image/png'  // Assuming PNG for generated images
    });
    
    // Add metadata
    if (alt) {
      formData.append('alt', alt);
    }
    
    debugLog('Uploading asset to Prismic Asset API');
    
    // Upload to Prismic Asset API
    const uploadResponse = await fetch('https://asset-api.prismic.io/assets', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${PRISMIC_API_KEY}`,
        'repository': REPOSITORY_NAME,
        ...formData.getHeaders()
      },
      body: formData
    });
    
    if (!uploadResponse.ok) {
      const errorText = await uploadResponse.text();
      throw new Error(`Asset upload failed: ${uploadResponse.status} ${uploadResponse.statusText} - ${errorText}`);
    }
    
    const assetData = await uploadResponse.json();
    debugLog('Asset uploaded successfully', { 
      assetId: assetData.id,
      assetUrl: assetData.url,
      filename,
      localPath
    });
    
    // Rate limiting: Asset API allows 1 request per second
    debugLog('Waiting 1 second for Asset API rate limit');
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Return asset in Prismic format
    return {
      id: assetData.id,
      url: assetData.url,
      alt: alt || '',
      copyright: null,
      dimensions: assetData.width && assetData.height ? {
        width: assetData.width,
        height: assetData.height
      } : null
    };
    
  } catch (error) {
    errorLog(`Error uploading asset: ${filename}`, error, { localPath, alt });
    
    // Return null for failed uploads - document can still be created without image
    return null;
  }
}

// Function to create asset (now with actual upload from local file)
async function createImageAsset(localPath, alt, filename) {
  debugLog('Creating image asset from local file', { 
    localPath,
    alt,
    filename
  });
  
  if (!localPath) {
    debugLog('No local path provided');
    return null;
  }
  
  try {
    // Upload the asset to Prismic
    const asset = await uploadAssetToPrismic(localPath, alt, filename);
    
    if (asset) {
      infoLog(`Successfully uploaded asset: ${filename}`);
      return asset;
    } else {
      infoLog(`Failed to upload asset: ${filename}`);
      return null;
    }
    
  } catch (error) {
    errorLog(`Error creating asset: ${filename}`, error, { localPath, alt });
    return null;
  }
}

// Function to process a single JSON file
async function processSingleFile(jsonFilePath, skipUpload = false) {
  const startTime = Date.now();
  debugLog('Starting processSingleFile', { jsonFilePath, skipUpload });
  
  try {
    infoLog(`Processing: ${jsonFilePath}`);
    
    const baseName = jsonFilePath.replace('.json', '').split('/').pop();
    const contentDir = jsonFilePath.includes('/') ? jsonFilePath.substring(0, jsonFilePath.lastIndexOf('/')) : '.';
    const mdPath = join(contentDir, `${baseName}.md`);
    
    debugLog('File paths calculated', { baseName, contentDir, mdPath });
    
    // Read JSON metadata
    debugLog('Reading JSON metadata file');
    const jsonContent = await readFile(jsonFilePath, 'utf8');
    const metadata = JSON.parse(jsonContent);
    
    debugLog('JSON metadata parsed', { 
      title: metadata.title,
      keyword: metadata.keyword,
      hasHeroImage: !!metadata.hero_image,
      hasLocalPath: !!(metadata.hero_image && metadata.hero_image.local_path),
      metaTitle: metadata.meta_title,
      metaDescription: metadata.meta_description?.substring(0, 100) + '...'
    });
    
    // Read markdown content
    debugLog('Reading markdown content file');
    const mdContent = await readFile(mdPath, 'utf8');
    debugLog('Markdown content read', { 
      contentLength: mdContent.length,
      lineCount: mdContent.split('\n').length
    });
    
    if (skipUpload) {
      const slug = createSlug(metadata.title);
      infoLog(`✅ Test mode - would upload: ${metadata.title}`);
      infoLog(`   UID would be: ${slug}`);
      infoLog(`   Repository: ${REPOSITORY_NAME}`);
      
      debugLog('Test mode completed', {
        processingTime: Date.now() - startTime + 'ms',
        title: metadata.title,
        slug
      });
      
      return { success: true, skipped: true, title: metadata.title };
    }
    
    // Create document slug first to check if document exists
    debugLog('Creating document slug');
    const slug = createSlug(metadata.title);
    
    // Check if document already exists
    debugLog('Checking if document exists');
    const existingDocument = await checkDocumentExists(slug);
    
    // Create featured image asset
    debugLog('Processing featured image');
    let featuredImage = null;
    if (metadata.hero_image && metadata.hero_image.local_path) {
      const filename = `${baseName}-hero.png`;
      featuredImage = await createImageAsset(metadata.hero_image.local_path, metadata.hero_image.alt, filename);
      debugLog('Featured image processed', { filename, hasAsset: !!featuredImage, localPath: metadata.hero_image.local_path });
    } else {
      debugLog('No featured image found in metadata or no local_path', { 
        hasHeroImage: !!metadata.hero_image,
        hasLocalPath: !!(metadata.hero_image && metadata.hero_image.local_path)
      });
    }
    
    // Prepare markdown content (remove frontmatter)
    debugLog('Preparing markdown content for direct insertion');
    const cleanMarkdown = mdContent.replace(/^---[\s\S]*?---\n/, '');
    debugLog('Markdown cleaned', { 
      originalLength: mdContent.length,
      cleanedLength: cleanMarkdown.length 
    });
    
    // Create document data structure
    const documentData = {
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
            markdownmainbody: [{ type: 'preformatted', text: cleanMarkdown, spans: [] }]  // Properly formatted StructuredText
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
    
    debugLog('Document structure created', {
      uid: slug,
      sliceCount: documentData.slices.length,
      markdownLength: cleanMarkdown.length,
      hasFeaturedImage: !!featuredImage,
      existingDocument: !!existingDocument
    });
    
    let migrationResult;
    
    if (existingDocument) {
      // Update existing document
      infoLog(`Updating existing document: ${metadata.title}`);
      debugLog('Updating existing document', { 
        existingId: existingDocument.id,
        uid: slug 
      });
      
      migrationResult = await writeClient.updateDocument({
        id: existingDocument.id,
        data: documentData
      });
      
      infoLog(`✅ Successfully updated: ${metadata.title}`);
      
    } else {
      // Create new document
      infoLog(`Creating new document: ${metadata.title}`);
      debugLog('Creating new document via migration');
      
      const migration = prismic.createMigration();
      
      const document = {
        type: 'blog',
        uid: slug,
        lang: 'en-us',
        data: documentData
      };
      
      migration.createDocument(document, metadata.meta_title || metadata.title);
      debugLog('Document added to migration');
      
      // Run migration
      infoLog('Uploading to Prismic...');
      
      try {
        migrationResult = await writeClient.migrate(migration, {
          reporter: (event) => {
            debugLog(`Migration event: ${event.type}`, event);
            infoLog(`Migration: ${event.type}`);
          },
        });
        
        infoLog(`✅ Successfully created: ${metadata.title}`);
        
      } catch (migrationError) {
        // Handle UID already exists error by falling back to update
        if (migrationError.message.includes('already exists') || 
            migrationError.response === 'A document with this UID already exists') {
          
          infoLog(`Document exists in Prismic but not detected by read client. Attempting update...`);
          debugLog('Migration failed due to existing UID, attempting update fallback', {
            uid: slug,
            error: migrationError.message
          });
          
          // Try multiple approaches to find the existing document
          try {
            let existingDoc = null;
            
            // Approach 1: Try with a different read client
            try {
              debugLog('Trying to find document with standard read client');
              const readClientForUpdate = prismic.createClient(REPOSITORY_NAME);
              existingDoc = await readClientForUpdate.getByUID('blog', slug);
              debugLog('Found document with standard read client', { uid: slug, id: existingDoc.id });
            } catch (readError) {
              debugLog('Standard read client failed', { error: readError.message });
              
              // Approach 2: Try searching all documents
              try {
                debugLog('Trying to find document by searching all blog documents');
                const readClientForSearch = prismic.createClient(REPOSITORY_NAME);
                const searchResults = await readClientForSearch.getByType('blog', {
                  filters: [prismic.filter.at('my.blog.uid', slug)],
                  pageSize: 1
                });
                
                if (searchResults.results && searchResults.results.length > 0) {
                  existingDoc = searchResults.results[0];
                  debugLog('Found document via search', { uid: slug, id: existingDoc.id });
                } else {
                  debugLog('No document found via search either');
                }
              } catch (searchError) {
                debugLog('Search approach also failed', { error: searchError.message });
              }
            }
            
            if (existingDoc) {
              debugLog('Found existing document for update', {
                uid: slug,
                existingId: existingDoc.id
              });
              
              // Update the existing document
              migrationResult = await writeClient.updateDocument({
                id: existingDoc.id,
                data: documentData
              });
              
              infoLog(`✅ Successfully updated existing document: ${metadata.title}`);
            } else {
              // If we can't find it but migration says it exists, let's try to force create with a slightly different UID
              const newSlug = slug + '-' + Date.now();
              infoLog(`Could not find existing document for update. Creating with new UID: ${newSlug}`);
              
              const newMigration = prismic.createMigration();
              const newDocument = {
                type: 'blog',
                uid: newSlug,
                lang: 'en-us',
                data: documentData
              };
              
              newMigration.createDocument(newDocument, metadata.meta_title || metadata.title);
              
              migrationResult = await writeClient.migrate(newMigration, {
                reporter: (event) => {
                  debugLog(`Fallback migration event: ${event.type}`, event);
                  infoLog(`Fallback migration: ${event.type}`);
                },
              });
              
              infoLog(`✅ Successfully created with new UID: ${newSlug}`);
            }
            
          } catch (updateError) {
            debugLog('All update approaches failed', {
              uid: slug,
              updateError: updateError.message
            });
            throw migrationError; // Re-throw the original migration error
          }
          
        } else {
          throw migrationError; // Re-throw if it's not a UID conflict
        }
      }
    }
    
    const processingTime = Date.now() - startTime;
    debugLog('Operation completed successfully', {
      uid: slug,
      title: metadata.title,
      processingTime: processingTime + 'ms',
      wasUpdate: !!existingDocument,
      migrationResult
    });
    
    return { 
      success: true, 
      uid: slug, 
      title: metadata.title, 
      result: migrationResult,
      wasUpdate: !!existingDocument 
    };
    
  } catch (error) {
    const processingTime = Date.now() - startTime;
    errorLog(`❌ Error processing file: ${jsonFilePath}`, error, {
      processingTime: processingTime + 'ms',
      skipUpload
    });
    return { success: false, error: error.message };
  }
}

// Function to read and process all content files
async function processContentFiles(migration) {
  const startTime = Date.now();
  const contentDir = './generated_content';
  
  debugLog('Starting batch content processing', { contentDir });
  
  const files = await readdir(contentDir);
  debugLog('Content directory read', { 
    totalFiles: files.length,
    files: files.slice(0, 10) // Log first 10 files
  });
  
  // Filter for JSON files
  const jsonFiles = files.filter(file => file.endsWith('.json'));
  infoLog(`Found ${jsonFiles.length} JSON files to process`);
  debugLog('JSON files found', { jsonFiles });
  
  const documents = [];
  let processedCount = 0;
  let errorCount = 0;
  
  for (const jsonFile of jsonFiles) {
    const fileStartTime = Date.now();
    debugLog(`Processing file ${processedCount + 1}/${jsonFiles.length}`, { jsonFile });
    
    try {
      const baseName = jsonFile.replace('.json', '');
      const jsonPath = join(contentDir, jsonFile);
      const mdPath = join(contentDir, `${baseName}.md`);
      
      debugLog('File paths for batch processing', { baseName, jsonPath, mdPath });
      
      // Read JSON metadata
      debugLog('Reading JSON metadata for batch');
      const jsonContent = await readFile(jsonPath, 'utf8');
      const metadata = JSON.parse(jsonContent);
      
      debugLog('JSON metadata parsed for batch', {
        title: metadata.title,
        keyword: metadata.keyword,
        hasHeroImage: !!metadata.hero_image,
        hasLocalPath: !!(metadata.hero_image && metadata.hero_image.local_path)
      });
      
      // Read markdown content
      debugLog('Reading markdown content for batch');
      const mdContent = await readFile(mdPath, 'utf8');
      
      // Create document slug
      const slug = createSlug(metadata.title);
      
      // Check if document already exists
      debugLog('Checking if document exists for batch processing', { uid: slug });
      const existingDocument = await checkDocumentExists(slug);
      
      if (existingDocument) {
        infoLog(`Document ${slug} already exists, will be updated`);
        debugLog('Existing document found in batch', { 
          uid: slug,
          existingId: existingDocument.id 
        });
      }
      
      // Create featured image asset
      debugLog('Processing featured image for batch');
      let featuredImage = null;
      if (metadata.hero_image && metadata.hero_image.local_path) {
        const filename = `${baseName}-hero.png`;
        featuredImage = await createImageAsset(metadata.hero_image.local_path, metadata.hero_image.alt, filename);
      }
      
      // Prepare markdown content (remove frontmatter)
      const cleanMarkdown = mdContent.replace(/^---[\s\S]*?---\n/, '');
      
      // Create document data structure
      const documentData = {
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
              markdownmainbody: [{ type: 'preformatted', text: cleanMarkdown, spans: [] }]  // Properly formatted StructuredText
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
      
      // Create document structure for batch processing
      const document = {
        type: 'blog',
        uid: slug,
        lang: 'en-us',
        data: documentData,
        existingDocument: existingDocument  // Track if this needs updating
      };
      
      documents.push(document);
      processedCount++;
      
      const fileProcessingTime = Date.now() - fileStartTime;
      infoLog(`Processed: ${metadata.title}`);
      debugLog('File processed successfully in batch', {
        title: metadata.title,
        uid: slug,
        processingTime: fileProcessingTime + 'ms',
        documentsCreated: documents.length
      });
      
    } catch (error) {
      errorCount++;
      const fileProcessingTime = Date.now() - fileStartTime;
      errorLog(`Error processing ${jsonFile}`, error, {
        processingTime: fileProcessingTime + 'ms',
        processedCount,
        errorCount
      });
    }
  }
  
  const totalProcessingTime = Date.now() - startTime;
  infoLog(`Batch processing completed: ${processedCount} successful, ${errorCount} errors`);
  debugLog('Batch processing summary', {
    totalFiles: jsonFiles.length,
    processedCount,
    errorCount,
    documentsCreated: documents.length,
    totalProcessingTime: totalProcessingTime + 'ms',
    avgTimePerFile: Math.round(totalProcessingTime / jsonFiles.length) + 'ms'
  });
  
  return documents;
}

// Main migration function for batch upload
async function runBatchMigration() {
  const startTime = Date.now();
  debugLog('Starting batch migration process');
  
  try {
    infoLog('Starting batch migration process...');
    infoLog(`Repository: ${REPOSITORY_NAME}`);
    infoLog(`API Key configured: ${PRISMIC_API_KEY ? 'Yes' : 'No'}`);
    
    debugLog('Batch migration configuration', {
      repository: REPOSITORY_NAME,
      hasApiKey: !!PRISMIC_API_KEY,
      startTime: new Date(startTime).toISOString()
    });
    
    // Create migration first
    debugLog('Creating migration instance');
    const migration = prismic.createMigration();
    
    // Process all content files with migration instance
    debugLog('Processing content files');
    const documents = await processContentFiles(migration);
    
    infoLog(`Successfully processed ${documents.length} documents`);
    
    if (documents.length === 0) {
      infoLog('No documents to migrate. Exiting...');
      debugLog('Migration terminated - no documents found');
      return;
    }
    
    // Separate documents into new and existing
    const newDocuments = documents.filter(doc => !doc.existingDocument);
    const existingDocuments = documents.filter(doc => doc.existingDocument);
    
    infoLog(`Processing ${newDocuments.length} new documents and ${existingDocuments.length} existing documents`);
    debugLog('Document separation complete', { 
      newCount: newDocuments.length,
      existingCount: existingDocuments.length 
    });
    
    let migrationResult = null;
    let updateResults = [];
    
    // Handle new documents via migration
    if (newDocuments.length > 0) {
      infoLog('Adding new documents to migration...');
      debugLog('Starting new document addition to migration', { documentCount: newDocuments.length });
      
      for (let i = 0; i < newDocuments.length; i++) {
        const doc = newDocuments[i];
        // Remove the existingDocument property before migration
        const cleanDoc = { ...doc };
        delete cleanDoc.existingDocument;
        
        migration.createDocument(cleanDoc, doc.data.meta_title || 'Untitled Document');
        
        debugLog(`Added new document ${i + 1}/${newDocuments.length}`, {
          uid: doc.uid,
          title: doc.data.meta_title,
          type: doc.type
        });
        
        infoLog(`Added new document: ${doc.uid}`);
      }
      
      debugLog('All new documents added to migration');
      
      // Run migration for new documents
      infoLog('Running migration for new documents...');
      debugLog('Starting Prismic migration upload');
      
      migrationResult = await writeClient.migrate(migration, {
        reporter: (event) => {
          debugLog(`Migration event received: ${event.type}`, event);
          infoLog(`Migration event: ${event.type}`);
        },
      });
      
      infoLog(`✅ Successfully created ${newDocuments.length} new documents`);
    }
    
    // Handle existing documents via updates
    if (existingDocuments.length > 0) {
      infoLog('Updating existing documents...');
      debugLog('Starting existing document updates', { updateCount: existingDocuments.length });
      
      for (let i = 0; i < existingDocuments.length; i++) {
        const doc = existingDocuments[i];
        
        try {
          debugLog(`Updating document ${i + 1}/${existingDocuments.length}`, {
            uid: doc.uid,
            existingId: doc.existingDocument.id
          });
          
          const updateResult = await writeClient.updateDocument({
            id: doc.existingDocument.id,
            data: doc.data
          });
          
          updateResults.push(updateResult);
          infoLog(`Updated document: ${doc.uid}`);
          
        } catch (error) {
          errorLog(`Failed to update document: ${doc.uid}`, error, {
            existingId: doc.existingDocument.id
          });
          // Continue with other updates even if one fails
        }
      }
      
      infoLog(`✅ Successfully updated ${updateResults.length}/${existingDocuments.length} existing documents`);
    }
    
    const totalTime = Date.now() - startTime;
    infoLog('Batch processing completed successfully!');
    
    const totalProcessed = (migrationResult ? newDocuments.length : 0) + updateResults.length;
    const totalAttempted = documents.length;
    
    infoLog(`Results: ${totalProcessed}/${totalAttempted} documents processed successfully`);
    infoLog(`  - Created: ${newDocuments.length}`);
    infoLog(`  - Updated: ${updateResults.length}`);
    
    if (migrationResult) {
      debugLog('Migration result:', migrationResult);
    }
    if (updateResults.length > 0) {
      debugLog('Update results:', { updateCount: updateResults.length });
    }
    
    debugLog('Batch processing completed successfully', {
      totalDocuments: documents.length,
      newDocuments: newDocuments.length,
      updatedDocuments: updateResults.length,
      totalProcessed,
      totalTime: totalTime + 'ms',
      avgTimePerDocument: totalAttempted > 0 ? Math.round(totalTime / totalAttempted) + 'ms' : '0ms'
    });
    
  } catch (error) {
    const totalTime = Date.now() - startTime;
    errorLog('Migration failed', error, {
      totalTime: totalTime + 'ms',
      repository: REPOSITORY_NAME
    });
    
    if (error.response) {
      errorLog('HTTP Response details', null, {
        status: error.response.status,
        statusText: error.response.statusText,
        data: error.response.data
      });
    }
    
    process.exit(1);
  }
}

// CLI interface
async function main() {
  const startTime = Date.now();
  const args = process.argv.slice(2);
  
  debugLog('Main function started', { 
    args,
    nodeVersion: process.version,
    platform: process.platform,
    cwd: process.cwd()
  });
  
  if (args.length === 0) {
    console.log(`
🚀 Prismic Content Uploader

Usage:
  node prismic_uploader.js <json_file> [--skip-upload] [--debug]
  node prismic_uploader.js --batch [--skip-upload] [--debug]

Options:
  --skip-upload    Skip actual upload (test mode)
  --batch          Process all files in generated_content/
  --debug          Enable detailed debug logging

Environment Variables:
  DEBUG=true       Enable debug mode via environment variable

Examples:
  node prismic_uploader.js generated_content/my-keyword.json
  node prismic_uploader.js generated_content/my-keyword.json --skip-upload
  node prismic_uploader.js --batch --debug
    `);
    process.exit(1);
  }

  const skipUpload = args.includes('--skip-upload');
  const batchMode = args.includes('--batch');
  
  debugLog('CLI arguments parsed', { skipUpload, batchMode, debugMode: DEBUG });
  
  if (skipUpload) {
    infoLog(`🧪 Running in test mode - no uploads will be performed`);
  }
  
  if (DEBUG) {
    infoLog(`🔍 Debug mode enabled - detailed logging active`);
  }

  try {
    if (batchMode) {
      debugLog('Starting batch mode processing');
      
      if (skipUpload) {
        infoLog('Batch test mode not implemented - use single file test instead');
        debugLog('Batch test mode requested but not supported');
        process.exit(1);
      }
      
      await runBatchMigration();
      
    } else {
      const targetFile = args[0];
      debugLog('Starting single file processing', { targetFile });
      
      if (!targetFile || targetFile.startsWith('--')) {
        errorLog('No target file specified');
        console.error('❌ Please specify a JSON file to process');
        process.exit(1);
      }
      
      const result = await processSingleFile(targetFile, skipUpload);
      
      if (result.success) {
        const totalTime = Date.now() - startTime;
        infoLog(`✅ Operation completed successfully`);
        
        if (result.skipped) {
          infoLog(`⏭️  Upload was skipped (test mode)`);
        }
        
        debugLog('Single file operation completed', {
          success: true,
          skipped: result.skipped,
          title: result.title,
          uid: result.uid,
          totalTime: totalTime + 'ms'
        });
        
      } else {
        const totalTime = Date.now() - startTime;
        errorLog(`❌ Operation failed: ${result.error}`, null, {
          targetFile,
          totalTime: totalTime + 'ms'
        });
        process.exit(1);
      }
    }
    
  } catch (error) {
    const totalTime = Date.now() - startTime;
    errorLog(`❌ Fatal error in main function`, error, {
      args,
      totalTime: totalTime + 'ms',
      skipUpload,
      batchMode
    });
    process.exit(1);
  }
  
  const totalTime = Date.now() - startTime;
  debugLog('Main function completed', { 
    totalTime: totalTime + 'ms',
    success: true
  });
}

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  debugLog('Script executed directly, starting main function');
  main().catch(error => {
    errorLog('Unhandled error in main execution', error);
    process.exit(1);
  });
} else {
  debugLog('Script imported as module, not executing main function');
} 