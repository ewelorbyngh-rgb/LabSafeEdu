
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime
import platform, re, random

st.set_page_config(page_title="LabSafeEdu实验室安全智能体", page_icon="🧪", layout="wide")

plt.rcParams["axes.unicode_minus"] = False
if platform.system() == "Windows":
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
elif platform.system() == "Darwin":
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "PingFang SC", "Heiti SC", "DejaVu Sans"]
else:
    plt.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "WenQuanYi Micro Hei", "DejaVu Sans"]

DATA_DIR = Path(__file__).parent / "data"

@st.cache_data
def load_data():
    return {
        "knowledge": pd.read_csv(DATA_DIR / "knowledge_base.csv"),
        "hazards": pd.read_csv(DATA_DIR / "hazard_rectification_library.csv"),
        "risk_rules": pd.read_csv(DATA_DIR / "risk_assessment_rules.csv"),
        "qa": pd.read_csv(DATA_DIR / "qa_pairs.csv"),
        "exam": pd.read_csv(DATA_DIR / "exam_bank.csv"),
        "cases": pd.read_csv(DATA_DIR / "scenario_cases.csv"),
        "refs": pd.read_csv(DATA_DIR / "references.csv"),
        "hazard_stats": pd.read_csv(DATA_DIR / "hazard_statistics.csv"),
        "risk_stats": pd.read_csv(DATA_DIR / "risk_distribution.csv"),
        "lab_type": pd.read_csv(DATA_DIR / "lab_type_distribution.csv"),
    }

data = load_data()

DATASET_CONFIG = {
    "制度知识库": {
        "key": "knowledge",
        "file": "knowledge_base.csv",
        "required": ["一级类别", "二级类别", "标题", "内容", "关键词"],
        "template": ["一级类别", "二级类别", "标题", "内容", "关键词", "更新日期", "状态"],
    },
    "隐患整改库": {
        "key": "hazards",
        "file": "hazard_rectification_library.csv",
        "required": ["隐患描述", "隐患类别", "风险等级", "问题分析", "整改建议", "复查要点", "关键词"],
        "template": ["隐患描述", "隐患类别", "风险等级", "问题分析", "整改建议", "复查要点", "关键词"],
    },
    "风险规则库": {
        "key": "risk_rules",
        "file": "risk_assessment_rules.csv",
        "required": ["风险因素", "分值", "建议风险级别", "控制措施", "关键词"],
        "template": ["风险因素", "分值", "建议风险级别", "控制措施", "关键词"],
    },
    "问答库": {
        "key": "qa",
        "file": "qa_pairs.csv",
        "required": ["问题", "答案", "类别", "关键词"],
        "template": ["问题", "答案", "类别", "关键词"],
    },
    "案例微课堂": {
        "key": "cases",
        "file": "scenario_cases.csv",
        "required": ["案例编号", "案例名称", "适用场景", "风险等级", "案例描述", "风险分析", "正确做法", "追问问题", "教学目标"],
        "template": ["案例编号", "案例名称", "适用场景", "风险等级", "案例描述", "风险分析", "正确做法", "追问问题", "教学目标"],
    },
}

def dataset_to_csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8-sig")

def empty_template_bytes(cols):
    return pd.DataFrame(columns=cols).to_csv(index=False).encode("utf-8-sig")

def read_uploaded_table(uploaded_file):
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(uploaded_file)
    raise ValueError("仅支持 CSV 或 Excel 文件。")

def validate_dataset(df, required_cols):
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        return False, "缺少必需列：" + "、".join(missing)
    if len(df) == 0:
        return False, "上传表为空。"
    return True, "格式检查通过。"

def save_dataset_to_local(dataset_label, df):
    cfg = DATASET_CONFIG[dataset_label]
    path = DATA_DIR / cfg["file"]
    df.to_csv(path, index=False, encoding="utf-8-sig")
    st.cache_data.clear()

def safe_table_for_display(df, cols):
    show_cols = [c for c in cols if c in df.columns]
    return df[show_cols] if show_cols else df



def normalize_text(x):
    return str(x).lower().replace("，"," ").replace("。"," ").replace("、"," ").replace("；"," ")

def tokens(text):
    q = normalize_text(text)
    base = set(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", q))
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]+", q))
    for n in [2,3,4]:
        for i in range(max(0, len(chinese)-n+1)):
            base.add(chinese[i:i+n])
    alias = {
        "不关门":["门未关","门没关","门禁敞开","未锁门","门开着","忘记关门"],
        "矿泉水桶":["矿泉水瓶","饮料瓶","生活容器","非专用容器"],
        "气瓶没固定":["气瓶未固定","钢瓶未固定","气瓶靠墙"],
        "过夜不关机":["过夜运行","连续运行","无人值守","长期不关机"],
        "不舒服":["头晕","恶心","胸闷","不适"],
        "刺鼻":["异味","吸入","泄漏","挥发"],
    }
    for k, vals in alias.items():
        if k in q or any(v in q for v in vals):
            base.add(k)
            base.update(vals)
    return {t for t in base if len(t) >= 2}

def score_text(query, row, fields):
    qs = tokens(query)
    score = 0
    for f in fields:
        val = normalize_text(row.get(f, ""))
        weight = 3 if f in ["标题","隐患描述","问题"] else 1
        for t in qs:
            if t in val:
                score += weight
    return score

def search_df(df, query, fields, topn=8):
    rows = []
    for _, row in df.iterrows():
        s = score_text(query, row, fields)
        if s > 0:
            d = row.to_dict()
            d["_相关度"] = s
            rows.append(d)
    if not rows:
        return df.head(0).copy()
    return pd.DataFrame(rows).sort_values("_相关度", ascending=False).head(topn)

def emergency_response(query):
    q = normalize_text(query)
    emergency_keywords = ["头晕","头痛","恶心","呕吐","胸闷","咳嗽","呼吸困难","眼睛刺痛","流泪","喉咙痛","皮肤刺痛","晕倒","中毒","不舒服","不适","刺鼻","异味","吸入","闻到","泄漏","暴露","溅到","进眼","灼伤","烫伤","割伤","流血","烧伤","腐蚀","酸溅","碱溅","化学品弄到"]
    if not any(k in q for k in emergency_keywords):
        return None
    if any(k in q for k in ["进眼","眼睛","流泪","眼睛刺痛","酸溅","碱溅"]):
        subtype, level = "眼部暴露/刺激", "紧急处置"
        first_action = "立即停止实验，尽快使用洗眼器或大量流动清水持续冲洗眼部，并报告导师或安全管理员；必要时立即就医。"
        checks = "确认接触物质名称和SDS；记录暴露时间；检查洗眼器是否可用；安排人员陪同就医。"
    elif any(k in q for k in ["头晕","头痛","恶心","胸闷","咳嗽","呼吸困难","刺鼻","异味","吸入","闻到","中毒","不舒服","不适"]):
        subtype, level = "疑似吸入暴露/通风异常", "需立即停止实验并报告"
        first_action = "立即停止当前实验，离开可能暴露区域，到空气流通处休息；不要独自继续实验。立即告知同伴、导师或实验室安全管理员。若症状明显、持续或加重，应及时就医或拨打急救电话。"
        checks = "排查是否存在挥发性溶剂、有毒有害气体、气瓶泄漏、通风橱异常或加热挥发；在确保安全前提下关闭相关设备和试剂容器，开启通风并疏散无关人员。"
    elif any(k in q for k in ["皮肤","灼伤","腐蚀","化学品弄到","溅到"]):
        subtype, level = "皮肤接触/化学灼伤", "紧急处置"
        first_action = "立即脱除被污染的手套或衣物，用大量流动清水冲洗接触部位，并报告导师或安全管理员；腐蚀性、有毒有害物质接触后应尽快就医。"
        checks = "确认接触化学品名称和浓度；查阅SDS；记录暴露时间和处理过程；检查喷淋或冲洗设施可用性。"
    elif any(k in q for k in ["割伤","流血","划伤","针刺"]):
        subtype, level = "机械伤害/锐器伤", "现场急救与报告"
        first_action = "立即停止操作，进行止血和伤口处理；涉及污染针头、玻璃或化学品污染伤口时，应报告并尽快就医。"
        checks = "保留事故物品信息；确认是否有化学品或生物材料污染；完善事故记录并开展复盘。"
    else:
        subtype, level = "实验过程人员不适", "需暂停实验并复核风险"
        first_action = "立即暂停实验，离开风险区域，告知同伴、导师或安全管理员，不要单独继续操作。若症状持续或加重，应及时就医。"
        checks = "复核实验化学品、通风、温度、气体、个人防护和操作过程，确认是否存在暴露或设备异常。"
    return "应急处置与人员不适", level, [
        ("识别场景", subtype),
        ("第一步处置", first_action),
        ("现场安全控制", "在确保自身安全的前提下，关闭可能的危险源，保持通风，疏散无关人员；不要盲目处理未知泄漏或未知暴露源。"),
        ("需要报告", "立即报告导师、实验室负责人或安全管理员；如症状明显、持续或加重，应联系校医院、急救人员或拨打当地急救电话。"),
        ("复查要点", checks),
        ("后续闭环", "记录发生时间、实验内容、可能暴露物质、现场处置和人员状态；完成事故/异常情况复盘，必要时暂停同类实验并开展专项检查。")
    ]

def detect_risk(query):
    q = normalize_text(query)
    score = 0
    factors = []
    for _, r in data["risk_rules"].iterrows():
        kws = [x.strip().lower() for x in str(r["关键词"]).split() if x.strip()]
        if any(k in q for k in kws):
            score += int(r["分值"])
            factors.append((r["风险因素"], int(r["分值"]), r["控制措施"]))
    if score >= 8 or any(x[1] >= 5 for x in factors):
        level = "重大风险" if any(x[1] >= 5 for x in factors) else "高风险"
    elif score >= 4:
        level = "高风险"
    elif score >= 2:
        level = "中风险"
    else:
        level = "低风险"
    return level, score, factors

def search_hazard(query):
    q = normalize_text(query)
    priority_rules = [
        (["不关门","门没关","门未关","门开着","未锁门","忘记关门","门禁敞开"], "实验室门未关闭或门禁长期敞开"),
        (["矿泉水桶","矿泉水瓶","饮料瓶","生活容器","非专用容器"], "使用矿泉水桶或饮料瓶装废液"),
        (["气瓶未固定","气瓶没固定","钢瓶未固定","气瓶靠墙"], "气瓶未固定"),
        (["插线板串联","插排串联","排插串联"], "插线板串联使用"),
        (["过夜不关机","过夜运行","无人值守","长期不关机"], "气相色谱仪长期过夜无人值守"),
        (["废液无标签","废液没标签"], "废液桶无标签或标签信息不完整"),
        (["地面积水","漏水","水池旁边"], "实验室地面积水未及时处理"),
    ]
    for keys, target in priority_rules:
        if any(k in q for k in keys):
            hit = data["hazards"][data["hazards"]["隐患描述"] == target]
            if len(hit) > 0:
                return hit.iloc[0]
    best, best_score = None, 0
    for _, row in data["hazards"].iterrows():
        s = score_text(query, row, ["隐患描述","隐患类别","问题分析","整改建议","复查要点","关键词"])
        if s > best_score:
            best_score, best = s, row
    return best if best_score > 0 else None

def fallback_hazard(query):
    q = normalize_text(query)
    rules = [
        (["门","门禁","不关门","未锁","敞开","外来人员"], "场所与门禁管理", "中风险", "可能导致无关人员进入、危险化学品和仪器设备失管、资产安全风险增加，也不利于事故责任追溯。", "立即恢复门禁或关闭实验室门，明确最后离室人员责任，外来人员进入应登记并进行安全告知，将关门纳入离室检查清单。", "门禁是否正常；离室记录是否完整；是否明确最后离室责任人；是否存在无关人员随意进入。"),
        (["水","漏水","水龙头","下水","积水","水池"], "用水与场所环境隐患", "中风险", "可能造成设备受潮、地面滑倒、漏水扩散或影响电气安全。", "立即关闭水源并清理积水，排查水龙头、管路和下水是否异常，必要时联系维修人员处理。", "水源是否关闭；地面积水是否清理；管路是否修复；是否纳入离室检查。"),
        (["电","插座","插排","插线板","电线","电源","短路","充电"], "用电安全隐患", "高风险", "可能造成过载、短路、触电或火灾风险。", "立即停止不规范用电，检查插座、电线、插排和设备负荷，禁止私拉乱接和插线板串联，必要时联系专业电工整改。", "线路是否规范；插排是否串联；设备是否断电；周边是否有可燃物。"),
        (["试剂","药品","化学品","酸","碱","溶剂","瓶","标签"], "危险化学品管理隐患", "高风险", "可能存在化学品成分不明、相容性不清、误用、泄漏、腐蚀、火灾或中毒风险。", "立即核实化学品名称和危险性，补充标签，按性质分类存放，不相容化学品分开，完善台账。", "标签是否完整；分类是否正确；台账是否一致；是否存在过期或来源不明试剂。"),
        (["废液","废弃物","垃圾","玻璃","针头","锐器"], "实验废弃物管理隐患", "高风险", "可能造成成分不明、混装反应、泄漏、割伤、污染或后续处置风险。", "按类别使用专用容器收集并张贴标签，危险废物不得与生活垃圾混放，不相容废液不得混装。", "容器是否专用；标签是否完整；是否分类收集；是否建立转运或暂存记录。"),
        (["气瓶","钢瓶","氢气","氧气","氮气","乙炔","减压阀"], "气瓶安全管理隐患", "高风险", "可能存在气瓶倾倒、阀门损坏、气体泄漏、窒息、中毒或燃爆风险。", "立即固定气瓶，检查阀门、减压阀、压力表和管路连接，使用后关闭总阀，并完善气瓶台账。", "气瓶是否固定；阀门和管路是否完好；使用后总阀是否关闭；台账是否完整。"),
        (["通风橱","通风","异味","挥发","气味"], "通风与暴露控制隐患", "中风险", "可能导致有毒有害、刺激性或挥发性物质暴露，影响人员健康。", "检查通风橱或排风系统运行状态，清理无关物品，涉及挥发性或有毒有害物质的操作应在通风橱内进行。", "通风是否正常；通风橱内是否堆放杂物；操作口高度是否合适。"),
        (["灭火器","消防","通道","安全出口","堵塞","喷淋","洗眼"], "消防与应急设施隐患", "高风险", "可能影响火灾初期处置、人员疏散或化学暴露后的紧急冲洗。", "立即清理遮挡物，保持消防通道、安全出口、灭火器、洗眼器和喷淋装置可达可用，并检查有效期和运行状态。", "设施是否可达；是否过期；通道是否畅通；检查记录是否完整。"),
        (["手套","护目镜","实验服","拖鞋","短裤","防护","口罩"], "个人防护隐患", "中风险", "可能导致化学品飞溅、割伤、烫伤、吸入暴露或交叉污染。", "按实验风险佩戴实验服、合适手套、护目镜或面屏，不得穿拖鞋短裤进入实验室，污染手套不得触摸公共物品。", "PPE是否佩戴；着装是否合规；污染手套是否规范脱除；是否开展教育提醒。"),
        (["加热","烘箱","电热板","回流","高温","过夜","无人"], "加热与连续运行隐患", "高风险", "可能存在设备过热、冷凝水中断、可燃物引燃、无人值守和火灾风险。", "停止无人值守的高风险加热或连续运行，检查设备状态、周边可燃物、冷凝水和巡查记录，必要时完成审批备案。", "是否有人值守；设备是否正常；可燃物是否清理；是否有运行和巡查记录。"),
    ]
    for keys, cat, level, analysis, action, check in rules:
        if any(k in q for k in keys):
            return {"隐患描述":"未收录隐患的智能兜底判断","隐患类别":cat,"风险等级":level,"问题分析":analysis,"整改建议":action,"复查要点":check,"关键词":"兜底规则"}
    return {"隐患描述":"未收录隐患的通用安全判断","隐患类别":"一般实验室安全隐患","风险等级":"中风险","问题分析":"该描述未命中具体隐患条目，但现场异常行为可能影响实验室安全秩序、风险控制或责任追溯。","整改建议":"建议先停止相关不规范行为，拍照记录，明确责任人和整改时限；由安全管理员结合现场情况进行复核，并将问题纳入隐患整改闭环。","复查要点":"是否完成现场整改；是否明确责任人；是否形成整改记录；是否复查销号；是否开展针对性安全教育。","关键词":"通用兜底"}

def answer_ai(query):
    emergency = emergency_response(query)
    if emergency is not None:
        return emergency
    if any(k in normalize_text(query) for k in ["隐患","巡检","整改","发现","存在","有人","不关门","门禁","废液","气瓶","插线板","混放","无标签","过夜","地面积水"]):
        h = search_hazard(query)
        source = "隐患库匹配"
        if h is None:
            h = fallback_hazard(query)
            source = "智能兜底判断"
        return "隐患识别与整改", h["风险等级"], [("识别来源", source),("隐患类别",h["隐患类别"]),("问题分析",h["问题分析"]),("整改建议",h["整改建议"]),("复查要点",h["复查要点"]),("教育提醒","建议将该隐患纳入案例化安全教育，形成“发现—整改—复查—反馈”的闭环。")]
    level, score, factors = detect_risk(query)
    if factors:
        return "实验前风险评估", level, [("命中风险因素","；".join([f"{x[0]}（{x[1]}分）" for x in factors])),("主要控制措施","；".join([x[2] for x in factors[:6]])),("审批备案建议","高风险及以上实验应进行实验前风险评估，由导师或实验室负责人审核；涉及夜间实验应完成备案。"),("个人防护建议","穿实验服，佩戴合适手套；涉及飞溅、腐蚀、挥发或有毒有害物质时佩戴护目镜或面屏，并优先在通风橱内操作。"),("废弃物建议","实验废液应使用专用废液桶分类收集，标签注明成分、危险类别、日期和责任人。")]
    res = search_df(data["qa"], query, ["问题","答案","关键词","类别"], topn=1)
    if len(res)>0:
        r = res.iloc[0]
        return "知识问答","学习指导",[("答案",r["答案"]),("关联类别",r["类别"])]
    res2 = search_df(data["knowledge"], query, ["标题","内容","关键词","一级类别","二级类别"], topn=1)
    if len(res2)>0:
        r = res2.iloc[0]
        return "知识库检索","学习指导",[("知识条目",r["标题"]),("内容",r["内容"]),("类别",f"{r['一级类别']} / {r['二级类别']}")]
    return "综合问答","需补充信息",[("提示","请补充实验名称、化学品、设备条件、是否夜间、是否产生废液或巡检隐患描述，我可以生成更准确的风险评估或整改建议。")]

def access_learning_plan(identity, lab, focus):
    rows = []
    base = ["准入与责任体系","个人防护","消防与应急处置"]
    cats = list(dict.fromkeys(base + focus))
    if "化学" in lab or "材料" in lab:
        cats += ["危险化学品","实验废弃物","气瓶与压力设备","用电与仪器设备"]
    if "生物" in lab:
        cats += ["生物与机械安全","消防与应急处置"]
    if identity in ["本科生","研究生"]:
        note = "重点强化准入考试、导师审核、不得独立开展高风险实验。"
    elif identity in ["新进教师","实验技术人员"]:
        note = "重点强化责任落实、风险辨识、台账管理和隐患闭环。"
    else:
        note = "重点强化短期进入安全告知、陪同管理和禁止独立操作。"
    df = data["knowledge"][data["knowledge"]["一级类别"].isin(set(cats))]
    return df[["一级类别","二级类别","标题","内容"]].head(30), note

st.sidebar.title("🧪 LabSafeEdu")
page = st.sidebar.radio("选择功能模块", ["首页","智能问答与应急助手","制度案例知识库","安全准入学习","实验前风险评估","隐患识别与整改","案例微课堂","准入考试与错题反馈","安全数据分析看板"])
st.sidebar.markdown("---")
st.sidebar.caption("高校化学与材料类实验室安全教育与风险闭环智能体")

if page == "首页":
    st.title("LabSafeEdu实验室安全智能体")
    st.caption("面向高校化学与材料类实验室的安全准入、风险评估、隐患整改与数据治理智能体")
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("知识条目", f"{len(data['knowledge'])}条")
    c2.metric("隐患规则", f"{len(data['hazards'])}条")
    c3.metric("考试题库", f"{len(data['exam'])}题")
    c4.metric("案例库", f"{len(data['cases'])}例")
    c5.metric("管理数据", "832项")
    st.subheader("系统定位")
    st.write("LabSafeEdu围绕学生准入、实验前风险评估、隐患识别整改、案例化育人、准入考试评价和安全管理数据分析，提供知识问答、风险研判、整改建议、个性化学习和管理辅助服务。")
    st.subheader("智能化能力自查后增强点")
    st.dataframe(pd.DataFrame([
        ["应急意图优先识别","头晕、刺鼻气味、化学品进眼、皮肤接触等先进入应急处置，而不是普通问答。"],
        ["隐患兜底判断","没有提前内置的隐患，也能按门禁、用电、用水、气瓶、废液、PPE等类别给出初步整改。"],
        ["准入学习个性化","根据身份和实验室类型生成学习路径。"],
        ["风险评估综合打分","结合文本描述和勾选因素生成风险等级、审批备案和检查清单。"],
        ["错题反馈联动知识库","薄弱知识点可反向检索学习资料。"]
    ], columns=["增强点","说明"]), use_container_width=True)

elif page == "智能问答与应急助手":
    st.header("智能问答与应急助手")
    examples = ["我做实验的过程中有点头晕，接下来我该怎么办？","实验时闻到刺鼻气味，应该怎么处理？","有化学品溅到眼睛里怎么办？","巡检发现有学生实验室不关门","有人把插排放在水池旁边","我今晚要做有机溶剂加热回流实验，需要注意什么？"]
    q = st.text_area("请输入问题", st.selectbox("示例问题", examples), height=120)
    if st.button("生成智能建议"):
        scene, level, rows = answer_ai(q)
        c1,c2 = st.columns(2)
        c1.metric("识别场景", scene)
        c2.metric("风险/状态", level)
        st.dataframe(pd.DataFrame(rows, columns=["项目","建议内容"]), use_container_width=True)


elif page == "制度案例知识库":
    st.header("制度案例知识库")
    st.caption("知识库基于本地 data/ 数据文件构建。管理者可通过表格模板批量更新制度变化、隐患规则、问答和案例。")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["制度知识", "隐患整改库", "问答库", "资料来源", "管理者更新"])

    with tab1:
        cats = ["全部"] + sorted(data["knowledge"]["一级类别"].dropna().unique().tolist())
        cat = st.selectbox("选择类别", cats)
        kw = st.text_input("检索关键词", "废液")
        df = data["knowledge"]
        if cat != "全部":
            df = df[df["一级类别"] == cat]
        res = search_df(df, kw, ["标题", "内容", "关键词", "一级类别", "二级类别"], topn=30) if kw else df
        if len(res) == 0:
            st.warning("未找到精确结果，已显示当前类别部分条目。建议换用更短关键词。")
            st.dataframe(df.head(20), use_container_width=True)
        else:
            display_cols = ["一级类别", "二级类别", "标题", "内容", "关键词", "更新日期", "状态", "_相关度"]
            st.dataframe(safe_table_for_display(res, display_cols), use_container_width=True)

    with tab2:
        kw2 = st.text_input("检索隐患", "气瓶")
        res = search_df(data["hazards"], kw2, ["隐患描述", "隐患类别", "问题分析", "整改建议", "关键词"], topn=30)
        if len(res) == 0:
            st.warning("未命中隐患库，可在“隐患识别与整改”模块使用智能兜底判断。")
        else:
            st.dataframe(res, use_container_width=True)

    with tab3:
        kw3 = st.text_input("检索问答", "头晕")
        res = search_df(data["qa"], kw3, ["问题", "答案", "关键词", "类别"], topn=30)
        st.dataframe(res, use_container_width=True)

    with tab4:
        st.dataframe(data["refs"], use_container_width=True)
        st.info("资料来源用于说明知识库构建依据。制度发生变化时，可在“管理者更新”中上传新版制度条目或替换资料来源表。")

    with tab5:
        st.subheader("管理者更新入口")
        st.write("适用场景：学校制度更新、学院新增管理要求、隐患库扩充、考试题库调整、案例库补充。")

        st.warning("提示：本地运行时点击保存会直接更新本地 data/ 文件；Streamlit Cloud 在线演示环境的写入可能会在重启后丢失。线上长期使用建议将更新后的 CSV 提交到 GitHub 仓库或接入数据库。")

        dataset_label = st.selectbox("选择要维护的数据表", list(DATASET_CONFIG.keys()))
        cfg = DATASET_CONFIG[dataset_label]
        current_df = data[cfg["key"]]

        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "下载当前数据备份 CSV",
                dataset_to_csv_bytes(current_df),
                file_name=cfg["file"],
                mime="text/csv",
            )
        with c2:
            st.download_button(
                "下载空白模板 CSV",
                empty_template_bytes(cfg["template"]),
                file_name=cfg["file"].replace(".csv", "_template.csv"),
                mime="text/csv",
            )

        st.markdown("#### 批量上传更新")
        uploaded = st.file_uploader("上传更新后的 CSV 或 Excel 文件", type=["csv", "xlsx", "xls"], key=f"upload_{dataset_label}")
        if uploaded is not None:
            try:
                new_df = read_uploaded_table(uploaded)
                ok, msg = validate_dataset(new_df, cfg["required"])
                if ok:
                    st.success(msg)
                    st.write("上传数据预览：")
                    st.dataframe(new_df.head(20), use_container_width=True)
                    if st.button("保存并覆盖本地数据文件", type="primary", key=f"save_{dataset_label}"):
                        save_dataset_to_local(dataset_label, new_df)
                        st.success("已保存到本地 data/ 文件。页面将刷新并加载新数据。")
                        st.rerun()
                else:
                    st.error(msg)
                    st.write("该数据表必需列：")
                    st.code("，".join(cfg["required"]))
            except Exception as e:
                st.error(f"读取上传文件失败：{e}")

        st.markdown("---")
        st.markdown("#### 快速新增一条制度知识")
        with st.form("add_knowledge_form"):
            col1, col2 = st.columns(2)
            with col1:
                new_cat = st.text_input("一级类别", "危险化学品")
                new_sub = st.text_input("二级类别", "制度更新")
                new_title = st.text_input("标题", "新版危险化学品管理要求")
            with col2:
                new_keywords = st.text_input("关键词", "危化品 台账 领用")
                new_date = st.text_input("更新日期", str(datetime.now().date()))
                new_status = st.selectbox("状态", ["现行", "试行", "已废止", "待审核"])
            new_content = st.text_area("制度内容 / 管理要求", height=120)
            submitted = st.form_submit_button("新增到制度知识库")
            if submitted:
                if not new_title.strip() or not new_content.strip():
                    st.error("标题和内容不能为空。")
                else:
                    base_df = data["knowledge"].copy()
                    row = {
                        "一级类别": new_cat,
                        "二级类别": new_sub,
                        "标题": new_title,
                        "内容": new_content,
                        "关键词": new_keywords,
                        "更新日期": new_date,
                        "状态": new_status,
                    }
                    for col in base_df.columns:
                        if col not in row:
                            row[col] = ""
                    base_df = pd.concat([base_df, pd.DataFrame([row])], ignore_index=True)
                    save_dataset_to_local("制度知识库", base_df)
                    st.success("已新增制度条目。页面将刷新并加载新数据。")
                    st.rerun()

        st.markdown("#### 当前数据结构")
        st.dataframe(pd.DataFrame({
            "数据表": list(DATASET_CONFIG.keys()),
            "本地文件": [DATASET_CONFIG[x]["file"] for x in DATASET_CONFIG],
            "必需列": ["、".join(DATASET_CONFIG[x]["required"]) for x in DATASET_CONFIG],
        }), use_container_width=True)

elif page == "安全准入学习":
    st.header("安全准入学习")
    identity = st.selectbox("身份", ["本科生","研究生","新进教师","实验技术人员","短期进入实验室人员"])
    lab = st.selectbox("实验室类型", ["化学类实验室","材料类实验室","机电类实验室","生物类实验室","其他实验室"])
    focus = st.multiselect("重点学习内容", sorted(data["knowledge"]["一级类别"].unique().tolist()), default=["准入与责任体系","个人防护","危险化学品","实验废弃物","消防与应急处置"])
    if st.button("生成准入学习方案"):
        df, note = access_learning_plan(identity, lab, focus)
        st.info(note)
        st.dataframe(df, use_container_width=True)
        st.success("建议流程：安全告知 → 制度学习 → 现场设施确认 → 准入考试 → 导师审核 → 首次实验陪同/复核。")

elif page == "实验前风险评估":
    st.header("实验前风险评估")
    exp = st.text_input("实验名称", "有机溶剂加热回流与气相色谱检测实验")
    desc = st.text_area("实验条件、化学品、设备和时间", "使用有机溶剂，加热回流，气相色谱检测，晚上进行，产生有机废液。", height=120)
    col1,col2,col3 = st.columns(3)
    checks = []
    with col1:
        if st.checkbox("夜间实验"): checks.append("夜间")
        if st.checkbox("首次独立操作"): checks.append("首次 独立")
    with col2:
        if st.checkbox("使用气瓶"): checks.append("气瓶")
        if st.checkbox("高温/高压"): checks.append("高温 高压")
    with col3:
        if st.checkbox("大量有机溶剂"): checks.append("大量 有机溶剂")
        if st.checkbox("管制类化学品"): checks.append("管制")
    if st.button("生成风险评估报告"):
        text = exp + " " + desc + " " + " ".join(checks)
        emergency = emergency_response(text)
        if emergency:
            scene, level, rows = emergency
            st.error("检测到人员不适或暴露描述，应优先按应急处置处理。")
            st.dataframe(pd.DataFrame(rows, columns=["项目","建议内容"]), use_container_width=True)
        else:
            level, score, factors = detect_risk(text)
            st.metric("初步风险等级", level)
            st.metric("风险分值", score)
            if factors:
                st.dataframe(pd.DataFrame(factors, columns=["风险因素","分值","控制措施"]), use_container_width=True)
            else:
                st.info("未命中高风险因素，但仍需完成基础安全检查。")
            pre = ["查阅SDS和实验方案","确认PPE和通风橱","检查水、电、气和加热设备","准备分类废液桶和标签","明确导师/负责人和应急联系人","实验结束完成离室检查"]
            if level in ["高风险","重大风险"]:
                pre += ["完成导师审核或实验室负责人审批","涉及夜间实验时完成夜间备案","不建议单人开展高风险实验"]
            st.dataframe(pd.DataFrame({"实验前检查项目":pre,"是否完成":["□"]*len(pre)}), use_container_width=True)

elif page == "隐患识别与整改":
    st.header("隐患识别与整改")
    htext = st.text_area("请输入隐患描述", "巡检发现有学生实验室不关门", height=120)
    if st.button("生成整改建议"):
        h = search_hazard(htext)
        source = "隐患库精确/相近匹配"
        if h is None:
            h = fallback_hazard(htext)
            source = "智能兜底判断"
        st.metric("风险等级", h["风险等级"])
        st.caption(f"识别来源：{source}")
        st.dataframe(pd.DataFrame([["隐患类别",h["隐患类别"]],["问题分析",h["问题分析"]],["整改建议",h["整改建议"]],["复查要点",h["复查要点"]],["整改时限建议","高风险和重大风险应立即整改；中风险应限期整改并复查销号。"]], columns=["项目","内容"]), use_container_width=True)

elif page == "案例微课堂":
    st.header("案例微课堂")
    row = data["cases"][data["cases"]["案例名称"] == st.selectbox("选择案例", data["cases"]["案例名称"].tolist())].iloc[0]
    st.metric("风险等级", row["风险等级"])
    st.markdown(f"**案例描述：** {row['案例描述']}")
    st.markdown(f"**风险分析：** {row['风险分析']}")
    st.markdown(f"**正确做法：** {row['正确做法']}")
    st.markdown(f"**追问问题：** {row['追问问题']}")
    st.markdown(f"**教学目标：** {row['教学目标']}")

elif page == "准入考试与错题反馈":
    st.header("准入考试与错题反馈")
    exam = data["exam"]
    qtype = st.selectbox("题型", ["全部"] + sorted(exam["题型"].unique().tolist()))
    n = st.slider("抽题数量", 5, 20, 10)
    df = exam if qtype=="全部" else exam[exam["题型"]==qtype]
    sample = df.sample(min(n,len(df)), random_state=42)
    for i,row in enumerate(sample.itertuples(),1):
        with st.expander(f"{i}. 【{row.题型}】{row.题目}"):
            if isinstance(row.选项,str) and row.选项.strip():
                st.text(row.选项)
            st.write(f"**答案：** {row.答案}")
            st.write(f"**解析：** {row.解析}")
            st.caption(f"知识点：{row.知识点}")
    weak = st.multiselect("选择薄弱知识点，生成复习建议", sorted(exam["知识点"].dropna().unique().tolist()))
    if st.button("生成复习建议"):
        if weak:
            for w in weak:
                res = search_df(data["knowledge"], w, ["标题","内容","关键词","一级类别","二级类别"], topn=3)
                st.write(f"**{w}**")
                st.dataframe(res[["一级类别","二级类别","标题","内容"]] if len(res)>0 else pd.DataFrame([["建议进入制度案例知识库检索相关内容"]], columns=["建议"]), use_container_width=True)
        else:
            st.info("请选择薄弱知识点。")

elif page == "安全数据分析看板":
    st.header("安全数据分析看板")
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("检查实验室", "133间")
    c2.metric("累计隐患", "832项")
    c3.metric("化学安全隐患", "384项")
    c4.metric("整改率", "89%→100%")
    st.subheader("隐患分类统计")
    st.dataframe(data["hazard_stats"], use_container_width=True)
    plot_df = data["hazard_stats"][data["hazard_stats"]["隐患类别"]!="合计"]
    fig, ax = plt.subplots()
    ax.bar(plot_df["隐患类别"], plot_df["数量"])
    ax.set_title("隐患类别数量分布")
    ax.set_ylabel("数量")
    plt.xticks(rotation=30, ha="right")
    st.pyplot(fig)
    st.subheader("风险等级分布")
    st.dataframe(data["risk_stats"], use_container_width=True)
    st.info("管理建议：以化学安全和基础安全为重点，强化危化品、废液、气瓶、用电、夜间实验和大型仪器连续运行管理；对重大风险和高风险实验室实施分级分类监管。")
