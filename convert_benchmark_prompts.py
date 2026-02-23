import csv
import sys
from pathlib import Path

# Setup paths
base_dir = Path('.')
input_file = base_dir / 'aeo_benchmark_prompts.csv'
output_file = base_dir / 'aeo_benchmark_seo_tasks.csv'

# Map benchmark stages to Search Intent
intent_map = {
    'problem_unaware': 'Informational',
    'problem_aware': 'Informational',
    'solution_aware': 'Commercial',
    'vendor_aware': 'Commercial',
    'purchase_intent': 'Transactional'
}

# Define SEMrush-style headers required by seo_content_generator.py
headers = [
    'Database', 'Keyword', 'Seed keyword', 'Page', 'Topic', 'Page type', 'Tags', 
    'Volume', 'Keyword Difficulty', 'CPC (USD)', 'Competitive Density', 
    'Number of Results', 'Intent', 'SERP Features', 'Trend', 'Click potential', 
    'Content references', 'Competitors'
]

print(f"Converting {input_file} to {output_file}...")

try:
    with open(input_file, 'r', encoding='utf-8') as f_in, \
         open(output_file, 'w', encoding='utf-8', newline='') as f_out:
        
        reader = csv.DictReader(f_in)
        writer = csv.DictWriter(f_out, fieldnames=headers)
        
        writer.writeheader()
        
        count = 0
        for row in reader:
            stage = row['stage']
            prompt = row['prompt']
            
            intent = intent_map.get(stage, 'Informational')
            
            writer.writerow({
                'Database': 'us',
                'Keyword': prompt,
                'Seed keyword': prompt,
                'Page': '',
                'Topic': stage,  # Store stage as Topic/Tag for reference
                'Page type': '',
                'Tags': stage,
                'Volume': '10',  # Dummy volume to ensure processing
                'Keyword Difficulty': '0',
                'CPC (USD)': '0.00',
                'Competitive Density': '0.00',
                'Number of Results': '0',
                'Intent': intent,
                'SERP Features': '',
                'Trend': '',
                'Click potential': '',
                'Content references': '',
                'Competitors': ''
            })
            count += 1
            
    print(f"Success: Created {output_file} with {count} keywords.")

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
