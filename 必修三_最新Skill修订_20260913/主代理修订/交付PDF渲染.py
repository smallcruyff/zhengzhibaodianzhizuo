"""Use the installed render_docx.py PNG pipeline with Word's exact native PDF as its conversion result."""
from pathlib import Path
import importlib.util,sys,os,json,hashlib
R=Path('/Users/wanglifei/Desktop/gpt6/必修三_最新Skill修订_20260913');doc=R/'必修三政治与法治宝典_R31续修_第43批_阶段审查稿.docx';pdf=doc.with_suffix('.pdf');out=R/'第43批页面_交付'
assert pdf.is_file() and pdf.stat().st_size>10000
os.environ['PATH']='/Users/wanglifei/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override:'+os.environ['PATH']
spec=importlib.util.spec_from_file_location('render_docx','/Users/wanglifei/.codex/plugins/cache/openai-primary-runtime/documents/26.909.22227/skills/documents/render_docx.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.convert_to_pdf=lambda *args,**kwargs:(str(pdf),'Native Microsoft Word export, exact saved manuscript. No LibreOffice conversion.')
sys.argv=['render_docx.py',str(doc),'--output_dir',str(out),'--dpi','120'];m.main()
from pypdf import PdfReader
record={'docx':str(doc),'docx_sha256':hashlib.sha256(doc.read_bytes()).hexdigest(),'pdf':str(pdf),'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'pages':len(PdfReader(pdf).pages),'png_count':len(list(out.glob('page-*.png'))),'renderer':'installed documents/render_docx.py main + native-PDF conversion adapter','dpi':120,'visual_review_complete':False}
assert record['pages']==record['png_count'];(R/'主代理修订/同版渲染记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2));print(record)
