# Prismic Content Migration

This directory contains scripts to migrate the SEO-generated content from the `generated_content` directory to your Prismic CMS.

## Prerequisites

1. **Node.js** (v18 or higher)
2. **Prismic Account** with a repository named `factory-ai`
3. **Prismic API Key** with write permissions

## Setup

### 1. Install Dependencies

The required dependencies are already listed in `package.json`:
- `@prismicio/client`
- `@prismicio/migrate`
- `dotenv`
- `marked`

Dependencies are installed automatically when you run the migration.

### 2. Configure Environment Variables

Update the `.env` file with your actual Prismic API key:

```bash
PRISMIC_API_KEY=your-actual-prismic-api-key-here
```

**To get your Prismic API key:**
1. Go to your Prismic repository dashboard
2. Navigate to Settings > API & Security
3. Create a new Permanent Access Token with Master API write access
4. Copy the token to your `.env` file

### 3. Prismic Custom Types Setup

Ensure your Prismic repository has the following custom types configured:

#### Blog Custom Type (`blog`)
- Type: Repeatable
- API ID: `blog`
- Fields:
  - `meta_title` (Text)
  - `meta_description` (Text)
  - `meta_image` (Image)
  - `slices` (Slice Zone)

#### Required Slices
- `title_and_body` slice with fields:
  - `title` (Title)
  - `category` (Text)
  - `featuredimage` (Image)
  - `main_body` (Rich Text)
- `profile_tim` slice with fields:
  - `tim1` (Text)

## Migration Scripts

### Test Migration (`test-migration.js`)

Run this first to test the migration with a single document:

```bash
node test-migration.js
```

This will:
- Process the `air-compressor-maintenance` content as a test
- Convert markdown to Prismic rich text format
- Create a single document in Prismic
- Verify the migration process works correctly

### Full Migration (`migrate.js`)

After testing successfully, run the full migration:

```bash
node migrate.js
```

This will:
- Process all content files in the `generated_content` directory
- Upload hero images to Prismic Asset API
- Convert all markdown content to rich text
- Create blog documents with proper slices
- Generate SEO-friendly slugs from titles

## Content Processing

### Markdown to Rich Text Conversion

The migration script converts markdown content to Prismic's rich text format:
- **Headings**: `# Title` → `heading1`, `## Title` → `heading2`, etc.
- **Paragraphs**: Regular text → `paragraph` blocks
- **Lists**: `- Item` → `list-item`, `1. Item` → `o-list-item`
- **Bold text**: `**text**` → paragraph with strong spans

### Image Handling

Hero images are:
1. Downloaded from the original URLs
2. Uploaded to Prismic's Asset API
3. Referenced in both the TitleAndBody slice and meta_image field
4. Fallback to original URL if upload fails

### Document Structure

Each migrated document includes:
1. **TitleAndBody Slice**: Main content with title, category, featured image, and body text
2. **ProfileTim Slice**: Author information at the bottom
3. **SEO Metadata**: Title, description, and image for search engines

### URL Slug Generation

Document slugs are created from titles by:
- Converting to lowercase
- Removing special characters
- Replacing spaces with hyphens
- Ensuring uniqueness

## Troubleshooting

### Common Issues

1. **"PRISMIC_API_KEY environment variable is required"**
   - Check that your `.env` file contains the correct API key
   - Ensure the API key has write permissions

2. **"Failed to upload image"**
   - Some hero image URLs may be expired
   - The script will fallback to using the original URL

3. **Migration fails with 401 Unauthorized**
   - Verify your API key is correct
   - Check that the key has Master API write access

4. **Document creation fails**
   - Ensure your Prismic custom types match the expected structure
   - Check that required slices are properly configured

### Monitoring Progress

The migration scripts provide detailed logging:
- Document processing status
- Image upload progress
- Error details for troubleshooting
- Final migration results

## Post-Migration

After successful migration:
1. Review the created documents in your Prismic repository
2. Check that images are properly uploaded and displayed
3. Verify that the rich text content renders correctly
4. Test the generated slugs and SEO metadata

## Support

If you encounter issues:
1. Check the console output for specific error messages
2. Verify your Prismic repository configuration
3. Ensure your API key has the correct permissions
4. Test with the single document migration first

## File Structure

```
.
├── migrate.js              # Main migration script
├── test-migration.js       # Test script for single document
├── package.json           # Node.js dependencies
├── .env                   # Environment variables (API keys)
├── migration-README.md    # This file
└── generated_content/     # Source content files
    ├── *.json            # Metadata files
    ├── *.md              # Markdown content files
    └── *.png             # Hero images (if any)
```