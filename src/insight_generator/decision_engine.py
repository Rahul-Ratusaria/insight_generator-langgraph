"""Report-wide evidence-first analytics. Generic table facts, deterministic arithmetic, optional multimodal LLM.
No persuasion or demographic targeting recommendations; political data stays descriptive.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any
import hashlib, json, os, re
import pymupdf
from pydantic import BaseModel, Field

VALUE = re.compile(r'^\s*([-+]?\d[\d,]*(?:\.\d+)?)\s*(%|days?|₹|\$)?\s*$')

class ExtractedFact(BaseModel):
    page: int = Field(ge=1)
    topic: str
    row: str
    column: str
    value: float
    unit: str = ''
    evidence: str
    evidence_type: str = 'table'
    confidence: str = 'medium'

class PageFacts(BaseModel):
    facts: list[ExtractedFact] = Field(default_factory=list)
    page_summary: str = ''
    issues: list[str] = Field(default_factory=list)

class DecisionNote(BaseModel):
    title: str
    finding: str
    implication: str
    suggested_next_step: str
    caveat: str
    source_ids: list[int] = Field(default_factory=list)
    priority: str = 'medium'

class BriefParagraph(BaseModel):
    heading: str
    paragraph: str
    source_ids: list[int] = Field(default_factory=list)
    source_pages: list[int] = Field(default_factory=list)

class SynthesizedNotes(BaseModel):
    notes: list[DecisionNote] = Field(default_factory=list)
    paragraphs: list[BriefParagraph] = Field(default_factory=list)
    overall_summary: str = ''

@dataclass
class VerifiedFinding:
    title: str
    observation: str
    calculation: str
    fact_ids: list[int]
    source_pages: list[int]
    evidence: list[str]
    category: str = 'comparison'
    caveat: str = 'This is descriptive. Compare definitions, sampling and uncertainty before deciding.'
    priority: str = 'medium'

@dataclass
class DecisionReport:
    document: str
    mode: str
    pages: int
    facts: list[dict] = field(default_factory=list)
    findings: list[dict] = field(default_factory=list)
    decision_notes: list[dict] = field(default_factory=list)
    brief_paragraphs: list[dict] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)
    page_summaries: list[dict] = field(default_factory=list)
    summary: str = ''

    def json(self):
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    def markdown(self):
        lines = [f'# Decision intelligence: {self.document}', '', self.summary, '',
                 f'Pages: {self.pages} | Metrics: {len(self.facts)} | Comparisons: {len(self.findings)}',
                 '', '## Verified comparisons']
        for x in self.findings:
            lines += [f'### {x["title"]}', x['observation'], f'Calculation: {x["calculation"]}',
                      f'Pages: {x["source_pages"]}', f'Caveat: {x["caveat"]}', '']
        lines.append('## Executive brief')
        for x in self.brief_paragraphs:
            lines += [f'### {x["heading"]}', x['paragraph'], f'Source pages: {x["source_pages"]}', '']
        lines.append('## Decision considerations')
        for x in self.decision_notes:
            lines += [f'### {x["title"]}', x['finding'], f'Implication: {x["implication"]}',
                      f'Next step: {x["suggested_next_step"]}', f'Caveat: {x["caveat"]}', '']
        lines += ['## Review issues'] + [f'- Page {i["page"]}: {i["issue"]}' for i in self.issues]
        return '\n'.join(lines)


def clean(s: Any) -> str:
    return ' '.join(str(s or '').split()).strip()


def parse_value(s: Any):
    v = clean(s)
    m = VALUE.match(v)
    return (float(m.group(1).replace(',', '')), m.group(2) or '') if m else None


def table_facts(path: Path, start: int, end: int | None = None):
    """Every numeric fact keeps the raw table cell, row/column labels, page, and geometric origin."""
    facts: list[ExtractedFact] = []
    metadata: list[dict] = []
    with pymupdf.open(path) as doc:
        upper = min(end or len(doc), len(doc))
        for i in range(start-1, upper):
            page = doc[i]
            text = page.get_text('text', sort=True)
            metadata.append({'page': i+1, 'text': text, 'visual': bool(page.get_images() or len(page.get_drawings()) > 10)})
            try: tables = page.find_tables().tables
            except Exception: tables = []
            for ti,t in enumerate(tables):
                rows = t.extract()
                if not rows: continue
                header_index = max(range(min(3,len(rows))), key=lambda j: sum(bool(clean(v)) and parse_value(v) is None for v in rows[j]))
                headings = [clean(v) for v in rows[header_index]]
                numeric_cols = [c for c in range(len(headings)) if sum(parse_value(row[c]) is not None for row in rows[header_index+1:] if len(row)>c)>=2]
                label_count = min(numeric_cols) if numeric_cols else 1
                last_labels = [''] * min(label_count,len(headings))
                complex_header = any(not clean(headings[c]) for c in numeric_cols) or any(sum(parse_value(x) is not None for x in row)>=2 for row in rows[:header_index])
                for row in rows[header_index+1:]:
                    if len(row) != len(headings): continue
                    for j in range(min(label_count,len(row))):
                        value = clean(row[j]); parsed = parse_value(value)
                        if value and not parsed: last_labels[j] = value
                    label = clean(' / '.join(v for v in last_labels if v)) or 'row'
                    for col,cell in enumerate(row):
                        if col < label_count: continue
                        parsed = parse_value(cell)
                        if parsed is None: continue
                        value,unit = parsed
                        heading = headings[col] if col < len(headings) else ''
                        if not heading:
                            # Conservative: ambiguous merged header is flagged for review later.
                            heading = f'column_{col+1}'
                        title = clean(text.splitlines()[1] if len(text.splitlines()) > 1 else f'Page {i+1}')
                        evidence = f'{label} | {heading}: {clean(cell)}'
                        facts.append(ExtractedFact(page=i+1, topic=f'Page {i+1} table {ti+1}: {title}',
                                                   row=label, column=heading, value=value, unit=unit,
                                                   evidence=evidence, evidence_type='pdf_table_cell',
                                                   confidence='high' if not heading.startswith('column_') and not complex_header else 'low'))
    return facts, metadata


def compare_facts(facts: list[ExtractedFact], limit: int = 100) -> list[VerifiedFinding]:
    """Only compare metrics from the SAME page/table/column or SAME page/table/row and same unit.
    Suppress anonymous headers, sample counts and zero denominators; differences for percentages are pp.
    """
    groups = defaultdict(list)
    for idx,f in enumerate(facts):
        if any(term in f.row.casefold().split(' / ')[-1].strip().split() for term in ('total','subtotal','grand')):
            continue
        if any(term in f.topic.casefold() for term in ('count summary','sample bucket','margin bucket')):
            continue
        if f.confidence == 'low' or not f.column or f.column.startswith('column_'): continue
        # Row-group comparison, e.g. districts or parties for identical vote-share type.
        groups[(f.topic, f.column.casefold(), f.unit, 'rows')].append((idx,f))
        # Column-group comparison, e.g. Effective vs Regular for same party.
        groups[(f.topic, f.row.casefold(), f.unit, 'cols')].append((idx,f))
    findings=[]; seen=set()
    for (topic,axis,unit,direction),items in groups.items():
        unique={}
        for idx,f in items:
            label = f.row if direction == 'rows' else f.column
            if clean(label).casefold() not in unique:
                unique[clean(label).casefold()] = (idx,f)
            else:
                # duplicates are ambiguous, don't silently choose
                unique[clean(label).casefold()] = None
        items = [x for x in unique.values() if x is not None]
        if len(items) < 2: continue
        items.sort(key=lambda t:t[1].value)
        low,high=items[0],items[-1]
        if high[1].value==low[1].value: continue
        if len(findings)>=limit:break
        idxa,a=low; idxb,b=high
        key=tuple(sorted((idxa,idxb)))
        if key in seen: continue
        seen.add(key)
        label_a = a.row if direction=='rows' else a.column
        label_b = b.row if direction=='rows' else b.column
        diff=b.value-a.value
        if unit == '%':
            calculation=f'{b.value:g}% − {a.value:g}% = {diff:g} percentage points'
            observation=f'Within {axis}, {label_b} is {b.value:g}% vs {label_a} at {a.value:g}%, a {diff:g}-percentage-point difference.'
        elif a.value > 0:
            pct=diff/a.value*100
            calculation=f'({b.value:g} − {a.value:g}) / {a.value:g} × 100 = {pct:.1f}%'
            observation=f'Within {axis}, {label_b} reports {b.value:g} vs {label_a} at {a.value:g}, a {pct:.1f}% relative difference.'
        else:
            calculation=f'{b.value:g} − {a.value:g} = {diff:g}'
            observation=f'Within {axis}, {label_b} reports {b.value:g} vs {label_a} at {a.value:g}; difference {diff:g}.'
        findings.append(VerifiedFinding(title=f'{axis}: {label_a} vs {label_b}', observation=observation,
            calculation=calculation, fact_ids=[idxa,idxb],source_pages=sorted({a.page,b.page}),
            evidence=[a.evidence,b.evidence],caveat='Compare only if these table categories share the same population, definitions and sample basis.'))
    return findings

PROMPT = '''Extract structured quantitative facts from this PDF page. The source may contain business dashboards, multi-level tables, charts and maps. Read the PAGE IMAGE and text together. For every fact retain page, topic, row, column, numeric value, unit, short verbatim evidence from OCR/text or visible table cell. Never invent missing figures. Do not interpret table headings as metrics. Extract at most 60 clearly supported facts and flag ambiguous labels. For a chart with unreadable axes, flag it rather than guessing. Return the required schema. Political surveys: remain descriptive and neutral; do not provide targeted persuasion tactics or instructions directed at demographic groups.'''


def vision_facts(path: Path, metadata: list[dict], model: str, max_pages: int | None = None) -> tuple[list[ExtractedFact], list[dict]]:
    import base64
    from openai import OpenAI
    client=OpenAI()
    facts=[]; issues=[]
    with pymupdf.open(path) as doc:
        for md in metadata[:max_pages] if max_pages else metadata:
            page=doc[md['page']-1]
            png=page.get_pixmap(matrix=pymupdf.Matrix(1.65,1.65),alpha=False).tobytes('png')
            imageurl='data:image/png;base64,'+base64.b64encode(png).decode()
            response=client.responses.parse(model=model, instructions=PROMPT,
                input=[{'role':'user','content':[{'type':'input_text','text':f'PAGE={md["page"]}\nExtracted text:\n{md["text"][:16000]}'},
                                                 {'type':'input_image','image_url':imageurl}]}],text_format=PageFacts)
            data=response.output_parsed
            if data is None:
                issues.append({'page':md['page'],'issue':'Unparseable model output'});continue
            for f in data.facts:
                if f.page != md['page'] or not f.evidence.strip() or not f.topic.strip() or not f.row.strip() or not f.column.strip():
                    issues.append({'page':md['page'],'issue':'Dropped improperly sourced model fact'});continue
                f.confidence='medium'  # Image-based claims are provisionally sourced, not numerically verified.
                f.evidence_type='vision_unverified'
                facts.append(f)
            for issue in data.issues: issues.append({'page':md['page'],'issue':issue})
    return facts,issues


def dedup_facts(facts: list[ExtractedFact]):
    seen=set(); results=[]
    for f in facts:
        k=(f.page,clean(f.topic).casefold(),clean(f.row).casefold(),clean(f.column).casefold(),f.value,f.unit)
        if k not in seen: seen.add(k);results.append(f)
    return results

SYNTHESIS='''You are a senior analytical reviewer. Only use the supplied supported facts and calculated comparisons. Prioritize up to 12 findings by magnitude, relevance, reliability and consequences. Provide executive decision considerations, not decorative summaries. Cite numeric fact IDs. Never invent numbers, baselines, margins of error or causality. Distinguish observations, interpretations, recommended verification, and uncertainties. If data are election surveys, provide strictly neutral methodological and descriptive insights; do not give political persuasion, voter targeting or campaign optimization advice. When evidence insufficient, say exactly what extra data would be needed. No definitive claims about election results. Output 3 to 5 SHORT cohesive executive paragraphs in paragraphs, each 45 to 85 words maximum, joining related findings within the same topic. One heading and one easy-to-read paragraph per theme, with simple language, numeric values, and a concluding decision-relevant verification question where appropriate. Do not repeat 'Interpretation' or 'Follow-up' labels within the paragraph. Never compare totals to subgroups, sample size buckets to engagement, or incompatible measurements. Explicitly identify the unit (district counts versus vote shares, percentage points versus percent change). Use only supplied evidence, source_ids and source_pages for each paragraph. Avoid implying voter motivations or political campaigning advice. Keep notes optional and concise. Overall summary: maximum two sentences.''' 

def validate_brief_paragraphs(paragraphs, selected, max_paragraphs=5):
    selected_map={i:f for i,f in selected}
    output=[]
    for p in paragraphs[:max_paragraphs]:
        if not p.source_ids or any(i not in selected_map for i in p.source_ids): continue
        pages=sorted({selected_map[i].page for i in p.source_ids})
        if p.source_pages and not set(p.source_pages).issubset(set(pages)): continue
        if len(p.paragraph.split()) > 100 or len(p.paragraph.split()) < 12: continue
        if any(v in p.paragraph.lower() for v in ('target voters','persuade voters','outreach strategy')): continue
        output.append({'heading':p.heading.strip(), 'paragraph':p.paragraph.strip(), 'source_ids':p.source_ids, 'source_pages':pages})
    return output

def synthesize(facts: list[ExtractedFact], findings: list[VerifiedFinding], model: str):
    from openai import OpenAI
    client=OpenAI()
    # Limit input to avoid excessive cost, prioritize trusted table records and computed differences.
    # Balance page coverage instead of blindly selecting the first 350 facts.
    buckets=defaultdict(list)
    for i,f in enumerate(facts): buckets[f.page].append((i,f))
    selected=[]
    while len(selected)<350 and any(buckets.values()):
        for p in sorted(buckets):
            if buckets[p] and len(selected)<350: selected.append(buckets[p].pop(0))
    selected_ids={i for i,_ in selected}
    payload={'facts':[{'id':i,**f.model_dump()} for i,f in selected],
             'comparisons':[asdict(f) for f in findings[:60]]}
    response=client.responses.parse(model=model,instructions=SYNTHESIS,
        input=[{'role':'user','content':json.dumps(payload,ensure_ascii=False)}],text_format=SynthesizedNotes)
    result=response.output_parsed
    if result is None: return [],'No executive synthesis generated.',[]
    allowed=selected_ids
    notes=[]
    for note in result.notes:
        if note.source_ids and all(i in allowed for i in note.source_ids):
            notes.append(note.model_dump())
    paragraphs = validate_brief_paragraphs(result.paragraphs, selected, max_paragraphs=5)
    return notes, result.overall_summary, paragraphs


def analyze_report(path: Path, mode='offline', model='gpt-4o-mini',start=1,end=None, max_ai_pages=None):
    if mode not in ('offline','openai'):raise ValueError('mode must be offline or openai')
    if mode=='openai' and not os.getenv('OPENAI_API_KEY'):raise ValueError('Set OPENAI_API_KEY first')
    offline,metadata=table_facts(path,start,end)
    issues=[]
    if mode=='openai':
        ai,extra=vision_facts(path,metadata,model,max_ai_pages)
        issues+=extra
        # AI-extracted facts are kept but not used in audited deterministic calculations
        # until textual or cell-level verification confirms the same operand.
        offline_keys={(f.page,round(f.value,5),f.unit) for f in offline}
        for f in ai:
            if (f.page,round(f.value,5),f.unit) in offline_keys:
                f.confidence='medium'
            else:
                issues.append({'page':f.page,'issue':f'Vision-only fact requires review: {f.row} / {f.column} = {f.value}'})
        all_facts=dedup_facts(offline+ai)
    else: all_facts=dedup_facts(offline)
    calculated=compare_facts([f for f in all_facts if f.evidence_type=='pdf_table_cell'])
    notes=[];paragraphs=[];summary='Descriptive summary generated from structured table extraction; interpretations require domain context.'
    if mode=='openai':
        notes,summary,paragraphs=synthesize(all_facts,calculated,model)
    return DecisionReport(document=path.name, mode=mode,pages=len(metadata),facts=[f.model_dump() for f in all_facts],
                          findings=[asdict(f) for f in calculated],decision_notes=notes,brief_paragraphs=paragraphs,
                          issues=issues,page_summaries=[{'page':p['page'],'preview':clean(p['text'])[:220]} for p in metadata],summary=summary)
