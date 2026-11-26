import csv
import random
import json
import os
import base64
import warnings
import streamlit as st
import ollama
from streamlit_local_storage import LocalStorage

# Python 3.8以降の非推奨警告を非表示化
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

# ==============================================================================
# ★ 1. クイズ設定・基本パラメータ（ここを変更して1周あたりの問題数を調整できます）
# ==============================================================================
MAX_MISTAKES = 3                # 最大誤答数（3回でゲームオーバー）
BASE_SCORE = 5                  # 正解時の基本獲得ポイント
TOTAL_QUIZ_COUNT = 10           # ★ 1周あたりの出題数（ここを好きな数字に変更してください。None にするとCSVの全問題を出題）

# --- ディレクトリ & ファイルパス設定 ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "images")
QUESTIONS_CSV_PATH = "quiz_questions.csv"  # クイズデータファイル名

# 背景画像ファイル名（images/ 直下に配置）
QUIZ_SHOP_BG = "bg1.jpg"   # クイズ・ショップ画面用背景
COMPLETED_BG = "bg2.jpg"   # おもちゃ箱画面用背景

# ==============================================================================
# ★ 2. キャラクター＆ショップ定義（新キャラ追加はここを編集するだけでOK！）
# ==============================================================================
# 新しいキャラクターを追加する場合は、以下のリストに辞書を追加し、
# images/{id}/ フォルダ内に各部位の画像（head.jpg, body.jpg, right_hand.jpg, left_hand.jpg, right_leg.jpg, left_leg.jpg, complete.jpg）を配置してください。
# ※特定の部位が存在しないキャラ（ぶろっこりの頭など）は "exclude_parts": ["head"] のように指定できます。

CHARACTERS = [
    {"id": "panda", "name": "ぱんだ", "emoji": "👑"},
    {"id": "broccoli", "name": "ぶろっこり", "emoji": "🥦", "exclude_parts": ["head"]},
    {"id": "kappa", "name": "かっぱ", "emoji": "🥒"},
    {"id": "tengu", "name": "てんぐ", "emoji": "👺"},
    {"id": "saru", "name": "さる", "emoji": "🐵"},
    {"id": "buru", "name": "ブルさん", "emoji": "🐶"},
    {"id": "daruma", "name": "だるま", "emoji": "　"},
    {"id": "kinoko", "name": "キノコ", "emoji": "🍄"},
    {"id": "megami", "name": "めがみ", "emoji": "🗽"},
    {"id": "katteni", "name": "スター", "emoji": "🎤"},

    # --- 新キャラ追加例（コメントを外して使えます） ---
    # {"id": "usagi", "name": "うさぎ", "emoji": "🐰"},
]

# 部位のマスター定義（価格やファイル名を一元管理）
PART_TEMPLATES = {
    "head":       {"label": "あたま",   "price": 80, "file": "head.jpg"},
    "body":       {"label": "からだ",   "price": 80, "file": "body.jpg"},
    "right_hand": {"label": "みぎて",   "price": 50, "file": "right_hand.jpg"},
    "left_hand":  {"label": "ひだりて", "price": 50, "file": "left_hand.jpg"},
    "right_leg":  {"label": "みぎあし", "price": 50, "file": "right_leg.jpg"},
    "left_leg":   {"label": "ひだりあし", "price": 50, "file": "left_leg.jpg"},
}

# CHARACTERS の定義から SHOP_ITEMS を自動生成する関数
def build_shop_items():
    shop = {part_key: [] for part_key in PART_TEMPLATES.keys()}
    for char in CHARACTERS:
        char_id = char["id"]
        char_name = char["name"]
        emoji = char.get("emoji", "✨")
        excluded = char.get("exclude_parts", [])
        
        for part_key, p_info in PART_TEMPLATES.items():
            if part_key in excluded:
                continue
            shop[part_key].append({
                "id": f"{char_id}_{part_key}",
                "char_id": char_id,
                "name": f"{emoji} {char_name}の{p_info['label']}",
                "price": p_info["price"],
                "file": p_info["file"]
            })
    return shop

SHOP_ITEMS = build_shop_items()

# --- ブラウザ（ローカルストレージ）セーブ・ロード関数 ---
local_storage = LocalStorage()
DEFAULT_USER_DATA = {"wallet": 0, "owned_items": [], "completed_chars": []}

def load_user_data_from_browser():
    try:
        saved_str = local_storage.getItem("quiz_app_user_data")
        if saved_str:
            return json.loads(saved_str)
    except Exception:
        pass
    return DEFAULT_USER_DATA.copy()

def save_user_data_to_browser(data):
    try:
        local_storage.setItem("quiz_app_user_data", json.dumps(data, ensure_ascii=False))
    except Exception:
        st.warning("端末へのデータ保存に失敗しました。")

if "user_data" not in st.session_state:
    st.session_state.user_data = load_user_data_from_browser()

# --- 拡張子揺らぎ吸収・画像パス取得関数 ---
def find_existing_image_path(*path_segments):
    base_path = os.path.join(*path_segments)
    if not base_path:
        return None
    if os.path.exists(base_path):
        return base_path
    
    root, _ = os.path.splitext(base_path)
    for ext in ['.jpg', '.JPG', '.jpeg', '.JPEG', '.png', '.PNG', '.webp', '.WEBP']:
        alt_path = root + ext
        if os.path.exists(alt_path):
            return alt_path
    return None

# --- 安全な画像表示ユーティリティ ---
def safe_render_image(image_path, width=None, use_container_width=False, caption=None):
    if not image_path or not os.path.exists(image_path):
        st.warning(f"※画像が見つかりません: {os.path.basename(image_path) if image_path else ''}")
        return
    try:
        if width:
            st.image(image_path, width=width, caption=caption)
        else:
            st.image(image_path, use_container_width=use_container_width, caption=caption)
    except Exception:
        st.warning(f"※画像読み込みエラー: {os.path.basename(image_path)}")

# --- 全面背景画像CSS適用関数 ---
def set_full_screen_background(image_filename):
    image_path = find_existing_image_path(IMAGE_DIR, image_filename)
    if image_path:
        try:
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode()
            st.markdown(
                f"""
                <style>
                .stApp {{
                    background-image: url("data:image/jpeg;base64,{encoded_string}");
                    background-size: cover;
                    background-position: center;
                    background-repeat: no-repeat;
                    background-attachment: fixed;
                }}
                .stApp, .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp span, .stMarkdown, .stTextArea, .stSelectbox, div[data-testid="stMetricValue"] {{
                    color: #000000 !important;
                }}
                .stMarkdown, .stTextArea, .stSelectbox, div[data-testid="stMetricValue"] {{
                    background-color: rgba(255, 255, 255, 0.85) !important;
                    padding: 8px;
                    border-radius: 8px;
                }}
                .stButton > button {{
                    background-color: #ffffff !important;
                    color: #000000 !important;
                    border: 2px solid #333333 !important;
                    font-weight: bold !important;
                    border-radius: 8px !important;
                }}
                .stButton > button:hover {{
                    background-color: #f0f0f0 !important;
                    color: #000000 !important;
                    border-color: #000000 !important;
                }}
                div[data-testid="stAlert"] {{
                    background-color: rgba(255, 255, 255, 0.95) !important;
                    color: #000000 !important;
                    font-weight: bold !important;
                    font-size: 1.15rem !important;
                    border: 2px solid #333333 !important;
                    border-radius: 10px;
                }}
                div[data-testid="stAlert"] p {{
                    color: #000000 !important;
                    font-weight: bold !important;
                }}
                </style>
                """,
                unsafe_allow_html=True
            )
        except Exception:
            pass

# --- A. クイズCSVデータ読み込み関数 ---
@st.cache_data
def load_questions(filepath):
    csv_path = os.path.join(BASE_DIR, filepath)
    questions = []
    if not os.path.exists(csv_path):
        st.error(f"クイズデータが見つかりません: {filepath}")
        return questions
        
    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if "id" in row and row["id"].strip():
                questions.append(row)
    return questions

# --- B. 判定ロジック ---
def judge_qa(user_input, correct_str):
    answers = [ans.strip().lower() for ans in correct_str.split("/")]
    return user_input.strip().lower() in answers

def judge_essay_keywords(user_input, keywords_str):
    if not keywords_str:
        return True, []
    and_groups = [group.strip() for group in keywords_str.split(",")]
    missing_groups = []
    for group in and_groups:
        or_keywords = [kw.strip() for kw in group.split("|")]
        if not any(kw in user_input for kw in or_keywords):
            missing_groups.append(" または ".join(or_keywords))
    return len(missing_groups) == 0, missing_groups

def judge_essay_with_ollama(question, user_ans, model_ans, keywords, is_kw_ok, missing_kws):
    kw_status = "【キーワード判定】: 必須キーワード条件をすべて満たしています。" if is_kw_ok else f"【キーワード判定】: 不足 -> {', '.join(missing_kws)}"
    prompt = f"""
あなたは採点補助AIです。以下の基準に従って採点してください。
【問題】: {question}
【模範解答】: {model_ans}
【必須キーワード仕様】: {keywords}
{kw_status}
【ユーザーの回答】: {user_ans}

【採点基準】:
1. 必須キーワードがすべて含まれ、内容が概ね8割以上正しい場合は「判定：正解」としてください。
2. それ以外は「判定：不正解」または「判定：おしい」としてください。

【出力フォーマット】:
1行目:「判定：正解」「判定：おしい」「判定：不正解」のいずれか
2行目以降:「アドバイス：(簡潔な解説)」
"""
    try:
        response = ollama.chat(model='qwen2.5', messages=[{'role': 'user', 'content': prompt}])
        return response['message']['content']
    except Exception as e:
        return f"判定：エラー\nAI判定エラー: {e}"

def calculate_combo_bonus(combo):
    if combo >= 5:
        return 5
    elif combo >= 3:
        return 3
    elif combo >= 2:
        return 1
    return 0

# --- C. メイン画面 & サイドバー表示 ---
st.sidebar.title("🎮 メニュー")
mode = st.sidebar.radio("モード選択", ["クイズに挑戦", "ショップ", "おもちゃ箱（キャラ保存・図鑑）"])

with st.sidebar.expander("⚙️ 端末データの管理"):
    if st.button("セーブデータを初期化"):
        st.session_state.user_data = DEFAULT_USER_DATA.copy()
        save_user_data_to_browser(st.session_state.user_data)
        st.success("データを初期化しました。")
        st.rerun()

# --- モード1: クイズに挑戦 ---
if mode == "クイズに挑戦":
    set_full_screen_background(QUIZ_SHOP_BG)
    st.title("⚔️ クイズ＆論述 チャレンジ")

    all_questions = load_questions(QUESTIONS_CSV_PATH)
    total_csv_count = len(all_questions)
    
    # コード上で設定された問題数（TOTAL_QUIZ_COUNT）を決定
    if TOTAL_QUIZ_COUNT is not None and TOTAL_QUIZ_COUNT > 0:
        session_quiz_count = min(TOTAL_QUIZ_COUNT, total_csv_count)
    else:
        session_quiz_count = total_csv_count

    st.sidebar.markdown("---")
    if st.sidebar.button("🎮 ゲームスタート！", use_container_width=True, disabled=(total_csv_count == 0)):
        selected_q = random.sample(all_questions, session_quiz_count)
        st.session_state.quiz_list = selected_q
        st.session_state.current_idx = 0
        st.session_state.score = 0
        st.session_state.combo = 0
        st.session_state.mistakes = 0
        st.session_state.loop_count = 1
        st.session_state.game_over = False
        st.session_state.answered = False
        st.session_state.pt_saved = False
        st.rerun()

    if "quiz_list" in st.session_state and st.session_state.quiz_list:
        if st.session_state.mistakes >= MAX_MISTAKES:
            st.session_state.game_over = True

        if not st.session_state.game_over and st.session_state.current_idx >= len(st.session_state.quiz_list):
            st.session_state.loop_count += 1
            st.session_state.current_idx = 0
            # 次の周回でも設定された問題数で再抽選
            st.session_state.quiz_list = random.sample(all_questions, session_quiz_count)
            st.toast(f"🎉 1周クリア！ {st.session_state.loop_count}周目に入ります！", icon="🔄")

        if not st.session_state.game_over:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("周回数", f"{st.session_state.get('loop_count', 1)} 周目")
            col2.metric("獲得Pt", f"{st.session_state.score} Pt")
            col3.metric("コンボ", f"{st.session_state.combo} 連勝")
            col4.metric("ライフ", "❤️" * (MAX_MISTAKES - st.session_state.mistakes))
            
            st.markdown("---")
            idx = st.session_state.current_idx
            current_q = st.session_state.quiz_list[idx]
            
            total_q_count = len(st.session_state.quiz_list)
            st.subheader(f"第 {idx + 1} / {total_q_count} 問 (ID: {current_q['id']})")
            st.info(current_q["question"])
            user_ans = st.text_area("あなたの回答を入力してください", key=f"input_{st.session_state.loop_count}_{idx}")
            
            col_send, col_quit = st.columns([2, 1])
            with col_send:
                if st.button("回答を送信") and not st.session_state.get("answered", False):
                    st.session_state.answered = True
                    is_correct = False
                    
                    if current_q["type"] == "qa":
                        if judge_qa(user_ans, current_q["answer"]):
                            is_correct = True
                        else:
                            st.error("❌ 不正解")
                            st.write(f"**模範解答**: {current_q['answer']}")
                    elif current_q["type"] == "essay":
                        is_kw_ok, missing_kws = judge_essay_keywords(user_ans, current_q["keywords"])
                        with st.spinner("AI判定中..."):
                            ai_feedback = judge_essay_with_ollama(
                                current_q["question"], user_ans, current_q["answer"], 
                                current_q["keywords"], is_kw_ok, missing_kws
                            )
                        if "判定：正解" in ai_feedback or "判定: 正解" in ai_feedback:
                            is_correct = True
                        else:
                            st.error("❌ 不正解")
                        st.write("**AIフィードバック**:")
                        st.write(ai_feedback)
                        st.info(f"**模範解答**: {current_q['answer']}")

                    if is_correct:
                        st.session_state.combo += 1
                        bonus = calculate_combo_bonus(st.session_state.combo)
                        earned = BASE_SCORE + bonus
                        st.session_state.score += earned
                        st.success(f"🎉 正解！ +{earned}Pt 獲得！")
                    else:
                        st.session_state.combo = 0
                        st.session_state.mistakes += 1

            with col_quit:
                if st.button("🛑 途中でやめる（ポイント確定）"):
                    st.session_state.game_over = True
                    st.rerun()

            if st.session_state.get("answered", False):
                if st.button("次の問題へ"):
                    st.session_state.current_idx += 1
                    st.session_state.answered = False
                    st.rerun()

        else:
            if st.session_state.mistakes < MAX_MISTAKES:
                st.balloons()
                st.header("🏆 チャレンジ終了！お疲れ様でした")
            else:
                st.snow()
                st.header("💔 ゲームオーバー！結果発表")
            
            earned_pt = st.session_state.score
            st.subheader(f"到達: {st.session_state.get('loop_count', 1)} 周目 / 獲得スコア: {earned_pt} Pt")
            
            if "pt_saved" not in st.session_state or not st.session_state.pt_saved:
                st.session_state.user_data["wallet"] += earned_pt
                save_user_data_to_browser(st.session_state.user_data)
                st.session_state.pt_saved = True
            
            st.success(f"所持ポイントへ追加されました！（現在: {st.session_state.user_data['wallet']} Pt）")
            if st.button("もう一度挑戦する"):
                del st.session_state.quiz_list
                st.session_state.pt_saved = False
                st.rerun()

# --- モード2: ショップ ---
elif mode == "ショップ":
    set_full_screen_background(QUIZ_SHOP_BG)
    st.title("🛍️ パーツショップ")
    
    wallet = st.session_state.user_data["wallet"]
    st.subheader(f"現在の所持ポイント: {wallet} Pt")
    st.markdown("---")
    
    owned = st.session_state.user_data["owned_items"]

    cat_labels = {
        "head": "👑 あたま パーツ",
        "body": "🥋 からだ パーツ",
        "right_hand": "⚔️ みぎて パーツ",
        "left_hand": "🛡️ ひだりて パーツ",
        "right_leg": "🦵 みぎあし パーツ",
        "left_leg": "🦵 ひだりあし パーツ"
    }

    for cat_key, items in SHOP_ITEMS.items():
        if not items:
            continue
        
        st.write(f"### **{cat_labels.get(cat_key, cat_key.upper())}**")
        cols = st.columns(2)
        for i, item in enumerate(items):
            with cols[i % 2]:
                is_owned = item["id"] in owned
                char_label = ""
                if "char_id" in item:
                    c_info = next((c for c in CHARACTERS if c["id"] == item["char_id"]), None)
                    if c_info:
                        char_label = f"[{c_info['name']}] "
                
                part_img_path = find_existing_image_path(IMAGE_DIR, item["char_id"], item["file"])
                safe_render_image(part_img_path, width=120)
                
                st.write(f"**{char_label}{item['name']}**")
                st.write(f"価格: {item['price']} Pt")
                if is_owned:
                    st.success("購入済み")
                else:
                    if st.button(f"購入", key=f"buy_{item['id']}"):
                        if wallet >= item["price"]:
                            st.session_state.user_data["wallet"] -= item["price"]
                            st.session_state.user_data["owned_items"].append(item["id"])
                            save_user_data_to_browser(st.session_state.user_data)
                            st.success(f"{item['name']} を購入しました！")
                            st.rerun()
                        else:
                            st.error("ポイントが不足しています")

# --- モード3: おもちゃ箱 ---
elif mode == "おもちゃ箱（キャラ保存・図鑑）":
    set_full_screen_background(COMPLETED_BG)
    
    st.title("🧸 おもちゃ箱（キャラ解放・図鑑）")
    
    selected_char_info = st.selectbox("完成させるキャラクターを選択", CHARACTERS, format_func=lambda x: x["name"])
    target_char_id = selected_char_info["id"]
    owned_ids = st.session_state.user_data["owned_items"]
    
    target_all_items = []
    for cat_key, items in SHOP_ITEMS.items():
        for item in items:
            if item.get("char_id") == target_char_id:
                target_all_items.append(item)

    owned_target_items = [item for item in target_all_items if item["id"] in owned_ids]
    
    total_needed_count = len(target_all_items)
    owned_count = len(owned_target_items)
    
    st.markdown("---")
    
    if total_needed_count > 0 and owned_count == total_needed_count:
        char_name = st.text_input("キャラクターの登録名", value=selected_char_info["name"])
        complete_img_path = find_existing_image_path(IMAGE_DIR, target_char_id, "complete.jpg")
        
        st.write("### 【完成イラスト】")
        safe_render_image(complete_img_path, width=350, caption=f"完成カード: {char_name}")
            
        if st.button("この完成品を図鑑に保存！"):
            new_char = {
                "base_char": selected_char_info["name"],
                "name": char_name,
                "img_path": complete_img_path
            }
            st.session_state.user_data["completed_chars"].append(new_char)
            save_user_data_to_browser(st.session_state.user_data)
            st.success("図鑑に保存しました！")
            st.rerun()
            
    else:
        st.warning(f"「{selected_char_info['name']}」のパーツがまだ揃っていません。（所持数: {owned_count} / {total_needed_count}）")

    st.markdown("---")
    st.subheader("📖 保存済みキャラクター図鑑")
    chars = st.session_state.user_data["completed_chars"]
    if chars:
        cols = st.columns(3)
        for idx, c in enumerate(chars):
            with cols[idx % 3]:
                st.write(f"**No.{idx + 1} {c['name']}**")
                img_p = find_existing_image_path(c.get('img_path', ''))
                safe_render_image(img_p, use_container_width=True)
    else:
        st.write("まだ保存されたキャラクターはありません。")