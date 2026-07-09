
import streamlit as st
import pandas as pd
from pathlib import Path
import re, io
from datetime import datetime

st.set_page_config(page_title="LabSafeEdu竞赛聚焦版", page_icon="🧪", layout="wide")
DATA_DIR = Path(__file__).parent / "data"

@st.cache_data
def load_data():
    return {
        "knowledge": pd.read_csv(DATA_DIR/'knowledge_base.csv'),
        "hazards": pd.read_csv(DATA_DIR/'hazard_rectification_library.csv'),
        "risk": pd.read_csv(DATA_DIR/'risk_rules.csv'),
        "cases": pd.read_csv(DATA_DIR/'scenario_cases.csv'),
    }
data = load_data()

def norm(x): return str(x).lower().replace('，',' ').replace('。',' ')
def has(q, words):
    q=norm(q); return any(w in q for w in words)

def emergency_triage(q):
    qn = norm(q)
    if has(qn, ['误食','误服','吃到','喝到','吞了','入口']):
        return '应急兜底', '紧急处置', [('第一步','立即停止实验，吐出口中残留物并清水漱口；不要自行催吐或自行服药。'),('报告与就医','立即报告导师/安全管理员，保留试剂瓶、标签、SDS或照片，必要时联系急救人员。'),('闭环复盘','排查食品饮料入室、标签不清、二次容器混淆和安全告知不到位问题。')]
    if has(qn, ['头晕','恶心','胸闷','刺鼻','异味','吸入']):
        return '应急兜底', '需立即停止实验并报告', [('第一步','停止实验，离开可能暴露区域，到空气流通处休息，不要独自继续实验。'),('现场排查','排查通风橱、挥发性溶剂、气瓶泄漏、加热挥发等因素。'),('闭环复盘','记录实验内容、可能暴露物质、处置过程和人员状态。')]
    if has(qn, ['进眼','眼睛','酸溅','碱溅']):
        return '应急兜底', '紧急处置', [('第一步','立即使用洗眼器或大量流动清水冲洗眼部，并报告导师或安全管理员。'),('就医建议','确认化学品名称、浓度和SDS，必要时就医。')]
    if has(qn, ['洒到','撒到','泼到','溅到','弄到']) and has(qn, ['身上','手上','皮肤','衣服','同学','他人','别人']):
        return '应急兜底', '紧急处置', [('第一步','立即停止实验，让受污染人员远离污染源，用大量流动清水冲洗接触部位。'),('报告与就医','脱除被污染衣物，报告导师/安全管理员；涉及强酸、强碱或物质不明时及时就医。'),('闭环复盘','复核PPE、试剂转移、喷淋/洗眼器可达性和操作空间。')]
    if has(qn, ['着火','起火','火灾','冒烟']):
        return '应急兜底', '紧急处置', [('第一步','立即呼救报警；火势可控且自身安全时使用合适灭火器初期处置。'),('撤离原则','火势不可控或烟雾明显时立即撤离，不返回取物。')]
    return None

def risk_assess(text):
    q=norm(text); score=0; factors=[]
    for _,r in data['risk'].iterrows():
        kws=str(r['关键词']).split()
        if any(k.lower() in q for k in kws):
            score += int(r['分值']); factors.append((r['风险因素'], r['分值'], r['控制措施']))
    level = '重大风险' if score>=8 else ('高风险' if score>=4 else ('中风险' if score>=2 else '低风险'))
    return level, score, factors

def hazard_match(text):
    q=norm(text); best=None; score=0
    for _,r in data['hazards'].iterrows():
        alltxt=' '.join(map(str,[r['隐患描述'],r['隐患类别'],r['问题分析'],r['整改建议'],r['关键词']])).lower()
        s=sum(1 for w in re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z0-9]+', q) if w in alltxt)
        if s>score: best=r; score=s
    if best is not None and score>0: return best, '隐患库匹配'
    if has(q, ['门','门禁','不关门','未锁']):
        return pd.Series({'隐患类别':'场所与门禁管理','风险等级':'中风险','问题分析':'可能导致无关人员进入和责任追溯困难。','整改建议':'落实门禁管理，明确最后离室人员责任，外来人员登记。','复查要点':'门禁状态、离室记录、人员登记。'}), '智能兜底'
    if has(q, ['插排','插座','插线板','电线','电源']):
        return pd.Series({'隐患类别':'用电安全','风险等级':'高风险','问题分析':'可能造成短路、触电或火灾风险。','整改建议':'停止不规范用电，远离水源，检查线路和负荷。','复查要点':'线路、插排、断电、周边可燃物。'}), '智能兜底'
    if has(q, ['护目镜','手套','实验服','防护']):
        return pd.Series({'隐患类别':'个人防护','风险等级':'高风险','问题分析':'PPE不足可能导致飞溅、腐蚀或吸入暴露。','整改建议':'停止操作，按风险佩戴PPE并进行再教育。','复查要点':'PPE佩戴、现场告知、应急设施。'}), '智能兜底'
    return pd.Series({'隐患类别':'一般安全隐患','风险等级':'中风险','问题分析':'现场行为可能影响安全秩序和管理闭环。','整改建议':'记录问题、明确责任人和整改时限，复查销号。','复查要点':'整改记录、责任人、复查结果。'}), '智能兜底'

def answer(q):
    tri = emergency_triage(q)
    if tri: return tri
    if has(q, ['准备','今晚','明天','要做','实验前','需要注意','注意什么']) and has(q, ['实验','溶剂','加热','回流','气瓶','废液','乙醇','丙酮']):
        level, score, factors = risk_assess(q)
        rows=[('风险因素','；'.join([f'{a}({b}分)' for a,b,c in factors]) or '未命中高风险因素'),('控制措施','；'.join([c for a,b,c in factors]) or '完成基础检查'),('学习推荐','进入案例微课堂学习“矿泉水桶装废液”“设备过夜运行”等案例。'),('测评推荐','完成准入测评中危化品、废液、用电和应急题目。')]
        return '实验前风险研判', level, rows
    if has(q, ['巡检','发现','隐患','整改','有人','学生','无标签','不关门','插排','护目镜','废液']):
        h, src = hazard_match(q)
        return '隐患整改闭环', h['风险等级'], [('识别来源',src),('隐患类别',h['隐患类别']),('问题分析',h['问题分析']),('整改建议',h['整改建议']),('复查要点',h['复查要点']),('教学转化','可转化为案例微课堂和错题反馈。')]
    if has(q, ['新生','准入','第一次','进入实验室']):
        return '场景化准入学习', '学习指导', [('学习路径','制度学习→现场设施确认→准入考试→导师审核→首次实验陪同。'),('重点内容','危险源、PPE、废液、气瓶、用电、应急和离室检查。')]
    return '知识问答', '学习指导', [('建议','建议从“场景化准入学习”或“实验前风险研判”入口使用，系统会给出更完整的学习与管理闭环。')]

st.sidebar.title('🧪 LabSafeEdu')
page=st.sidebar.radio('选择功能模块',['首页','场景化准入学习','实验前风险研判','隐患整改闭环','案例微课堂','准入测评与错题反馈','管理数据看板','知识库维护'])
st.sidebar.caption('高校化学与材料类实验室安全准入与风险闭环教育智能体')

if page=='首页':
    st.title('LabSafeEdu高校实验室安全准入与风险闭环教育智能体')
    st.caption('聚焦“学前准入—实验前研判—案例学习—测评反馈—隐患整改—管理优化”的教育闭环')
    c1,c2,c3,c4=st.columns(4)
    c1.metric('检查实验室','133间')
    c2.metric('累计隐患','832项')
    c3.metric('化学安全隐患','384项')
    c4.metric('整改率','89%→100%')
    st.subheader('参赛亮点')
    st.dataframe(pd.DataFrame([
        ['场景化安全教育','学生输入实验任务，系统生成风险点、学习内容、案例和测评建议。'],
        ['实验前风险研判','自动识别有机溶剂、加热、夜间、废液、气瓶等风险因素，生成检查清单。'],
        ['隐患整改闭环','巡检隐患自动分类、判断风险等级、生成整改建议和复查要点。'],
        ['知识库持续更新','管理者可导入制度、PPT、Excel台账、案例材料，持续更新本地知识库。'],
        ['真实数据支撑','基于133间实验室和832项隐患形成安全画像。'],
    ],columns=['创新点','说明']),use_container_width=True)

elif page=='场景化准入学习':
    st.header('场景化准入学习')
    identity=st.selectbox('学习对象',['本科生','研究生','新进教师','实验技术人员','短期进入人员'])
    scene=st.text_area('学习场景','研一新生第一次进入化学类实验室，后续可能开展有机溶剂实验。')
    if st.button('生成个性化准入路径'):
        st.success('推荐学习路径：制度学习 → 现场设施确认 → 准入考试 → 导师审核 → 首次实验陪同/复核')
        st.dataframe(data['knowledge'][['一级类别','二级类别','标题','内容']].head(10),use_container_width=True)

elif page=='实验前风险研判':
    st.header('实验前风险研判')
    text=st.text_area('输入实验内容','今晚做有机溶剂加热回流实验，使用乙醇和丙酮，会产生有机废液。')
    if st.button('生成风险研判'):
        scene, level, rows=answer(text)
        st.metric('风险等级',level)
        st.dataframe(pd.DataFrame(rows,columns=['项目','内容']),use_container_width=True)
        checklist=['查阅SDS','确认PPE','检查通风橱/冷凝水/加热设备','准备专用废液桶和标签','完成导师审核或备案','实验结束离室检查']
        st.dataframe(pd.DataFrame({'实验前检查清单':checklist,'完成情况':['□']*len(checklist)}),use_container_width=True)

elif page=='隐患整改闭环':
    st.header('隐患整改闭环')
    text=st.text_area('输入巡检隐患','巡检发现学生用矿泉水桶装实验废液，桶身没有规范标签。')
    if st.button('生成整改闭环建议'):
        scene, level, rows=answer(text)
        st.metric('风险等级',level)
        st.dataframe(pd.DataFrame(rows,columns=['项目','内容']),use_container_width=True)

elif page=='案例微课堂':
    st.header('案例微课堂')
    name=st.selectbox('选择案例',data['cases']['案例名称'].tolist())
    row=data['cases'][data['cases']['案例名称']==name].iloc[0]
    st.metric('风险等级',row['风险等级'])
    for lab in ['案例描述','风险分析','正确做法','追问问题','教学目标']:
        st.markdown(f'**{lab}：** {row[lab]}')

elif page=='准入测评与错题反馈':
    st.header('准入测评与错题反馈')
    st.write('系统围绕危化品、废液、气瓶、用电、PPE、应急和离室检查自动生成测评与复习建议。')
    questions=pd.DataFrame([
        ['单选','实验废液应如何处理？','分类收集于专用废液桶并贴标签','废液管理'],
        ['判断','夜间开展高风险实验前应进行备案。','正确','夜间实验'],
        ['情景','巡检发现废液桶无标签，应如何整改？','补贴标签、完善台账、复查销号','隐患整改'],
    ],columns=['题型','题目','答案/解析','知识点'])
    st.dataframe(questions,use_container_width=True)
    weak=st.multiselect('选择薄弱知识点',['废液管理','夜间实验','隐患整改','个人防护','气瓶安全'])
    if weak: st.info('复习建议：进入制度知识库和案例微课堂学习：'+'、'.join(weak))

elif page=='管理数据看板':
    st.header('管理数据看板')
    df=pd.DataFrame([['实验场所方面',64],['安全设施方面',78],['基础安全方面',206],['化学安全方面',384],['生物安全方面',4],['其他隐患',96]],columns=['隐患类别','数量'])
    st.dataframe(df,use_container_width=True)
    chart_df = df.set_index('隐患类别')
    st.bar_chart(chart_df, height=360)
    st.caption('图表采用浏览器原生渲染，避免服务器缺少中文字体导致中文显示为方框。')
    st.info('管理建议：以化学安全和基础安全为重点，强化危化品、废液、气瓶、用电、夜间实验和大型仪器连续运行管理。')

elif page=='知识库维护':
    st.header('知识库维护')
    st.write('本模块用于展示知识库持续更新能力。正式部署可上传制度、PPT、Excel台账、PDF或文本资料，由管理者审核后写入本地知识库。')
    file=st.file_uploader('上传制度/台账/培训材料（演示入口）',type=['txt','md','csv','xlsx','docx','pptx','pdf'])
    extra=st.text_area('或粘贴新增制度条款')
    if st.button('生成入库建议'):
        if file or extra.strip():
            st.success('已生成入库预览：建议归入“制度知识库/隐患整改库/案例微课堂”，由管理者审核后写入。')
        else:
            st.warning('请先上传文件或粘贴内容。')
