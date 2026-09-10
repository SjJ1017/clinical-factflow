from pathlib import Path
import json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=ROOT/'findings/medcase24-study'
data=json.loads((OUT/'summary.json').read_text());payload=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
(OUT/'index.html').write_text((HERE/'report-template.html').read_text().replace('__DATA__',payload))
print('Report:',OUT/'index.html')
