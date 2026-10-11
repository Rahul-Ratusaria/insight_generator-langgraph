"""New decision intelligence dashboard. Start: python -m streamlit run decision_app.py"""
import json, os, tempfile
from pathlib import Path
import pandas as pd
import streamlit as st
from insight_generator.decision_graph import run_decision_graph

st.set_page_config(page_title='InsightForge Decision Intelligence',page_icon='📊',layout='wide')
st.title('InsightForge | Decision Intelligence')
st.caption('Evidence-aware multi-page PDF analytics · deterministic calculations · optional multimodal AI · review-first methodology')
with st.sidebar:
    st.header('Configuration')
    mode=st.selectbox('Analysis mode',['offline','openai'],help='Offline parses clearly identified PDF tables. OpenAI adds page-image extraction and decision synthesis; requires a paid API key.')
    model=st.text_input('Vision + reasoning model','gpt-4o-mini',disabled=mode=='offline')
    first=st.number_input('First page',min_value=1,value=1)
    last=st.number_input('Last page (0 = all)',min_value=0,value=0)
    max_ai=st.number_input('Maximum AI pages (0 = selected range)',min_value=0,value=0,disabled=mode=='offline')
    st.warning('PDFs containing confidential or personal information should not be sent to an external AI provider without authorization and an appropriate data-processing agreement.')
file=st.file_uploader('Upload a PDF report',type='pdf')
if file and st.button('Generate decision intelligence',type='primary'):
    if mode=='openai' and not os.environ.get('OPENAI_API_KEY'):
        st.error('Set OPENAI_API_KEY in the terminal before starting Streamlit.')
    else:
        with tempfile.NamedTemporaryFile(suffix='.pdf',delete=False) as tmp:
            tmp.write(file.getvalue());path=Path(tmp.name)
        try:
            with st.spinner('Extracting structured tables, computing auditable comparisons and assembling decisions...'):
                st.session_state['decision_report']=run_decision_graph(path,mode=mode,model=model,start=int(first),end=int(last) or None,max_ai_pages=int(max_ai) or None)
        except Exception as error:
            st.error(str(error))
        finally:path.unlink(missing_ok=True)
if 'decision_report' in st.session_state:
    r=st.session_state['decision_report']
    a,b,c,d=st.columns(4)
    a.metric('Pages',r.pages);b.metric('Extracted numeric facts',len(r.facts));c.metric('Audited comparisons',len(r.findings));d.metric('Review flags',len(r.issues))
    t1,t2,t3,t4=st.tabs(['Executive decisions','Evidence-backed comparisons','Structured metrics & QA','Download'])
    with t1:
        st.subheader('Executive brief')
        if r.brief_paragraphs:
            for p in r.brief_paragraphs:
                st.markdown('#### '+p['heading'])
                st.write(p['paragraph'])
                st.caption('Sources: PDF page(s) '+', '.join(map(str,p['source_pages'])))
                st.divider()
        else:
            st.info('No source-validated narrative paragraphs were returned. Review the raw observations below; the model may need better table evidence.')
        with st.expander('Overall assessment and detailed evidence notes',expanded=False):
            st.write(r.summary)
            if mode=='offline':st.info('Paragraph synthesis requires OpenAI mode. Offline mode provides auditable comparisons.')
            for n in r.decision_notes:
                st.markdown('**'+n['title']+'**')
                st.write(n['finding'])
                st.write('Interpretation: '+n['implication'])
                st.write('Review question: '+n['suggested_next_step'])
                st.caption('Source fact IDs: '+str(n['source_ids'])+' | Caveat: '+n['caveat'])
        st.caption('These are descriptive survey findings, not causal findings or predictions.')
    with t2:
        if not r.findings:st.warning('No safe comparisons under current table-header confidence constraints. For complex charts, try image-aware OpenAI mode, then manually verify any vision-derived cells.')
        for f in r.findings[:100]:
            with st.expander(f['title']):
                st.write(f['observation']);st.code(f['calculation'],language=None)
                st.caption('Evidence: '+' | '.join(f['evidence']))
                st.caption('Pages '+', '.join(map(str,f['source_pages']))+' · '+f['caveat'])
    with t3:
        if r.facts:
            df=pd.DataFrame(r.facts)
            st.dataframe(df,use_container_width=True,hide_index=True)
            if 'page' in df:st.bar_chart(df.groupby('page').size())
        else:st.warning('No numeric tables detected. This may require vision/OCR.')
        if r.issues:
            with st.expander(f'Review flags ({len(r.issues)})'):
                st.dataframe(pd.DataFrame(r.issues),use_container_width=True,hide_index=True)
    with t4:
        st.download_button('Download full report JSON',r.json(),'insightforge_decision_report.json','application/json')
        st.download_button('Download executive Markdown',r.markdown(),'insightforge_decision_brief.md','text/markdown')
        if r.facts:
            import io
            buffer=io.BytesIO()
            with pd.ExcelWriter(buffer,engine='openpyxl') as writer:
                pd.DataFrame(r.facts).to_excel(writer,sheet_name='Source Metrics',index=False)
                pd.DataFrame(r.findings).to_excel(writer,sheet_name='Comparisons',index=False)
                pd.DataFrame(r.decision_notes).to_excel(writer,sheet_name='Decision Notes',index=False)
                pd.DataFrame(r.issues).to_excel(writer,sheet_name='Review Queue',index=False)
            st.download_button('Download analyst workbook',buffer.getvalue(),'insightforge_analysis.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
