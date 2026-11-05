#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Daily Intelligence & Twitter Formatter - Google AI Studio Auto Updater
每天定时运行：抓取全网热搜事件 -> 调用 Gemini 2.5 Flash 生成推特发帖长文 -> 自动更新网页
"""
import os
import re
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AQ.Ab8RN6JluJlv-VhrZmQTDNE8KQRpxTSWfzud2bSlNlDJjk9jkQ")
GEMINI_MODEL = "gemini-2.5-flash"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_FILE = os.path.join(BASE_DIR, "index.html")

# 严苛文风规范（继承 STYLE_GUIDE.md）
SYSTEM_PROMPT = """你是一名长期活跃在 Twitter/X 上的深度硬核观察家与财经/科技评论人。你的文字融合了三位推特知名创作者的精髓：
1. @LuBtc888：刺破公关辞令与宏大叙事，直切最底层的商业利益、现金流困境、权势再分配与真金白银博弈；
2. @daxiniu1：冷眼客观的细节白描，用精确数字、关键人物微表情、不可逆的真实时间线说话，杜绝空洞口号；
3. 查百万：冷峻的宿命感与黑色幽默，将荒诞的现实剥皮见骨，不灌鸡汤，不作庸俗说教。

【绝对格式铁律 - 必须严格执行】：
1. 必须适合 Twitter/X 移动端阅读习惯：每行严格控制在 25 个汉字左右（自然呼吸断句）。
2. 每个段落之间必须空一行（双换行）。
3. 全文篇幅：每篇正文控制在 800 至 1200 字，节奏致密，信息量极大。
4. 第一行必须直接输出具体的内容大标题（不得带有【大标题】字样，直接是震撼且具洞察力的单行标题，包含核心冲突）。
5. 严禁出现任何“地摊文学感”或“劣质自媒体套话”：
   - 绝对禁止词汇：【不得不说】【细思极恐】【开挂】【瞬间逆袭】【打脸】【值得深思】【让我们拭目以待】【不是...而是...】【然而现实是...】【拔刀】【震怒】。
   - 绝对禁止“神仙打架、小学生互撕”式的幼稚比喻，必须用专业机构、利益集团、监管审查、资本回报率等真实商业与地缘维度剖析。
6. 结构规范：
   - 开篇（1-2段）：冷峻白描切入核心大事件的最新不可逆节点，抛弃一切客套；
   - 中篇（3-5段）：层层剥开背后的隐秘动机与真金白银计算；
   - 终篇（1-2段）：宿命式冷眼结语，点透游戏规则的残酷本质，不升华，不灌鸡汤。
"""

def fetch_web_hotlist():
    """从公共热榜接口获取今日真实热搜"""
    topics = []
    # 尝试 1: vvhan 热榜接口 (知乎/微博)
    for endpoint, cat in [("wbHot", "国内热点"), ("zhihuHot", "科技与大厂")]:
        try:
            req = urllib.request.Request(
                f"https://api.vvhan.com/api/hotlist/{endpoint}",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                for item in data.get('data', [])[:5]:
                    title = item.get('title', '').strip()
                    desc = item.get('desc', '') or item.get('hot', '')
                    if title and len(title) > 6:
                        topics.append({"title": title, "summary": desc, "category": cat})
        except Exception:
            pass

    # 尝试 2: rebang.today 解析
    if len(topics) < 6:
        try:
            req = urllib.request.Request(
                "https://rebang.today/?from=itab.link",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
            matches = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', html)
            for href, inner in matches:
                t = re.sub(r'<[^>]+>', '', inner).strip()
                if len(t) > 10 and not t.startswith('http') and not t.startswith('GitHub'):
                    topics.append({"title": t, "summary": "今日全网高频搜索与热议事件", "category": "国内热点"})
                if len(topics) >= 12:
                    break
        except Exception:
            pass

    # 若网络接口全部波动，使用当天高质量前沿备用事实选题（保证系统绝对不崩溃）
    if len(topics) < 4:
        topics = [
            {"title": "OpenAI与Anthropic企业级大模型价格战再升级：推理算力折旧与企业采购的暗流", "summary": "API降价背后是芯片算力集群的沉没成本与大客户锁定", "category": "科技与大厂博弈"},
            {"title": "半导体先进制程设备出口管制新规落地：全球芯片供应链的二次割裂", "summary": "从成熟制程到先进封装的全球资本支出重构", "category": "国际前沿大局"},
            {"title": "地方城投债务置换与专项债发行提速：地方资产负债表与银行信贷考核", "summary": "从隐性债务到合规化阳光化背后的各方博弈", "category": "国内热点剖析"},
            {"title": "新能源汽车价格战向海外市场蔓延：关税壁垒、海外建厂与本土化阻击", "summary": "中国车企出海产业链与欧洲本土工会的博弈", "category": "国内热点剖析"}
        ]
    return topics[:8]

def call_gemini(prompt: str) -> str:
    """通过 Google AI Studio REST API 调用 Gemini"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.8,
            "maxOutputTokens": 2048,
        }
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={"Content-Type": "application/json"}
    )
    
    with urllib.request.urlopen(req, timeout=30) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        return res["candidates"][0]["content"]["parts"][0]["text"].strip()

def generate_daily_news():
    """获取热点并调用 Gemini 批量生成符合推特格式的深度长文"""
    topics = fetch_web_hotlist()
    print(f"[{datetime.now()}] 准备为 {len(topics)} 条精选热点生成推特排版长文...")
    
    generated_news = []
    
    for i, t in enumerate(topics):
        title = t["title"]
        category = t.get("category", "国内热点剖析")
        print(f"[{i+1}/{len(topics)}] 正在由 Gemini 生成推文: {title[:20]}...")
        
        prompt = f"""请针对以下最新真实新闻线索，撰写一篇符合 Twitter/X 发帖标准的千字硬核深度长推文：

新闻线索：
【标题】：{title}
【背景】：{t.get('summary', '')}
【领域】：{category}

【写作要求】：
1. 第一行直接输出主标题（不要有任何额外文字，如【标题】或书名号）；
2. 提炼一句不超过 45 个字的核心摘要导读；
3. 正文单行约 25 个汉字，断句自然，行与行/段与段之间空一行；
4. 深度 800 至 1200 字，刺穿公关辞令，还原背后的商业利益、成本核算、监管逻辑或宿命博弈；
5. 坚决禁止任何地摊文学腔调与廉价自媒体感叹词。

请以如下 JSON 格式直接返回（不要输出 markdown 代码块标记，直接输出合法 JSON 文本）：
{{
  "title": "单行震撼大标题",
  "summary": "40字以内的核心洞察导读",
  "content": "完整的推特排版长文（含换行符\\n\\n）"
}}
"""
        try:
            raw_output = call_gemini(prompt)
            # 过滤可能的 markdown ```json 标记
            clean_json = re.sub(r'^```json\s*', '', raw_output, flags=re.MULTILINE)
            clean_json = re.sub(r'```$', '', clean_json, flags=re.MULTILINE).strip()
            item_data = json.loads(clean_json)
            
            # 分类映射
            cat_id = "cn"
            cat_name = "国内热点剖析"
            tag = "财经商业与治理"
            if "科技" in category or "大厂" in category or "AI" in title or "芯片" in title:
                cat_id = "tech"
                cat_name = "科技与大厂博弈"
                tag = "互联网巨头公关战"
            elif "国际" in category or "海外" in title or "全球" in title or "美" in title or "欧" in title:
                cat_id = "global"
                cat_name = "国际前沿大局"
                tag = "地缘与经贸博弈"
                
            generated_news.append({
                "id": f"news_auto_{int(time.time())}_{i+1}",
                "category": cat_id,
                "category_name": cat_name,
                "tag": tag,
                "title": item_data.get("title", title),
                "summary": item_data.get("summary", title),
                "content": item_data.get("content", "")
            })
            time.sleep(1) # 礼貌间隔
        except Exception as e:
            print(f"生成该条时出错: {e}")
            continue
            
    print(f"[{datetime.now()}] 成功生成 {len(generated_news)} 条高质量推特长文！")
    return generated_news

def update_html_database(new_news_items):
    """将新生成的资讯无缝写入 index.html，并实现常青库每日置顶轮换"""
    if not os.path.exists(HTML_FILE):
        print(f"未找到 {HTML_FILE}")
        return False
        
    with open(HTML_FILE, 'r', encoding='utf-8') as f:
        html = f.read()
        
    db_match = re.search(r'const DATABASE = (\{[\s\S]*?\});\s*(?:let|var|const|//)', html)
    if not db_match:
        print("未能在 index.html 中定位 DATABASE 对象")
        return False
        
    try:
        db = json.loads(db_match.group(1))
    except Exception as e:
        print(f"解析已有 DATABASE 失败: {e}")
        return False
        
    # 1. 替换/更新今日要闻资讯
    if new_news_items:
        db["news"] = new_news_items
        print(f"已更新 DATABASE.news 为今日最新的 {len(new_news_items)} 篇要闻。")
        
    # 2. 常青库每日轮换算法（基于一年中的第几天轮换置顶）
    day_of_year = datetime.now().timetuple().tm_yday
    
    # 轮换历史档案 7 个国家
    for country_key in ["history_cn", "history_jp", "history_us", "history_de", "history_es", "history_fr", "history_ru"]:
        items = db.get(country_key, [])
        if len(items) > 1:
            shift = day_of_year % len(items)
            db[country_key] = items[shift:] + items[:shift]
            
    # 轮换怪谈与名流
    for key in ["curiosity", "celebrity"]:
        items = db.get(key, [])
        if len(items) > 1:
            shift = day_of_year % len(items)
            db[key] = items[shift:] + items[:shift]
            
    # 3. 序列化并替换回 HTML
    new_db_json = json.dumps(db, ensure_ascii=False, indent=2)
    new_html = html[:db_match.start(1)] + new_db_json + html[db_match.end(1):]
    
    # 4. 更新页面时间戳展示
    today_str = datetime.now().strftime("%Y年%m月%d日")
    new_html = re.sub(r'🕒 [^<]*', f'🕒 已由 Gemini 自动更新 · {today_str}', new_html, count=1)
    
    # 备份原有文件
    bak_file = HTML_FILE + ".bak"
    try:
        with open(bak_file, 'w', encoding='utf-8') as f:
            f.write(html)
    except Exception:
        pass
        
    # 写入新 HTML
    with open(HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(new_html)
        
    print(f"[{datetime.now()}] 成功更新 {HTML_FILE}！今日情报与轮换推荐已全部就绪。")
    return True

def main():
    print("=" * 60)
    print(f"[{datetime.now()}] 启动每日情报自动更新流水线 (Google AI Studio Gemini 驱动)")
    print("=" * 60)
    
    new_news = generate_daily_news()
    if new_news:
        success = update_html_database(new_news)
        if success:
            print(f"[{datetime.now()}] 每日更新大功告成！")
    else:
        print(f"[{datetime.now()}] 今日未生成新的资讯，跳过 HTML 更新。")

if __name__ == "__main__":
    main()
