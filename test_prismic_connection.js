#!/usr/bin/env node

import { createClient } from '@prismicio/client';
import dotenv from 'dotenv';

dotenv.config();

const repositoryName = process.env.PRISMIC_REPOSITORY_NAME || 'factory-ai';
const accessToken = process.env.PRISMIC_ACCESS_TOKEN || process.env.PRISMIC_API_KEY;

console.log('🔧 Testing Prismic Connection');
console.log('================================');
console.log(`Repository: ${repositoryName}`);
console.log(`Access Token: ${accessToken ? 'Present' : 'Missing'}`);
console.log(`API URL: https://${repositoryName}.cdn.prismic.io/api/v2`);

try {
    const client = createClient(repositoryName, {
        accessToken: accessToken,
    });

    console.log('\n📡 Testing repository connection...');
    
    // Try to get repository info
    const repository = await client.getRepository();
    console.log('✅ Repository connection successful!');
    console.log(`   Name: ${repository.ref}`);
    console.log(`   Master ref: ${repository.refs?.[0]?.ref || 'Unknown'}`);
    
    // Try to get existing documents
    console.log('\n📄 Testing document retrieval...');
    const response = await client.get();
    console.log(`✅ Document query successful!`);
    console.log(`   Total documents: ${response.results.length}`);
    console.log(`   Page: ${response.page}/${response.total_pages}`);
    
    // List some document types if any exist
    if (response.results.length > 0) {
        const types = [...new Set(response.results.map(doc => doc.type))];
        console.log(`   Document types: ${types.join(', ')}`);
    }

} catch (error) {
    console.error('❌ Connection failed:');
    console.error(`   Error: ${error.message}`);
    
    if (error.message.includes('not found')) {
        console.log('\n💡 Troubleshooting suggestions:');
        console.log('   1. Verify the repository name is correct');
        console.log('   2. Check if the repository exists in your Prismic dashboard');
        console.log('   3. Ensure the API token has access to this repository');
    }
    
    process.exit(1);
} 