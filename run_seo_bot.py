#!/usr/bin/env python3
"""
Non-interactive SEO Bot Runner
Automatically processes keywords from kw.csv
"""

import os
import sys
from seo_content_generator import SEOContentGenerator

def main():
    print("🚀 Starting SEO Content Generator for f7i.ai")
    print("=" * 50)
    
    # Use existing CSV file
    csv_path = "kw.csv"
    if not os.path.exists(csv_path):
        print("❌ kw.csv file not found!")
        return
    
    print(f"📊 Using CSV file: {csv_path}")
    
    # Use default sitemap URL
    sitemap_url = "https://f7i.ai/sitemap.xml"
    print(f"🔗 Using sitemap: {sitemap_url}")
    
    try:
        generator = SEOContentGenerator()
        
        # Load keywords with SERP data
        print("\n🔍 Loading keywords from CSV...")
        keyword_data = generator.load_keywords_from_csv(csv_path)
        if not keyword_data:
            print("❌ No keywords found in CSV!")
            return
        
        print(f"✅ Loaded {len(keyword_data)} unique keywords")
        
        # Load existing content from sitemap
        print(f"\n🕸️  Loading existing content from sitemap...")
        existing_content = generator.load_existing_content_from_sitemap(sitemap_url)
        
        # Filter out keywords that overlap with existing content OR already have generated content
        filtered_keywords = []
        skipped_overlap = 0
        skipped_existing = 0
        
        print("\n📋 Filtering keywords...")
        for keyword in keyword_data.keys():
            # Check if content already exists
            if generator.check_existing_content(keyword):
                print(f"✅ Skipping '{keyword}' - content already generated")
                skipped_existing += 1
                continue
            
            # Check for content overlap with existing blog
            if generator.check_keyword_overlap(keyword, existing_content):
                print(f"⚠️  Skipping '{keyword}' - overlaps with existing blog content")
                skipped_overlap += 1
                continue
            
            filtered_keywords.append(keyword)
        
        print(f"\n📊 Content Generation Summary:")
        print(f"   • Total keywords in CSV: {len(keyword_data)}")
        print(f"   • Already generated: {skipped_existing}")
        print(f"   • Overlaps with existing blog: {skipped_overlap}")
        print(f"   • Ready for generation: {len(filtered_keywords)}")
        
        if not filtered_keywords:
            print("\n✅ All keywords have been processed!")
            return
        
        print(f"\n🎯 Processing {len(filtered_keywords)} keywords...")
        
        # Process each keyword
        for i, keyword in enumerate(filtered_keywords, 1):
            print(f"\n📝 Processing keyword {i}/{len(filtered_keywords)}: '{keyword}'")
            print("-" * 60)
            
            try:
                # Research keyword with SERP data
                print("  🔬 Researching keyword with SERP analysis...")
                serp_data = keyword_data.get(keyword, [])
                research_data = generator.research_keyword_with_claude(keyword, serp_data)
                
                if "error" in research_data:
                    print(f"  ❌ Research failed: {research_data['error']}")
                    continue
                
                # Generate content
                print("  ✍️  Generating content with Claude...")
                blog_post = generator.generate_content_with_claude(keyword, research_data)
                
                if not blog_post:
                    print(f"  ❌ Failed to generate content for: {keyword}")
                    continue
                
                # Generate image
                print("  🎨 Generating hero image with DALL-E...")
                blog_post.image_url = generator.generate_image_with_openai(blog_post.image_prompt)
                
                # Format for Prismic
                print("  📋 Formatting for Prismic CMS...")
                prismic_data = generator.format_for_prismic(blog_post)
                
                # Save output
                print("  💾 Saving files...")
                body_markdown = blog_post.body
                filepaths = generator.save_output(prismic_data, keyword, body_markdown)
                
                print(f"  ✅ Content generated successfully!")
                print(f"  📄 Files saved: {filepaths[0]} & {filepaths[1]}")
                
                # Rate limiting
                print("  ⏱️  Waiting 2 seconds before next keyword...")
                import time
                time.sleep(2)
                
            except Exception as e:
                print(f"  ❌ Error processing '{keyword}': {e}")
                continue
        
        print(f"\n🎉 Content generation complete!")
        print(f"📁 Check the 'generated_content' folder for your files.")
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        return

if __name__ == "__main__":
    main()