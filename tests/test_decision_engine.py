from pathlib import Path
from insight_generator.decision_engine import ExtractedFact,parse_value,compare_facts,analyze_report

def fact(row,col,value,unit='%'):
    return ExtractedFact(page=2,topic='Page 2 table 1: sample',row=row,column=col,value=value,unit=unit,evidence=f'{row} {col} {value}')

def test_parse_numbers():
    assert parse_value('30,791') == (30791.0,'')
    assert parse_value('44.0%') == (44.0,'%')
    assert parse_value('NDA') is None

def test_percentage_point_arithmetic():
    xs=compare_facts([fact('A','overall',44),fact('B','overall',36.7)])
    assert len(xs)>=1
    assert '7.3' in xs[0].calculation
    assert xs[0].source_pages == [2]

def test_ambiguous_headers_excluded():
    a=fact('A','column_4',44);a.confidence='low'
    assert compare_facts([a,fact('B','column_4',36.7)]) == []

def test_facts_are_provenance_aware():
    x=fact('A','overall',44)
    assert x.page==2 and x.evidence


def test_real_report_structured_tables():
    path=Path(__file__).resolve().parents[1]/'tests'/'fixtures'/'report_extract.pdf'
    if not path.exists():return
    report=analyze_report(path,start=1,end=2)
    assert report.facts
    assert report.findings

def test_total_row_not_compared_to_party():
    xs=compare_facts([fact('Total','Effective VS',38,''),fact('JSP','Effective VS',0,'')])
    assert xs == []

def test_sample_bucket_suppressed():
    a=fact('800 to 1000','Effective VS',0,'');a.topic='Count Summary: District'
    b=fact('800 to 1000','Regular VS',6,'');b.topic='Count Summary: District'
    assert compare_facts([a,b]) == []

def test_validated_short_paragraph():
    from insight_generator.decision_engine import BriefParagraph, validate_brief_paragraphs
    source=fact('NDA','Effective VS',20,'')
    p=BriefParagraph(heading='Method difference',paragraph='The district counts change between the two reported methods, so the definitions should be checked before interpreting district-level differences.',source_ids=[9],source_pages=[2])
    assert len(validate_brief_paragraphs([p],[(9,source)])) == 1
    p.source_ids=[999]
    assert validate_brief_paragraphs([p],[(9,source)]) == []
