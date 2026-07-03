@echo off
chcp 65001
echo 正在启动 LabSafeEdu 实验室安全智能体...
echo 如果第一次运行失败，请先执行：pip install -r requirements.txt
streamlit run app.py
pause