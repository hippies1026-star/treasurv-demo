import copy
import csv
import html
import io
import json
import os
from datetime import datetime, date
from pathlib import Path
from uuid import uuid4

import streamlit as st
import plotly.graph_objects as graph
from dotenv import load_dotenv

from data import demo
from finance_engine import analyze, forecast, validate, validate_plan, fingerprint, KINDS
from agent import ask

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")
st.set_page_config(page_title="TreaSurv · 기업 자금운용", page_icon=str(ROOT / "logo.svg"), layout="wide", initial_sidebar_state="expanded")
st.html("<style>" + (ROOT / "styles.css").read_text(encoding="utf-8") + "</style>")

DEFAULT_STATE = {"data": demo(), "page": "대시보드", "entered": False, "history": [],
                 "logs": [], "approved": None, "proposal": None, "draft_policy": None,
                 "revision": 0, "last_sync": "데모 기본값", "ai_enabled": False}
for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = copy.deepcopy(value)
S = st.session_state


def stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(action, detail):
    S.logs.insert(0, {"시각": stamp(), "사용자": "가태용", "작업": action, "내용": detail})


def save(new, action):
    validate(new)
    S.data = copy.deepcopy(new)
    S.revision += 1
    S.draft_policy = None
    S.proposal = None
    log(action, "입력 변경 · 기존 정책은 새 계산과 비교해 재승인 필요")


def go(page):
    S.page = page


def money(n):
    return f"{n / 1e8:,.2f}억 원" if abs(n) >= 1e8 else f"{n / 1e4:,.0f}만 원"


def card_html(label, value, note, accent=False):
    return (f'<div class="metric-card {"accent" if accent else ""}"><div class="metric-label">{html.escape(label)}</div>'
            f'<div class="metric-value">{html.escape(value)}</div><div class="metric-note">{html.escape(note)}</div></div>')


def card(label, value, note, accent=False):
    st.html(card_html(label, value, note, accent))


def title(text, description):
    st.html('<div class="eyebrow">TREASURV / WORKSPACE</div>')
    st.title(text)
    st.caption(description)


def chart(a, extra=None):
    fig = graph.Figure()
    traces = [("계획대로 진행", a["base"], "#7149E8"), ("보호 기준 시나리오", a["protective"], "#E08A34")]
    if extra:
        traces.append(("선택한 비교 시나리오", extra, "#108F9E"))
    for name, rows, color in traces:
        fig.add_trace(graph.Scatter(x=[0] + [r["month"] for r in rows],
            y=[a["available"] / 1e8] + [r["balance"] / 1e8 for r in rows], name=name,
            mode="lines", line={"color": color, "width": 3},
            hovertemplate="%{x}개월 후 · %{y:.2f}억 원<extra>%{fullData.name}</extra>"))
    fig.add_hline(y=0, line_dash="dot", line_color="#C34F5C")
    fig.update_layout(height=340, margin=dict(l=8,r=8,t=15,b=5), paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#626B80"),
        legend=dict(orientation="h",y=1.16,x=0), hovermode="x unified",
        xaxis=dict(title="현재로부터 개월",dtick=3,gridcolor="#EEF0F5"),
        yaxis=dict(title="예상 가용 잔액 (억 원)",gridcolor="#EEF0F5"))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def table_rows(rows):
    return [{"개월 후": r["month"], "영업 유입(원)": round(r["inflow"]), "영업 지출(원)": round(r["outflow"]),
             "자금조달(원)": round(r["funding"]), "순유입(원)": round(r["net"]), "예상 잔액(원)": round(r["balance"])} for r in rows]


def csv_bytes(rows):
    out = io.StringIO()
    if rows:
        writer = csv.DictWriter(out, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return out.getvalue().encode("utf-8-sig")


def secret(name, default=""):
    try:
        return str(st.secrets.get(name, os.getenv(name, default)))
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return os.getenv(name, default)


def overview():
    d, a = S.data, analyze(S.data)
    title("우리 회사의 돈, 다음 기회를 준비하도록.", "현금 현황부터 미래 계획, 운용 시뮬레이션까지 한눈에 확인하세요.")
    st.html(f'<div class="hero"><span class="tag">자금운용 시뮬레이션</span><div class="hero-title">'
            f'{money(a["capacity"])}의 운용 여력을 검토할 수 있어요.</div><div class="muted">'
            f'앞으로 {d["target"]}개월의 스트레스 현금흐름과 {d["buffer"]}개월분 예비자금을 먼저 반영했어요.</div></div>')
    metrics = [("가용 현금", money(a["available"]), "사용 제한 자금 제외"),
               ("보호할 현금", money(a["floor"]), f"{d['target']}개월 기준 · Survival Floor"),
               ("운용 상한", money(a["capacity"]), "가용 현금 − 보호할 현금"),
               ("추가 수익 가정 / 연", money(a["incremental"]), "기존 이율 대비 · 세전 단순 계산")]
    st.html('<div class="metric-grid">' + ''.join(card_html(*metric, i == 3) for i, metric in enumerate(metrics)) + '</div>')
    if a["gap"]:
        st.warning(f"보호 기준 대비 {money(a['gap'])}이 부족합니다. 신규 운용액은 0원으로 계산했어요.")
    st.write("")
    left,right = st.columns([2.15,1])
    with left, st.container(border=True):
        st.subheader("24개월 현금 전망")
        chart(a)
        st.caption("보호 기준: 매출 감소·비용 증가 반영, 미수령 자금조달 제외. 운용수익은 이 전망에 합산하지 않았어요.")
    with right, st.container(border=True):
        st.subheader("다음 의사결정")
        st.markdown(f"**{len(d['plans'])}개 사업계획**이 반영되어 있어요.")
        st.write("채용이나 투자 일정이 바뀌었다면 먼저 계획을 업데이트하세요.")
        st.button("사업계획 확인 →", on_click=go,args=("사업계획",),width="stretch")
        st.divider()
        st.markdown(f"**{money(a['principal'])}** · 현재 운용 비중 {d['allocation']}%")
        st.caption(f"가정 연이율 {d['rate']:.2f}% · 기간 {d['tenor']}개월")
        st.button("운용수익 비교 →", on_click=go,args=("운용 시뮬레이터",),type="primary",width="stretch")
    with st.container(border=True):
        st.subheader("다가오는 사업계획")
        plans_table()


def plans_table():
    rows = [{"계획": p["name"], "유형": p["kind"], "시점": f"{p['month']}개월 후",
             "금액": money(p["amount"]), "반복": "매월" if p["recurring"] else "일회성",
             "상태": "확정" if p["confirmed"] else "예정"} for p in sorted(S.data["plans"],key=lambda p:p["month"])]
    if rows: st.dataframe(rows,hide_index=True,width="stretch")
    else: st.info("등록된 계획이 없습니다. 아래에서 추가해 주세요.")


def cash_page():
    d,a = S.data,analyze(S.data)
    title("현금 현황", "데모 데이터를 계좌·회계 연동 화면 형태로 보여줍니다.")
    cols=st.columns(3)
    for col,label,value in zip(cols,["총 현금","사용 제한 자금","가용 현금"],[d['cash'],d['restricted'],a['available']]):
        with col: card(label,money(value),"가상 연결 데이터")
    st.write("")
    with st.container(border=True):
        st.subheader("자금 구분")
        st.dataframe([{"구분":"즉시 사용 가능", "잔액(원)":a["available"]},
                      {"구분":"사용 제한 · 운용 제외", "잔액(원)":d["restricted"]}],hide_index=True,width="stretch")
        st.caption("계좌별 합계의 중복을 막기 위해 이 데모는 통합 잔액 한 곳에서 관리합니다.")
        st.button("연결 데이터 편집",on_click=go,args=("데이터 연결",),type="primary")


def forecast_page():
    title("현금흐름 예측", "미래 계획을 월별 입출금에 반영한 24개월 결정론적 전망입니다.")
    a=analyze(S.data)
    chart(a)
    choice=st.segmented_control("조회 기준",["기본","보호 기준"],default="기본")
    rows=table_rows(a["protective"] if choice=="보호 기준" else a["base"])
    st.dataframe(rows,hide_index=True,width="stretch")
    st.download_button("월별 전망 CSV 다운로드",csv_bytes(rows),"forecast.csv","text/csv")


def floor_page():
    d,a=S.data,analyze(S.data)
    title("보호할 현금", "목표 기간 동안 자금조달에 의존하지 않고 지켜둘 금액을 계산합니다.")
    c1,c2=st.columns([1,1.35])
    with c1,st.form("floor"):
        target=st.slider("목표 기간 (개월)",1,24,int(d["target"]))
        buffer=st.slider("추가 예비자금 (월 지출 배수)",0,6,int(d["buffer"]))
        rev=st.slider("매출 감소 가정 (%)",0,100,int(d["revenue_stress"]))
        cost=st.slider("비용 증가 가정 (%)",0,100,int(d["cost_stress"]))
        if st.form_submit_button("보호 기준 저장",type="primary"):
            save({**d,"target":target,"buffer":buffer,"revenue_stress":rev,"cost_stress":cost},"보호 기준 변경")
            st.rerun()
    with c2,st.container(border=True):
        card("현재 보호할 현금",money(a["floor"]),"정해진 스트레스 가정의 결과",True)
        st.markdown(f"- 기간 중 최대 누적 부족액: **{money(a['deficit'])}**\n- 추가 예비자금: **{money(a['reserve'])}**")
        st.markdown("**계산 방식**\n\n보호할 현금 = 최대 누적 부족액 + 현재 월 지출 × 예비 개월 수")
        st.caption("현재부터 목표 기간까지의 모든 월을 확인합니다. 미수령 자금조달과 미확정 추가 매출은 보호 기준에서 제외합니다. 확률 모델이나 검증된 안전 보장이 아닙니다.")


def plans_page():
    title("사업계획", "현재는 데이터로 읽고, 미래는 계획으로 알려주세요.")
    plans_table()
    with st.container(border=True),st.form("new_plan",clear_on_submit=True):
        st.subheader("새 계획 추가")
        c1,c2=st.columns(2)
        name=c1.text_input("계획 이름",placeholder="예: 개발자 2명 채용")
        kind=c2.selectbox("계획 유형",KINDS)
        month=c1.number_input("현재로부터 시작 월",1,24,3)
        amount=c2.number_input("금액 (만 원 · 채용은 추가 월 총인건비)",min_value=1.0,value=600.0,step=100.0)
        recurring=c1.checkbox("시작 월부터 매월 반복")
        confirmed=c2.checkbox("확정된 계획",value=True)
        if st.form_submit_button("계획 추가",type="primary"):
            p={"id":uuid4().hex,"name":name.strip(),"kind":kind,"month":month,"amount":amount*1e4,"recurring":recurring,"confirmed":confirmed}
            try:
                validate_plan(p)
                save({**S.data,"plans":S.data["plans"]+[p]},"사업계획 추가: "+p["name"])
                st.rerun()
            except ValueError as exc: st.error(str(exc))
    if S.data["plans"]:
        with st.expander("기존 계획 삭제"):
            options={p["id"]:p["name"] for p in S.data["plans"]}
            selected=st.selectbox("삭제할 계획",list(options),format_func=lambda x:options[x])
            if st.button("선택한 계획 삭제"):
                save({**S.data,"plans":[p for p in S.data["plans"] if p["id"]!=selected]},"사업계획 삭제")
                st.rerun()
    st.caption("기존 계획의 금액·시점 수정은 데이터 연결 화면의 백업 JSON 대신 삭제 후 재등록으로 진행합니다. 반복 채용은 추가 월 인건비 총액을 입력하세요.")


def scenario_page():
    title("시나리오 비교", "투자 일정과 매출·비용이 달라지는 경우를 저장된 기준과 비교합니다.")
    c1,c2,c3=st.columns(3)
    delay=c1.slider("자금조달 지연 (개월)",0,12,3)
    rev=c2.slider("매출 감소 (%)",0,100,25)
    cost=c3.slider("비용 증가 (%)",0,100,10)
    d={**S.data,"revenue_stress":rev,"cost_stress":cost}
    a=analyze(S.data)
    scenario=forecast(d,stress=True,funding_delay=delay)
    comparison=analyze(d)
    cols=st.columns(3)
    with cols[0]:card("선택 시나리오 최저 잔액",money(min([a['available']]+[r['balance'] for r in scenario])),"24개월 · 자금조달 반영")
    with cols[1]:card("변경된 보호할 현금",money(comparison['floor']),"자금조달 제외 · 목표 기간 기준")
    with cols[2]:card("변경된 운용 상한",money(comparison['capacity']),"현재 운용 정책에는 아직 미반영")
    chart(a,scenario)
    st.caption("보호 기준은 원래부터 미수령 자금조달을 제외하므로, 조달 지연만 바꿔서는 보호할 현금이 변하지 않습니다.")


def treasury_page():
    d=S.data
    title("운용 시뮬레이터", "보호할 현금 밖의 금액으로, 추가 수익의 크기를 비교하세요.")
    left,right=st.columns([1,1.45])
    with left,st.form("yield"):
        allocation=st.slider("운용 상한 중 배분 비중 (%)",0,100,int(d["allocation"]))
        rate=st.number_input("비교할 연이율 가정 (%)",0.0,20.0,float(d["rate"]),0.1)
        baseline=st.number_input("기존 보관 연이율 가정 (%)",0.0,20.0,float(d["baseline_rate"]),0.1)
        tenor=st.slider("비교 기간 (개월)",1,12,int(d["tenor"]))
        if st.form_submit_button("수익 가정 적용",type="primary"):
            save({**d,"allocation":allocation,"rate":rate,"baseline_rate":baseline,"tenor":tenor},"운용 시뮬레이션 변경")
            st.rerun()
    a=analyze(d)
    with right,st.container(border=True):
        card("기간 중 추가 수익 가정",money(a["incremental"]*d["tenor"]/12),f"{d['tenor']}개월 · 기존 이율 대비 · 세전",True)
        st.markdown(f"**운용액 {money(a['principal'])}** / 운용 상한 {money(a['capacity'])}")
        st.dataframe([{"항목":"기존 방식 이자","금액":money(a['principal']*d['baseline_rate']/100*d['tenor']/12)},
                      {"항목":"비교 방식 이자","금액":money(a['tenor_interest'])},
                      {"항목":"차이","금액":money(a['incremental']*d['tenor']/12)}],hide_index=True,width="stretch")
        st.caption("금리는 직접 입력한 가정입니다. 원금이 기간 내내 유지되고 만기에 이자를 받는 단리로 계산하며, 세금·수수료·중도해지·금리변동을 반영하지 않습니다.")
    st.info("이 화면은 운용 여력과 가정 수익을 비교합니다. 실제 상품 가입이나 송금은 실행하지 않습니다.")
    if d["tenor"]>d["target"]:
        st.warning("비교 기간이 보호 기준의 목표 기간보다 깁니다. 정책 초안을 만들기 전에 목표 기간을 늘려 주세요.")
    if st.button("이 조건으로 정책 초안 만들기",type="primary",disabled=a["principal"]<=0 or d["tenor"]>d["target"]):
        S.draft_policy={"fingerprint":a["fingerprint"],"principal":a["principal"],"rate":d["rate"],"tenor":d["tenor"],"floor":a["floor"],"created":stamp()}
        log("운용 정책 초안 생성",money(a["principal"]))
    if S.draft_policy:
        st.success("정책 초안이 준비됐어요. 승인은 데모 기록만 남깁니다.")
        c1,c2=st.columns(2)
        if c1.button("초안 승인 · 데모",width="stretch"):
            if S.draft_policy["fingerprint"]!=fingerprint(S.data):
                st.error("데이터가 변경됐습니다. 새 초안을 만드세요.")
            else:
                S.approved={**S.draft_policy,"approved_at":stamp(),"by":"가태용"}
                S.draft_policy=None
                log("운용 정책 승인 · 데모","실제 금융거래 없음")
                st.rerun()
        if c2.button("초안 취소",width="stretch"):
            S.draft_policy=None
            log("운용 정책 초안 취소","")
            st.rerun()
    if S.approved:
        valid=S.approved["fingerprint"]==fingerprint(S.data)
        st.caption(f"최근 승인: {S.approved['approved_at']} · {money(S.approved['principal'])} · {'현재 데이터와 일치' if valid else '입력 변경으로 재승인 필요'}")


def ai_page():
    title("AI CFO", "재무 도구로 계산하고, 대화로 설명합니다. 계획 반영은 확인 후 진행하세요.")
    key=secret("GROQ_API_KEY") if S.ai_enabled else ""
    st.caption("Groq 연결 모드 · AI 생성 설명" if key else "로컬 계산 모드 · 외부 AI 미연결")
    st.caption("예: ‘투자유치가 3개월 늦어지면?’ / ‘3개월 후 월 총 1,200만 원의 확정 채용계획을 제안해 줘.’")
    for m in S.history:
        with st.chat_message(m["role"]):st.markdown(m["content"])
    question=st.chat_input("회사 자금과 앞으로의 계획을 물어보세요")
    if question:
        with st.chat_message("user"):st.write(question)
        try:
            with st.spinner("현금과 사업계획을 확인하고 있어요…"):
                answer,proposal=ask(question,S.data,S.history,key,secret("GROQ_MODEL","llama-3.3-70b-versatile"))
            S.history += [{"role":"user","content":question},{"role":"assistant","content":answer}]
            if proposal:S.proposal={"plan":proposal,"fingerprint":fingerprint(S.data)}
            with st.chat_message("assistant"):st.markdown(answer)
        except RuntimeError as exc:st.error(str(exc))
    if S.proposal:
        with st.container(border=True):
            st.subheader("AI가 제안한 계획 · 승인 대기")
            p=S.proposal["plan"]
            st.write(f"{p['name']} · {p['kind']} · {p['month']}개월 후 · {money(p['amount'])} · {'매월' if p['recurring'] else '일회성'}")
            st.caption("확정" if p["confirmed"] else "예정")
            c1,c2=st.columns(2)
            if c1.button("계획에 반영",type="primary"):
                if S.proposal["fingerprint"]!=fingerprint(S.data):st.error("입력이 변경됐습니다. 다시 제안받아 주세요.")
                else:
                    save({**S.data,"plans":S.data["plans"]+[{**p,"id":uuid4().hex}]},"AI 계획 승인")
                    st.rerun()
            if c2.button("제안 버리기"):
                S.proposal=None
                st.rerun()


def integrations_page():
    d=S.data
    title("데이터 연결", "은행·회계 연결을 가정한 데모입니다. 값을 바꾸면 모든 계산에 반영됩니다.")
    c1,c2=st.columns(2)
    with c1,st.container(border=True):
        st.subheader("은행 잔액")
        st.write("데모 데이터 연결")
        st.caption("실제 은행 API 미연결")
    with c2,st.container(border=True):
        st.subheader("회계 입출금")
        st.write("데모 데이터 연결")
        st.caption("매출 인식액이 아닌 월 현금 수취액 기준")
    with st.form("data_edit"):
        c1,c2=st.columns(2)
        cash=c1.number_input("총 현금 (만 원)",min_value=0.0,value=float(d['cash']/1e4),step=1000.0)
        restricted=c2.number_input("사용 제한 자금 (만 원)",min_value=0.0,value=float(d['restricted']/1e4),step=100.0)
        inflow=c1.number_input("월평균 영업 현금유입 (만 원)",min_value=0.0,value=float(d['inflow']/1e4),step=100.0)
        outflow=c2.number_input("월평균 영업 현금지출 (만 원)",min_value=0.0,value=float(d['outflow']/1e4),step=100.0)
        if st.form_submit_button("데모 데이터 저장",type="primary"):
            try:
                save({**d,"cash":cash*1e4,"restricted":restricted*1e4,"inflow":inflow*1e4,"outflow":outflow*1e4},"데모 데이터 변경")
                S.last_sync=stamp()
                st.rerun()
            except ValueError as exc:st.error(str(exc))
    st.caption("마지막 데모 변경: "+S.last_sync)


def reports_page():
    title("보고서", "현재 입력과 계산 결과를 내려받아 검토하거나 다음 시연에 다시 불러오세요.")
    a=analyze(S.data)
    text=(f"# TreaSurv 데모 분석 보고서\n\n작성: {stamp()}\n\n회사: {S.data['company']} · 가태용\n\n"
          f"가용 현금: {money(a['available'])}\n\n보호할 현금: {money(a['floor'])}\n\n운용 상한: {money(a['capacity'])}\n\n"
          f"선택 운용액: {money(a['principal'])}\n\n연 추가 수익 가정: {money(a['incremental'])}\n\n"
          "금리는 사용자 가정, 세전 단리. 실제 금융 연동 및 거래 없음. 월별 모델은 월중 자금 부족을 평가하지 않음.\n\n"
          "## 분석 조건\n\n```json\n"+json.dumps(S.data,ensure_ascii=False,indent=2)+"\n```\n")
    st.markdown(text.split("## 분석 조건")[0])
    c1,c2,c3=st.columns(3)
    c1.download_button("분석 보고서 (.md)",text,"TreaSurv-report.md")
    c2.download_button("현금 전망 (.csv)",csv_bytes(table_rows(a['base'])),"TreaSurv-forecast.csv","text/csv")
    backup={"schema":1,"data":S.data}
    c3.download_button("시연 데이터 백업 (.json)",json.dumps(backup,ensure_ascii=False,indent=2),"TreaSurv-demo.json","application/json")
    upload=st.file_uploader("시연 데이터 복원",type=["json"])
    if upload and st.button("백업 불러오기"):
        try:
            if upload.size>1_000_000:raise ValueError("백업 파일은 1MB 이하로 올려 주세요.")
            raw=json.load(upload)
            if raw.get("schema")!=1:raise ValueError("지원하지 않는 백업 형식입니다.")
            data=raw["data"]
            if set(data)!=set(demo()):raise ValueError("백업 데이터 항목을 확인하세요.")
            if not isinstance(data['plans'],list) or len(data['plans'])>100:raise ValueError("사업계획은 최대 100개입니다.")
            if not isinstance(data['company'],str) or not 1<=len(data['company'])<=60:raise ValueError("회사명을 확인하세요.")
            data['owner']='가태용'
            if len({p['id'] for p in data['plans']})!=len(data['plans']):raise ValueError("중복된 계획 ID가 있습니다.")
            save(data,"데이터 복원")
            st.rerun()
        except (ValueError,KeyError,TypeError,AttributeError):st.error("백업 형식 또는 금액·계획 값이 올바르지 않습니다.")


def team_page():
    title("팀", "가상 워크스페이스의 구성원 정보입니다.")
    st.dataframe([{"이름":"가태용","역할":"대표 / 워크스페이스 관리자","이메일":"demo@example.com","환경":"데모"}],hide_index=True,width="stretch")
    st.info("실제 회원 초대·인증·권한 관리는 연결하지 않은 시연용 화면입니다.")


def logs_page():
    title("변경 기록", "이번 브라우저 세션에서 일어난 입력 변경과 정책 승인을 확인하세요.")
    if S.logs:
        st.dataframe(S.logs,hide_index=True,width="stretch")
        st.download_button("변경 기록 CSV",csv_bytes(S.logs),"TreaSurv-log.csv","text/csv")
    else:st.info("아직 변경 기록이 없습니다. 사업계획이나 운용 조건을 바꿔 보세요.")
    st.caption("세션 내 데모 로그입니다. 영구 보관되거나 위변조 방지된 감사 로그가 아닙니다.")


def settings_page():
    title("설정", "회사 정보와 AI 연결을 관리합니다.")
    with st.form("company"):
        company=st.text_input("고객사 이름",S.data["company"],max_chars=60)
        st.text_input("대표자","가태용",disabled=True)
        if st.form_submit_button("회사 정보 저장"):
            if company.strip():
                save({**S.data,"company":company.strip()},"회사 정보 변경")
                st.rerun()
            else:st.error("회사 이름을 입력하세요.")
    with st.container(border=True):
        st.subheader("Groq AI 연결")
        configured=bool(secret("GROQ_API_KEY"))
        st.write("API 키 설정됨" if configured else "API 키가 아직 없어요")
        st.caption("프로젝트의 .env에 GROQ_API_KEY를 입력하거나 Streamlit Secrets를 설정하세요. 키 자체는 화면에 표시하지 않습니다.")
        def set_ai_mode():
            S.ai_enabled = S._ai_enabled
        st.toggle("Groq AI 사용",value=S.ai_enabled,key="_ai_enabled",on_change=set_ai_mode,disabled=not configured)
        st.caption("켜면 AI CFO 질문과 집계 재무정보·사업계획이 Groq로 전송됩니다. 실제 개인정보 대신 데모 데이터로 시연하세요.")
    with st.expander("데모 환경 안내"):
        st.write("TreaSurv · 주식회사 트레서브랩스 (가상)")
        st.write("대표자: 가태용 / 본사: 서울특별시 동대문구 한국외국어대학교 근처 자취방 (데모)")
        st.write("사업자등록번호: 000-00-00000 (미등록 데모 표기)")
        st.caption("인증·은행 연동·거래 실행·영구 저장은 제공하지 않습니다. 브라우저 연결이 끝나면 세션 데이터가 사라질 수 있으니 보고서에서 백업하세요.")
    if st.button("모든 데모 데이터 초기화"):
        for key,value in DEFAULT_STATE.items():S[key]=copy.deepcopy(value)
        st.rerun()


PAGES = {"대시보드":overview,"현금 현황":cash_page,"현금흐름 예측":forecast_page,
         "보호할 현금":floor_page,"사업계획":plans_page,"시나리오 비교":scenario_page,
         "운용 시뮬레이터":treasury_page,"AI CFO":ai_page,"데이터 연결":integrations_page,
         "보고서":reports_page,"팀":team_page,"변경 기록":logs_page,"설정":settings_page}

if not S.entered:
    left,center,right=st.columns([1,1.5,1])
    with center:
        st.html('<div class="brand"><div class="logo">TS</div><div class="brand-name">TreaSurv</div></div>')
        st.title("기업의 현금에,\n다음 가능성을.")
        st.write("꼭 필요한 현금은 보호하고, 운용 여력은 더 명확하게.")
        with st.container(border=True):
            st.subheader("가태용님의 데모 워크스페이스")
            st.caption("NOVA Labs · 가상 재무 데이터가 준비되어 있어요.")
            if st.button("데모 시작하기 →",type="primary",width="stretch"):
                S.entered=True
                st.rerun()
            st.caption("실제 로그인 없이 체험할 수 있는 공모전 프로토타입입니다.")
    st.stop()

with st.sidebar:
    st.html('<div class="brand"><div class="logo">TS</div><div><div class="brand-name">TreaSurv</div><div class="muted">기업 자금운용 워크스페이스</div></div></div>')
    st.markdown("**"+S.data["company"]+"**")
    st.caption("가태용 · 데모 관리자")
    groups={"현황":["대시보드","현금 현황","현금흐름 예측"],"계획과 운용":["보호할 현금","사업계획","시나리오 비교","운용 시뮬레이터","AI CFO"],
            "워크스페이스":["데이터 연결","보고서","팀","변경 기록","설정"]}
    for group,pages in groups.items():
        st.caption(group)
        for page in pages:
            st.button(page,key="nav_"+page,type="primary" if S.page==page else "secondary",width="stretch",on_click=go,args=(page,))
    st.divider()
    st.caption("PROTOTYPE · 금융거래 없음")
    if st.button("시작 화면으로"):
        S.entered=False
        st.rerun()

st.caption(f"{S.data['company']}  /  {S.page}                                      DEMO WORKSPACE")
PAGES.get(S.page,overview)()
st.html('<div class="footer"><strong>TreaSurv</strong> · 대표 가태용 · 공모전용 프로토타입<br>가상 재무 데이터 · 실제 은행 연동 및 금융거래 없음 · 입력한 조건에 따른 시뮬레이션</div>')
