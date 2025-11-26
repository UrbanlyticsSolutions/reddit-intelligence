import os
from pathlib import Path

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r"Z:\\Code\\Backend\\Stock\\Reddit\\stock-479103-d965c4908b0e.json"
os.environ['GCS_BUCKET_NAME'] = 'stock-479103-deepseek-results'
os.environ['GCS_DEST_PREFIX'] = 'debug'
os.environ['ENABLE_GCS_UPLOADS'] = 'true'

from reddit_intelligence import upload_outputs_to_gcs

result = {
    'deepseek_market_analysis': 'Test analysis',
    'deepseek_symbol_analyses': {'TEST': 'Debug entry'},
    'deepseek_risk_assessment': 'Risk summary',
    'summary': {'generated_at': '2025-11-23T00:00:00Z'},
    'top_insights': [{'title': 'Sample'}]
}

output_dir = Path('outputs')
output_dir.mkdir(exist_ok=True)

sample_path = output_dir / 'debug_sample.txt'
sample_path.write_text('debug content', encoding='utf-8')

uploaded = upload_outputs_to_gcs(result, '20251123_000000', {'sample': sample_path}, output_dir)
print('Uploaded:', uploaded)
