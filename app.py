import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime
import platform

# 自动适配中文字体，减少图表中文乱码
plt.rcParams["axes.unicode_minus"] = False
if platform.system() == "Windows":
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
elif platform.system() == "Darwin":
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "PingFang SC", "Heiti SC", "DejaVu Sans"]
else:
    plt.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "WenQuanYi Micro Hei", "DejaVu Sans"]

st.set_page_config(
    page_title="LabSafeEdu实验室安全智能体",
    page_icon="🧪",
    layout="wide"
)

DATA_DIR = Path(__file__).parent / "data"

# ---------- 基础样式 ----------
st.markdown("""
<style>
.main-title {
    font-size: 32px;
    font-weight: 800;
    margin-bottom: 0.2rem;
}
.sub-title {
    font-size: 17px;
    color: #666;
    margin-bottom: 1.2rem;
}
.card {
    padding: 1.1rem 1.2rem;
    border-radius: 14px;
    border: 1px solid #e6e6e6;
    background: #fafafa;
    margin-bottom: 1rem;
}
.metric-card {
    padding: 1rem;
    border-radius: 14px;
    border: 1px solid #e6e6e6;
    background: #ffffff;
}
.warning-box {
    padding: 1rem;
    border-radius: 12px;
    border-left: 5px solid #d9534f;
    background: #fff7f7;
}
.good-box {
    padding: 1rem;
    border-radius: 12px;
    border-left: 5px solid #5cb85c;
    background: #f7fff7;
}
</style>
""", unsafe_allow_html=True)

# ---------- 工具函数 ----------
def risk_level_score(features):
    score = 0
    high_reasons = []
    critical_reasons = []

    if features.get("管制类化学品"):
        score += 5
        critical_reasons.append("涉及剧毒、易制毒、易制爆等管制类化学品")
    if features.get("高压或失控反应"):
        score += 5
        critical_reasons.append("涉及高压反应、爆炸风险或失控反应风险")
    if features.get("大量易燃易爆"):
        score += 5
        critical_reasons.append("涉及大量易燃易爆物质")

    for k, reason in [
        ("有机溶剂", "使用有机溶剂，存在挥发、易燃或吸入暴露风险"),
        ("易燃易爆", "涉及易燃、易爆物质"),
        ("有毒有害", "涉及有毒、有害物质"),
        ("强腐蚀", "涉及强酸、强碱或强腐蚀性物质"),
        ("高温", "涉及高温、加热或灼烫风险"),
        ("气瓶", "使用气瓶，存在泄漏、倾倒或压力风险"),
        ("大型仪器连续运行", "使用大型仪器或连续运行设备"),
        ("夜间实验", "夜间实验管理风险较高"),
        ("较多危险废液", "产生较多危险废液或废气"),
        ("首次独立操作", "学生首次独立开展复杂实验"),
    ]:
        if features.get(k):
            score += 2
            high_reasons.append(reason)

    if critical_reasons or score >= 8:
        level = "重大风险" if critical_reasons else "高风险"
    elif score >= 4:
        level = "高风险"
    elif score >= 2:
        level = "中风险"
    else:
        level = "低风险"

    return level, high_reasons, critical_reasons

def ppe_suggestions(features):
    items = ["穿实验服", "佩戴合适的防护手套", "实验结束后及时洗手并清理台面"]
    if features.get("有机溶剂") or features.get("有毒有害") or features.get("强腐蚀"):
        items += ["佩戴护目镜，必要时佩戴防护面屏", "优先在通风橱内操作"]
    if features.get("高温"):
        items += ["使用耐热手套，检查加热装置和温控装置"]
    if features.get("气瓶"):
        items += ["检查气瓶固定、阀门、减压阀和管路连接"]
    return list(dict.fromkeys(items))

def waste_suggestions(features):
    if features.get("较多危险废液") or features.get("有机溶剂") or features.get("强腐蚀") or features.get("有毒有害"):
        return [
            "实验废液不得直接倒入水池",
            "使用专用废液桶分类收集",
            "标签注明废液成分、危险类别、产生日期、实验室名称和责任人",
            "不相容废液不得混装",
            "废液桶不得敞口放置，不得过量盛装"
        ]
    return ["如产生少量普通废液，也应根据实验室要求分类收集，不得随意倾倒。"]

def approval_suggestions(features, level):
    need = []
    if level in ["高风险", "重大风险"]:
        need.append("建议进行实验前风险评估，并由导师或实验室负责人审核")
    if features.get("夜间实验"):
        need.append("应完成夜间实验备案，原则上不建议单人开展")
    if features.get("气瓶"):
        need.append("气瓶使用应明确责任人并做好台账")
    if features.get("大型仪器连续运行"):
        need.append("大型仪器连续运行应建立审批、运行记录和定时巡查机制")
    if features.get("管制类化学品"):
        need.append("管制类化学品应严格执行采购、领用、使用、回收和台账管理")
    if not need:
        need.append("按照实验室常规管理要求开展，实验前仍应完成基础检查")
    return need

def hazard_assessment(text):
    t = text.lower()
    rules = [
        (["矿泉水", "饮料瓶", "废液", "无标签", "标签"], "化学废弃物管理隐患", "高风险",
         "非专用容器和标签缺失可能导致废液成分不明、误用、泄漏或不相容废液混合反应。",
         "立即停止使用非专用容器，将废液转移至专用废液桶，张贴规范标签，注明成分、危险类别、产生日期、实验室名称和责任人。"),
        (["气相色谱", "过夜", "不关机", "连续运行", "大型仪器"], "仪器设备运行管理隐患", "高风险",
         "大型仪器长期运行存在电气故障、气路异常、设备过热和无人值守风险。",
         "建立连续运行审批和巡查制度，明确责任人，做好运行记录，必要时设置摄像头、远程监控或定时巡查。"),
        (["吹风机", "烘干机", "插头", "插座", "不拔", "待机"], "用电安全隐患", "中风险",
         "小型电器使用后未断电可能导致设备过热、电线老化、短路和火灾风险。",
         "使用后立即关闭电源并拔掉插头，固定存放小型电器，张贴用电安全提醒，纳入每日离室检查。"),
        (["气瓶", "未固定", "固定", "钢瓶"], "气瓶安全管理隐患", "高风险",
         "气瓶未固定可能因倾倒造成阀门损坏、气体泄漏、冲击伤害甚至火灾爆炸。",
         "立即使用链条、支架或气瓶柜固定气瓶，检查阀门、减压阀和管路，使用后关闭总阀。"),
        (["混放", "酸碱", "氧化剂", "还原剂", "有机溶剂", "药品柜"], "危险化学品储存隐患", "高风险",
         "不相容化学品混放可能引发泄漏、腐蚀、放热反应、有毒气体释放、火灾或爆炸。",
         "按照酸、碱、氧化剂、还原剂、易燃液体、毒害品等类别分柜或分区存放，建立化学品台账。"),
        (["插线板", "串联", "私拉", "乱接", "电线老化"], "用电安全隐患", "高风险",
         "插线板串联、私拉乱接或电线老化容易引发过载、短路和火灾。",
         "立即停止串联使用和私拉乱接，检查线路负荷，使用合格插座，并将用电问题纳入重点巡查。"),
        (["通风橱", "堆放", "杂物", "堵塞"], "安全设施使用隐患", "中风险",
         "通风橱堆放杂物会影响通风效果，增加有害气体暴露和事故处置难度。",
         "清理通风橱内无关物品，保持操作空间和通风效率，定期检查风速与运行状态。"),
    ]
    for keywords, category, level, analysis, action in rules:
        if any(k in t for k in keywords):
            return category, level, analysis, action
    return "一般实验室安全隐患", "中风险", "该问题可能影响实验室安全秩序和风险控制，需要结合现场情况进一步核实。", "建议拍照记录、明确责任人和整改时限，按照实验室安全制度完成整改并复查。"

def exam_questions():
    return [
        {
            "题型": "单选题",
            "题目": "进入化学实验室前，以下哪项做法是正确的？",
            "选项": "A. 未经培训也可以进入实验室参观\nB. 穿拖鞋进入实验室\nC. 完成安全教育和准入考核后进入实验室\nD. 在实验室内饮食",
            "答案": "C",
            "解析": "进入实验室前应完成安全教育和准入考核，未经准入不得独立开展实验。"
        },
        {
            "题型": "单选题",
            "题目": "实验废液应如何处理？",
            "选项": "A. 直接倒入水池\nB. 倒入矿泉水瓶中暂存\nC. 分类收集于专用废液桶并张贴标签\nD. 与生活垃圾一起处理",
            "答案": "C",
            "解析": "实验废液应分类收集，使用专用废液桶，并注明成分、危险类别、产生日期和责任人。"
        },
        {
            "题型": "单选题",
            "题目": "气瓶在实验室中应如何放置？",
            "选项": "A. 随意靠墙放置\nB. 平放在地面\nC. 使用链条、支架或气瓶柜固定\nD. 放在门口方便搬运",
            "答案": "C",
            "解析": "气瓶应固定，防止倾倒造成泄漏、撞击或爆炸风险。"
        },
        {
            "题型": "判断题",
            "题目": "实验室内可以使用矿泉水瓶临时盛装实验废液。",
            "选项": "正确 / 错误",
            "答案": "错误",
            "解析": "矿泉水瓶或饮料瓶容易造成误认，且不符合实验废液容器要求。"
        },
        {
            "题型": "判断题",
            "题目": "夜间开展高风险实验前，应进行风险评估并履行审批或备案程序。",
            "选项": "正确 / 错误",
            "答案": "正确",
            "解析": "夜间实验风险较高，应明确实验人员、实验内容、防护措施和应急联系方式。"
        },
        {
            "题型": "情景分析题",
            "题目": "某学生计划晚上单独进行有机溶剂加热回流实验，是否合适？应如何处理？",
            "选项": "",
            "答案": "不合适。",
            "解析": "该实验涉及易燃挥发、加热设备和夜间实验风险，不建议单人开展。应进行风险评估，报导师审批，完成夜间实验备案，在通风橱内操作并安排人员值守。"
        },
    ]


def ai_safety_answer(question):
    """本地规则增强版AI安全问答：不调用付费API，适合原型演示。"""
    q = question.strip().lower()
    features = {
        "有机溶剂": any(k in q for k in ["有机溶剂", "乙醇", "甲醇", "丙酮", "乙腈", "二氯甲烷", "dmf", "dmso"]),
        "易燃易爆": any(k in q for k in ["易燃", "易爆", "燃烧", "爆炸", "乙醇", "甲醇", "丙酮"]),
        "有毒有害": any(k in q for k in ["有毒", "毒害", "刺激性", "致癌", "苯", "甲醛", "氯仿"]),
        "强腐蚀": any(k in q for k in ["强酸", "强碱", "浓硫酸", "盐酸", "硝酸", "氢氧化钠", "腐蚀"]),
        "高温": any(k in q for k in ["加热", "高温", "回流", "烘箱", "马弗炉", "电热板"]),
        "气瓶": any(k in q for k in ["气瓶", "钢瓶", "氢气", "氧气", "氮气", "乙炔", "载气"]),
        "大型仪器连续运行": any(k in q for k in ["气相色谱", "液相色谱", "大型仪器", "过夜", "连续运行", "不关机"]),
        "夜间实验": any(k in q for k in ["晚上", "夜间", "通宵", "过夜"]),
        "较多危险废液": any(k in q for k in ["废液", "废气", "废弃物", "有机废液"]),
        "首次独立操作": any(k in q for k in ["第一次", "首次", "新生", "研一", "独立操作"]),
        "管制类化学品": any(k in q for k in ["管制", "易制毒", "易制爆", "剧毒"]),
        "高压或失控反应": any(k in q for k in ["高压", "反应釜", "爆聚", "失控反应"]),
        "大量易燃易爆": any(k in q for k in ["大量易燃", "大量有机溶剂", "大量易爆"]),
    }

    # 隐患整改类问题优先判断
    if any(k in q for k in ["巡检", "隐患", "整改", "矿泉水", "废液桶", "气瓶未固定", "插线板", "混放", "不拔插头"]):
        category, level, analysis, action = hazard_assessment(question)
        return {
            "类型": "隐患识别与整改",
            "风险等级": level,
            "内容": [
                ("隐患类别", category),
                ("问题分析", analysis),
                ("整改建议", action),
                ("复查要点", "完成现场整改后，应拍照留痕，明确责任人和整改时限，由安全管理员复查销号。"),
                ("教育提醒", "建议结合该隐患开展一次案例化安全教育，说明错误做法、风险后果和规范要求。")
            ]
        }

    level, reasons, critical = risk_level_score(features)

    if any(features.values()):
        content = [
            ("初步判断", f"该问题更接近“实验前风险评估”场景，初步风险等级为：{level}。"),
            ("主要危险源", "；".join((critical + reasons) or ["常规实验操作风险、用水用电安全和个人防护风险。"])),
            ("个人防护", "；".join(ppe_suggestions(features))),
            ("审批备案", "；".join(approval_suggestions(features, level))),
            ("废弃物处置", "；".join(waste_suggestions(features))),
            ("应急提醒", "实验前确认灭火器、洗眼器、喷淋装置、通风橱和紧急联系人；高风险实验不建议单人开展。")
        ]
        return {"类型": "实验前风险评估", "风险等级": level, "内容": content}

    if any(k in q for k in ["新生", "准入", "入室", "学习", "培训", "考试"]):
        return {
            "类型": "安全准入学习",
            "风险等级": "学习指导",
            "内容": [
                ("学习重点", "实验室基本行为规范、个人防护、危险化学品、废液分类、气瓶安全、用电安全、夜间实验和应急处置。"),
                ("准入要求", "完成安全教育培训和准入考核，未经准入不得独立进入实验室开展实验。"),
                ("学习建议", "先完成准入学习清单，再进入准入考试模块进行自测，对错题进行针对性复习。")
            ]
        }

    return {
        "类型": "综合安全问答",
        "风险等级": "需补充信息",
        "内容": [
            ("回答", "请补充实验名称、使用化学品、设备条件、是否夜间实验、是否产生废液等信息，我可以进一步生成风险等级和防护建议。"),
            ("提示", "涉及危险化学品、气瓶、高温高压、夜间实验或大型仪器连续运行时，应进行导师审核、风险评估和必要备案。")
        ]
    }


def build_risk_report_text(exp_name, chemicals, level, source_items, ppe_items, waste_items, approval_items):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "LabSafeEdu实验前风险评估报告",
        f"生成时间：{now}",
        "",
        f"实验名称：{exp_name}",
        f"使用化学品/材料：{chemicals}",
        f"初步风险等级：{level}",
        "",
        "一、主要危险源：",
    ]
    lines += [f"{i+1}. {x}" for i, x in enumerate(source_items)]
    lines += ["", "二、个人防护要求："]
    lines += [f"{i+1}. {x}" for i, x in enumerate(ppe_items)]
    lines += ["", "三、废弃物处置建议："]
    lines += [f"{i+1}. {x}" for i, x in enumerate(waste_items)]
    lines += ["", "四、审批备案与管理要求："]
    lines += [f"{i+1}. {x}" for i, x in enumerate(approval_items)]
    lines += ["", "五、说明：本报告为实验前安全辅助评估，不替代学校正式审批流程、导师判断和现场安全管理制度。"]
    return "\\n".join(lines)

# ---------- 侧边栏 ----------
st.sidebar.title("🧪 LabSafeEdu")
page = st.sidebar.radio(
    "选择功能模块",
    [
        "首页",
        "AI安全问答助手",
        "安全准入学习",
        "实验前风险评估",
        "隐患识别与整改",
        "准入考试与错题反馈",
        "安全数据分析看板",
        "参赛材料导出"
    ]
)

st.sidebar.markdown("---")
st.sidebar.caption("高校化学与材料类实验室安全教育与风险闭环智能体原型系统")

# ---------- 首页 ----------
if page == "首页":
    st.markdown('<div class="main-title">LabSafeEdu实验室安全智能体</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">面向高校化学与材料类实验室的安全准入、风险评估、隐患整改与数据治理原型系统</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("检查实验室", "133间")
    c2.metric("累计隐患", "832项")
    c3.metric("化学安全隐患", "384项")
    c4.metric("整改率", "89%→100%")

    st.markdown("### 系统定位")
    st.markdown("""
    LabSafeEdu是一款面向高校化学与材料类实验室的安全教育与风险闭环管理智能体。
    系统围绕学生准入、实验前风险评估、隐患识别整改、准入考试评价和安全管理数据分析等场景，
    提供知识问答、风险研判、整改建议、个性化学习和管理辅助服务。
    """)

    st.markdown("### 六个核心模块")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("**AI安全问答助手**\n\n支持自然语言提问，自动识别准入、评估和整改场景。")
        st.info("**安全准入学习**\n\n生成入室前安全学习清单，帮助学生掌握基本规范。")
        st.info("**实验前风险评估**\n\n识别危险源、判断风险等级，提醒审批备案。")
    with col2:
        st.info("**隐患识别与整改**\n\n判断隐患类别、风险等级，生成整改和复查建议。")
        st.info("**准入考试与反馈**\n\n生成题目、答案解析和薄弱点复习建议。")
    with col3:
        st.info("**安全数据分析看板**\n\n基于隐患数据形成风险画像和管理建议。")

    st.markdown("### 闭环逻辑")
    st.success("AI问答引导 → 学生入室学习 → 实验前风险评估 → 实验过程风险提醒 → 隐患发现与整改 → 考试评价与数据分析 → 反向优化安全教育内容")


# ---------- AI安全问答助手 ----------
elif page == "AI安全问答助手":
    st.header("AI安全问答助手")
    st.write("这是本地规则增强版AI问答模块，不调用付费API。用户可直接用自然语言描述实验任务或巡检隐患，系统会自动识别场景并生成建议。")

    examples = [
        "我今晚要做有机溶剂加热回流实验，需要注意什么？",
        "巡检发现有学生用矿泉水桶装实验废液，桶身没有标签。",
        "我是研一新生，第一次进入化学实验室，需要学习哪些内容？",
        "气相色谱仪需要过夜运行，应该怎么管理？",
        "实验室气瓶没有固定，风险大吗？"
    ]
    selected = st.selectbox("选择一个示例问题，也可以在下方自行修改", examples)
    question = st.text_area("请输入你的问题", selected, height=120)

    if st.button("生成AI安全建议"):
        answer = ai_safety_answer(question)
        st.subheader("智能体判断结果")
        c1, c2 = st.columns(2)
        c1.metric("识别场景", answer["类型"])
        c2.metric("风险/状态", answer["风险等级"])

        rows = pd.DataFrame(answer["内容"], columns=["项目", "建议内容"])
        st.dataframe(rows, use_container_width=True)

        st.markdown("#### 可复制安全建议")
        text = "【LabSafeEdu智能安全建议】\\n"
        text += f"用户问题：{question}\\n"
        text += f"识别场景：{answer['类型']}\\n"
        text += f"风险/状态：{answer['风险等级']}\\n"
        for k, v in answer["内容"]:
            text += f"{k}：{v}\\n"
        text += "说明：本建议用于安全教育和管理辅助，不替代学校正式审批、导师判断和现场安全制度。"
        st.code(text, language="text")
        st.download_button("下载本次AI安全建议TXT", text, file_name="LabSafeEdu_AI安全建议.txt")

# ---------- 安全准入学习 ----------
elif page == "安全准入学习":
    st.header("安全准入学习模块")
    identity = st.selectbox("请选择你的身份", ["本科生", "研究生", "新进教师", "实验技术人员", "短期进入实验室人员"])
    lab_type = st.selectbox("请选择实验室类型", ["化学类实验室", "材料类实验室", "机电类实验室", "生物类实验室", "其他实验室"])
    focus = st.multiselect(
        "你希望重点学习哪些内容？",
        ["基本行为规范", "个人防护", "危险化学品", "实验废液", "气瓶安全", "用电安全", "高温设备", "夜间实验", "应急处置"],
        default=["基本行为规范", "个人防护", "危险化学品", "实验废液", "用电安全", "应急处置"]
    )
    if st.button("生成入室前安全学习清单"):
        st.subheader("入室前安全学习清单")
        st.markdown(f"适用对象：**{identity}**；实验室类型：**{lab_type}**。")
        checklist = [
            ["学习项目", "具体要求"],
            ["准入要求", "完成实验室安全教育培训和准入考核，未经准入不得独立开展实验。"],
            ["基本行为规范", "不得在实验室饮食、吸烟、嬉戏打闹；实验结束后关闭水、电、气、门窗和仪器设备。"],
            ["个人防护", "进入实验室穿实验服；涉及化学品时佩戴防护手套、护目镜，长发应束起。"],
            ["危险化学品", "使用前了解危险特性、防护要求和泄漏处置方法；不得使用无标签容器存放。"],
            ["实验废液", "分类收集于专用废液桶，不得倒入水池，不得使用矿泉水瓶或饮料瓶盛装。"],
            ["气瓶安全", "气瓶必须固定，使用前检查阀门、减压阀和管路，使用后关闭总阀。"],
            ["用电安全", "不得私拉乱接电线，不得插线板串联，小型电器使用后断电并拔掉插头。"],
            ["夜间实验", "涉及高风险因素时应完成导师审批和夜间实验备案，不建议单人开展。"],
            ["应急处置", "熟悉灭火器、洗眼器、喷淋装置、急救箱位置和使用方法。"],
        ]
        df = pd.DataFrame(checklist[1:], columns=checklist[0])
        st.dataframe(df, use_container_width=True)
        st.markdown("### 个性化学习建议")
        st.write("建议优先学习：" + "、".join(focus) + "。学习后可进入“准入考试与错题反馈”模块进行自测。")

# ---------- 风险评估 ----------
elif page == "实验前风险评估":
    st.header("实验前风险评估模块")
    st.write("请根据计划开展的实验填写信息，系统将生成风险等级、危险源、防护要求、审批备案提醒和检查清单。")

    exp_name = st.text_input("实验名称", "有机溶剂加热回流与气相色谱检测实验")
    chemicals = st.text_area("使用的化学品或材料", "有机溶剂、待测样品、标准品")
    col1, col2, col3 = st.columns(3)
    features = {}
    with col1:
        features["有机溶剂"] = st.checkbox("使用有机溶剂", True)
        features["易燃易爆"] = st.checkbox("涉及易燃易爆物质", True)
        features["有毒有害"] = st.checkbox("涉及有毒有害物质")
        features["强腐蚀"] = st.checkbox("涉及强酸强碱/强腐蚀")
    with col2:
        features["高温"] = st.checkbox("涉及加热/高温", True)
        features["气瓶"] = st.checkbox("使用气瓶")
        features["大型仪器连续运行"] = st.checkbox("大型仪器或连续运行设备", True)
        features["夜间实验"] = st.checkbox("夜间实验", True)
    with col3:
        features["较多危险废液"] = st.checkbox("产生较多危险废液/废气", True)
        features["首次独立操作"] = st.checkbox("学生首次独立操作")
        features["管制类化学品"] = st.checkbox("涉及管制类化学品")
        features["高压或失控反应"] = st.checkbox("涉及高压或失控反应")
        features["大量易燃易爆"] = st.checkbox("大量易燃易爆物质")

    if st.button("生成风险评估报告"):
        level, reasons, critical = risk_level_score(features)
        st.subheader("实验前风险评估结果")
        if level in ["高风险", "重大风险"]:
            st.markdown(f'<div class="warning-box"><b>风险等级：{level}</b><br>该实验涉及较高风险因素，应完成风险评估、导师审核或备案，不建议单人开展。</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="good-box"><b>风险等级：{level}</b><br>按实验室常规要求开展，仍需完成基础安全检查。</div>', unsafe_allow_html=True)

        st.markdown("#### 一、主要危险源")
        source_items = critical + reasons
        if not source_items:
            source_items = ["常规实验操作风险，如玻璃器皿破损、轻微暴露、用水用电安全等。"]
        for i, item in enumerate(source_items, 1):
            st.write(f"{i}. {item}")

        st.markdown("#### 二、个人防护要求")
        for item in ppe_suggestions(features):
            st.write(f"- {item}")

        st.markdown("#### 三、废弃物处置建议")
        for item in waste_suggestions(features):
            st.write(f"- {item}")

        st.markdown("#### 四、审批备案与管理要求")
        for item in approval_suggestions(features, level):
            st.write(f"- {item}")

        st.markdown("#### 五、实验前检查清单")
        check_items = [
            "确认实验方案、SDS和应急处置方法已经学习",
            "确认通风橱、灭火器、洗眼器和喷淋装置可用",
            "检查水、电、气、冷凝水和仪器运行状态",
            "确认废液桶、标签和收集方式符合要求",
            "明确现场人员、导师或紧急联系人",
            "实验结束后清理台面，关闭水、电、气、门窗和设备"
        ]
        st.dataframe(pd.DataFrame({"检查项目": check_items, "是否完成": ["□"] * len(check_items)}), use_container_width=True)

        report_text = build_risk_report_text(
            exp_name,
            chemicals,
            level,
            source_items,
            ppe_suggestions(features),
            waste_suggestions(features),
            approval_suggestions(features, level)
        )
        st.markdown("#### 六、一键导出")
        st.download_button("下载实验前风险评估报告TXT", report_text, file_name="LabSafeEdu实验前风险评估报告.txt")

# ---------- 隐患整改 ----------
elif page == "隐患识别与整改":
    st.header("隐患识别与整改模块")
    text = st.text_area("请输入巡检发现的隐患描述", "巡检发现有学生用矿泉水桶装实验废液，桶身没有标签。", height=120)

    if st.button("生成隐患整改建议"):
        category, level, analysis, action = hazard_assessment(text)
        st.subheader("隐患判断结果")
        result_df = pd.DataFrame([
            ["隐患类别", category],
            ["风险等级", level],
            ["问题分析", analysis],
            ["整改措施", action],
            ["整改时限建议", "高风险隐患建议立即整改；中风险隐患建议限期整改并复查。"],
            ["教育提醒", "对相关人员开展针对性安全教育，说明风险后果和正确做法。"],
        ], columns=["项目", "内容"])
        st.dataframe(result_df, use_container_width=True)

        st.markdown("#### 复查要点")
        if "废液" in text or "矿泉水" in text:
            checks = ["是否更换为专用废液桶", "是否张贴规范废液标签", "是否注明成分、危险类别和责任人", "是否仍存在生活容器盛装废液"]
        elif "气瓶" in text:
            checks = ["气瓶是否固定", "标识是否清晰", "减压阀和管路是否完好", "使用后是否关闭总阀", "是否建立台账"]
        elif "吹风机" in text or "插头" in text or "烘干机" in text:
            checks = ["设备是否断电", "插头是否拔出", "周围是否有可燃物", "是否纳入离室检查"]
        else:
            checks = ["是否完成现场整改", "是否明确责任人和整改时限", "是否形成整改记录", "是否完成复查销号"]
        st.dataframe(pd.DataFrame({"复查项目": checks, "复查结果": ["□ 合格 / □ 不合格"] * len(checks)}), use_container_width=True)

        st.markdown("#### 可复制整改通知")
        notice = f"""【实验室安全隐患整改提醒】
隐患描述：{text}
隐患类别：{category}
风险等级：{level}
整改要求：{action}
复查要求：请在规定时限内完成整改，并提交整改照片或说明，由安全管理员复查确认。
"""
        st.code(notice, language="text")

# ---------- 考试 ----------
elif page == "准入考试与错题反馈":
    st.header("准入考试与错题反馈模块")
    st.write("系统可生成实验室安全准入题目，并提供答案解析。当前为原型题库，可后续扩展为随机抽题。")

    questions = exam_questions()
    for idx, q in enumerate(questions, 1):
        with st.expander(f"{idx}. 【{q['题型']}】{q['题目']}"):
            if q["选项"]:
                st.text(q["选项"])
            st.markdown(f"**正确答案：** {q['答案']}")
            st.markdown(f"**解析：** {q['解析']}")

    st.markdown("### 薄弱点反馈示例")
    weak = st.multiselect("请选择本次答错或不熟悉的知识点", ["废液管理", "气瓶安全", "用电安全", "危险化学品储存", "夜间实验", "个人防护"])
    if st.button("生成复习建议"):
        if not weak:
            st.success("本次未选择薄弱点，建议继续完成情景题训练。")
        else:
            st.write("建议重点复习：")
            for item in weak:
                st.write(f"- **{item}**：结合真实案例学习风险后果、规范要求和整改要点。")

# ---------- 数据看板 ----------
elif page == "安全数据分析看板":
    st.header("安全数据分析与管理建议模块")

    hazard_df = pd.read_excel(DATA_DIR / "LabSafeEdu实验室安全数据分析表.xlsx", sheet_name="隐患分类统计")
    risk_df = pd.read_excel(DATA_DIR / "LabSafeEdu实验室安全数据分析表.xlsx", sheet_name="风险等级分布")
    lab_type_df = pd.read_excel(DATA_DIR / "LabSafeEdu实验室安全数据分析表.xlsx", sheet_name="实验室类型分布")
    effect_df = pd.read_excel(DATA_DIR / "LabSafeEdu实验室安全数据分析表.xlsx", sheet_name="管理成效数据")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("检查实验室", "133间")
    c2.metric("累计隐患", "832项")
    c3.metric("化学安全占比", "46.2%")
    c4.metric("基础安全占比", "24.8%")

    st.markdown("### 隐患分类统计")
    st.dataframe(hazard_df, use_container_width=True)
    fig1, ax1 = plt.subplots()
    plot_df = hazard_df[hazard_df["隐患类别"] != "合计"]
    ax1.bar(plot_df["隐患类别"], plot_df["数量"])
    ax1.set_ylabel("数量")
    ax1.set_title("隐患类别数量分布")
    plt.xticks(rotation=30, ha="right")
    st.pyplot(fig1)

    st.markdown("### 风险等级分布")
    col_a, col_b = st.columns([1, 1])
    with col_a:
        st.dataframe(risk_df, use_container_width=True)
    with col_b:
        fig2, ax2 = plt.subplots()
        risk_plot = risk_df[risk_df["风险等级"] != "合计"]
        ax2.pie(risk_plot["实验室数量"], labels=risk_plot["风险等级"], autopct="%1.1f%%")
        ax2.set_title("实验室风险等级占比")
        st.pyplot(fig2)

    st.markdown("### 管理建议")
    st.info("""
    1. 化学安全隐患数量最多，应将危险化学品储存、管制类化学品、实验废液和气瓶管理作为下一阶段重点。
    2. 基础安全隐患占比较高，应持续加强用电安全、小型电器断电、个人防护和离室检查。
    3. 重大风险和高风险实验室合计54间，应实施分级分类监管，强化导师审核、高风险实验审批和夜间实验备案。
    4. 通过准入考试、专项培训、周检查、节前检查和隐患闭环整改，推动安全管理从经验型向数据驱动型转变。
    """)

# ---------- 参赛材料导出 ----------
elif page == "参赛材料导出":
    st.header("参赛材料导出")
    st.write("本页提供参赛报告可直接使用的简介、关键词和创新点。")

    intro = """本案例面向高校化学与材料类实验室安全教育与管理场景，构建LabSafeEdu实验室安全智能体。智能体围绕学生准入、实验前风险评估、隐患识别、整改闭环和安全文化培育等环节，融合实验室安全制度、隐患案例、风险分级规则和检查数据，提供知识问答、风险研判、整改建议、准入考试和数据分析等功能。该智能体能够提升实验室安全教育的互动性、精准性和持续性，推动安全管理由经验型、事后型向数据驱动、过程预防和闭环治理转变。"""
    st.markdown("### 简介")
    st.text_area("可复制简介", intro, height=160)

    st.markdown("### 关键词")
    st.code("实验室安全；AI智能体；风险评估；隐患整改；安全教育", language="text")

    st.markdown("### 创新点")
    innovation = pd.DataFrame([
        ["场景化安全教育", "将传统文件学习和统一培训转化为面向真实实验任务的交互式学习。"],
        ["实验前风险预判", "学生在实验前输入实验内容，系统自动识别危险源并提示审批备案。"],
        ["隐患整改闭环", "对巡检隐患进行分类、风险判断、整改建议和复查要点生成。"],
        ["真实数据驱动", "基于133间实验室、832项隐患和整改率变化形成风险画像。"],
        ["育人与管理融合", "把准入学习、考试反馈、隐患案例和管理分析连接为闭环。"],
    ], columns=["创新点", "说明"])
    st.dataframe(innovation, use_container_width=True)

    report = f"""LabSafeEdu实验室安全智能体演示摘要
生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}

作品名称：LabSafeEdu：高校化学与材料类实验室安全教育与风险闭环智能体

简介：
{intro}

关键词：
实验室安全；AI智能体；风险评估；隐患整改；安全教育

核心模块：
1. 安全准入学习
2. 实验前风险评估
3. 隐患识别与整改
4. 准入考试与错题反馈
5. 安全数据分析看板
"""
    st.download_button("下载演示摘要TXT", report, file_name="LabSafeEdu演示摘要.txt")