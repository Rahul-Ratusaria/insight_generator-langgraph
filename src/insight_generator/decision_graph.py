"""LangGraph orchestration: ingest -> visual supplement -> audit -> conditional synthesis -> finish.
The data-analysis functions are testable outside LangGraph; this graph is the production path.
"""
from pathlib import Path
from typing import TypedDict, Any
from langgraph.graph import StateGraph, START, END
from .decision_engine import table_facts, vision_facts, compare_facts, synthesize, dedup_facts, DecisionReport

class DecisionState(TypedDict, total=False):
    pdf_path: str
    mode: str
    model: str
    start: int
    end: int | None
    max_ai_pages: int | None
    facts: list
    metadata: list
    findings: list
    notes: list
    paragraphs: list
    issues: list
    summary: str
    report: Any

def ingest(state: DecisionState):
    facts,metadata=table_facts(Path(state['pdf_path']),state.get('start',1),state.get('end'))
    return {'facts':facts,'metadata':metadata,'issues':[]}

def should_vision(state:DecisionState):
    return 'vision' if state['mode']=='openai' else 'audit'

def extract_vision(state:DecisionState):
    ai,issues=vision_facts(Path(state['pdf_path']),state['metadata'],state['model'],state.get('max_ai_pages'))
    canonical=state['facts']; keys={(x.page,round(x.value,5),x.unit) for x in canonical}
    for f in ai:
        if (f.page,round(f.value,5),f.unit) not in keys:
            issues.append({'page':f.page,'issue':f'Vision-derived value awaiting visual validation: {f.row} / {f.column} = {f.value}'})
    return {'facts':dedup_facts(canonical+ai),'issues':issues}

def audit(state:DecisionState):
    facts=[x for x in state['facts'] if x.evidence_type=='pdf_table_cell']
    return {'findings':compare_facts(facts),'summary':'Numeric comparisons are limited to confidently identified, same-scope table cells.'}

def should_synthesize(state:DecisionState):
    return 'synthesis' if state['mode']=='openai' else 'final'

def synthesis(state:DecisionState):
    notes,summary,paragraphs=synthesize(state['facts'],state['findings'],state['model'])
    return {'notes':notes,'summary':summary,'paragraphs':paragraphs}

def final(state:DecisionState):
    report=DecisionReport(document=Path(state['pdf_path']).name,mode=state['mode'],pages=len(state['metadata']),
        facts=[x.model_dump() for x in state['facts']],findings=[__import__('dataclasses').asdict(x) for x in state['findings']],
        decision_notes=state.get('notes',[]),brief_paragraphs=state.get('paragraphs',[]),issues=state.get('issues',[]),
        page_summaries=[{'page':p['page'],'preview':p['text'][:200]} for p in state['metadata']],summary=state.get('summary',''))
    return {'report':report}

def build_decision_graph():
    g=StateGraph(DecisionState)
    g.add_node('ingest',ingest);g.add_node('vision',extract_vision);g.add_node('audit',audit)
    g.add_node('synthesis',synthesis);g.add_node('final',final)
    g.add_edge(START,'ingest')
    g.add_conditional_edges('ingest',should_vision,{'vision':'vision','audit':'audit'})
    g.add_edge('vision','audit')
    g.add_conditional_edges('audit',should_synthesize,{'synthesis':'synthesis','final':'final'})
    g.add_edge('synthesis','final');g.add_edge('final',END)
    return g.compile()

def run_decision_graph(path,mode='offline',model='gpt-4o-mini',start=1,end=None,max_ai_pages=None):
    import os
    if mode not in ('offline','openai'):raise ValueError('Invalid mode')
    if mode=='openai' and not os.environ.get('OPENAI_API_KEY'):raise ValueError('OPENAI_API_KEY is required')
    state=build_decision_graph().invoke({'pdf_path':str(path),'mode':mode,'model':model,'start':start,'end':end,'max_ai_pages':max_ai_pages})
    return state['report']
