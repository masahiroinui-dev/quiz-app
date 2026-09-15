import streamlit as st
from supabase import create_client, Client
import pandas as pd
import time
import base64
import os
import re

# --------------------------------------------------
# ページ設定
# --------------------------------------------------
st.set_page_config(page_title="リアルタイムクイズシステム", page_icon="🧩", layout="wide")

# --------------------------------------------------
# ローカル画像をBase64に変換するヘルパー関数
# --------------------------------------------------
def get_base64_image(image_path: str) -> str:
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    return ""

# --------------------------------------------------
# 背景画像 & スタイル設定
# --------------------------------------------------
bg_file = None
bg_candidates = [
    "bg.png", "bg.jpg", "bg.jpeg", "bg.webp",
    "BG.png", "BG.jpg", "BG.jpeg", "BG.webp",
    "Bg.png", "Bg.jpg"
]

for cand in bg_candidates:
    if os.path.exists(cand):
        bg_file = cand
        break

if bg_file:
    bg_b64 = get_base64_image(bg_file)
    ext = bg_file.split(".")[-1].lower()
    if ext == "jpg":
        ext = "jpeg"
    bg_css = f"""
    <style>
    .stApp {{
        background-image: url("data:image/{ext};base64,{bg_b64}");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}
    </style>
    """
else:
    bg_css = """
    <style>
    .stApp {
        background: linear-gradient(135deg, #1e1e2f 0%, #2a2a40 100%);
    }
    </style>
    """

st.markdown(bg_css, unsafe_allow_html=True)

# 視認性CSS
st.markdown("""
    <style>
    .block-container {
        background: transparent !important;
        box-shadow: none !important;
        padding-top: 2rem !important;
    }

    h1, h2, h3, h4, h5, h6, p, span, label, div, .stMarkdown {
        color: #ffffff !important;
        text-shadow: 0px 2px 6px rgba(0, 0, 0, 0.95), 0px 0px 12px rgba(0, 0, 0, 0.8) !important;
        font-weight: 700 !important;
    }

    section[data-testid="stSidebar"] {
        background-color: rgba(12, 14, 24, 0.75) !important;
        backdrop-filter: blur(10px);
        border-right: 1px solid rgba(255, 255, 255, 0.15);
    }

    input, select, textarea {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
        text-shadow: none !important;
        font-weight: bold !important;
    }

    button[kind="primary"] {
        background-color: #00d2ff !important;
        color: #000000 !important;
        font-weight: bold !important;
        border: none !important;
        box-shadow: 0 0 15px rgba(0, 210, 255, 0.6) !important;
        text-shadow: none !important;
    }

    div[data-testid="stDataFrame"] {
        background-color: rgba(0, 0, 0, 0.6) !important;
        border-radius: 8px;
        backdrop-filter: blur(4px);
    }
    </style>
""", unsafe_allow_html=True)

# --------------------------------------------------
# Supabase 初期化
# --------------------------------------------------
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

try:
    supabase = init_supabase()
except Exception as e:
    st.error("Supabaseへの接続に失敗しました。.streamlit/secrets.toml の設定を確認してください。")
    st.stop()

def safe_execute(query, retries=2, delay=0.2):
    for i in range(retries):
        try:
            return query.execute()
        except Exception as e:
            if i == retries - 1:
                raise e
            time.sleep(delay)

# --------------------------------------------------
# クイズデータ読み込み
# --------------------------------------------------
@st.cache_data
def get_raw_quiz_data():
    csv_file = "questions.csv"
    if os.path.exists(csv_file):
        try:
            df = pd.read_csv(csv_file, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(csv_file, encoding="shift-jis")
            
        if "id" in df.columns:
            df["q_id"] = pd.to_numeric(df["id"], errors="coerce").fillna(0).astype(int)
        else:
            df["q_id"] = range(1, len(df) + 1)
            
        df["answer"] = df["answer"].astype(str).str.strip()
        df["question"] = df["question"].astype(str).str.strip()
        return df
    else:
        st.error(f"クイズファイル `{csv_file}` が見つかりません。")
        st.stop()

df_raw_quiz = get_raw_quiz_data()

# スラッシュ(/や／)区切りの複数正解を判定する関数
def check_is_correct(user_ans: str, raw_correct_ans: str) -> bool:
    if not user_ans or not user_ans.strip():
        return False
    clean_user = user_ans.strip().lower()
    answers = re.split(r'[/／]', str(raw_correct_ans))
    valid_answers = [a.strip().lower() for a in answers if a.strip()]
    return clean_user in valid_answers

# 指定範囲のシャッフルリストをシード値から計算するヘルパー関数
def get_shuffled_questions(s_id: int, e_id: int, seed: int):
    sub_df = df_raw_quiz[(df_raw_quiz["q_id"] >= s_id) & (df_raw_quiz["q_id"] <= e_id)]
    if sub_df.empty:
        return []
    return sub_df.sample(frac=1, random_state=seed)["q_id"].tolist()

# q_start_id カラムにエンコードされた (start_id, seed) をパースするヘルパー関数
def encode_start_and_seed(s_id: int, seed: int) -> int:
    # 例: s_id=1, seed=123456 -> 10000000001 + (seed % 1000000)*10
    # 簡易的に [100万 * s_id + (seed % 100万)] の整数として格納
    return s_id * 1000000 + (seed % 1000000)

def decode_start_and_seed(encoded_val: int, default_start: int):
    if not encoded_val or encoded_val < 1000000:
        return encoded_val if encoded_val else default_start, 42
    s_id = encoded_val // 1000000
    seed = encoded_val % 1000000
    return s_id, seed

# --------------------------------------------------
# キャラアイコン読み込み
# --------------------------------------------------
available_icons = {}
valid_extensions = (".png", ".jpg", ".jpeg", ".webp")
for filename in sorted(os.listdir(".")):
    if filename.lower().endswith(valid_extensions) and not filename.lower().startswith("bg"):
        display_name = os.path.splitext(filename)[0]
        b64 = get_base64_image(filename)
        ext = filename.split(".")[-1].lower()
        if ext == "jpg":
            ext = "jpeg"
        available_icons[display_name] = f"data:image/{ext};base64,{b64}"

if not available_icons:
    available_icons = {"キャラ01": "🐶", "キャラ02": "🐱", "キャラ03": "🦊", "キャラ04": "🤖"}

def render_icon_html(icon_value: str, size: int = 70) -> str:
    if icon_value.startswith("data:image"):
        return f'<img src="{icon_value}" width="{size}" height="{size}" style="border-radius: 50%; vertical-align: middle; margin-right: 12px; border: 3px solid rgba(255,255,255,0.9); background-color: rgba(0,0,0,0.4); padding: 2px; filter: drop-shadow(0px 4px 8px rgba(0,0,0,0.8)); object-fit: contain;">'
    return f'<span style="font-size: {size}px; vertical-align: middle; margin-right: 12px;">{icon_value}</span>'

# --------------------------------------------------
# サイドバー: 役割選択
# --------------------------------------------------
st.sidebar.title("🎮 クイズシステム")
role = st.sidebar.radio("役割を選択してください", ["👤 プレイヤー（参加者）", "👑 オーナー（管理者）"])

min_q_id = int(df_raw_quiz["q_id"].min())
max_q_id = int(df_raw_quiz["q_id"].max())

# --------------------------------------------------
# オーナー（管理者）画面
# --------------------------------------------------
if role == "👑 オーナー（管理者）":
    st.title("👑 オーナー管理画面")
    
    password = st.sidebar.text_input("管理者パスワード", type="password")
    owner_pass = st.secrets.get("owner", {}).get("password", "admin")
    
    if password != owner_pass:
        st.warning("正しいパスワードを入力してください。")
        st.stop()
        
    st.success("管理者として認証されました。")
    st.subheader("⚙️ ルームコントロール")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        room_code = st.text_input("ルームコード", value="ROOM1")
    with col2:
        q_start = st.number_input("開始問題ID", min_value=min_q_id, max_value=max_q_id, value=min_q_id)
    with col3:
        q_end = st.number_input("終了問題ID", min_value=min_q_id, max_value=max_q_id, value=min_q_id + 9 if min_q_id + 9 <= max_q_id else max_q_id)
        
    btn_col1, btn_col2 = st.columns([2, 1])
    with btn_col1:
        if st.button("🚀 ルームを作成 / 初期化する（指定範囲でシャッフル）", type="primary"):
            s_id = min(int(q_start), int(q_end))
            e_id = max(int(q_start), int(q_end))
            new_seed = int(time.time())
            
            # DBのq_start_idに (s_id と seed) をまとめてエンコード保存することで全端末共通化
            encoded_val = encode_start_and_seed(s_id, new_seed)
            
            existing_room = safe_execute(supabase.table("rooms").select("room_code").eq("room_code", room_code)).data
            
            room_payload = {
                "room_code": room_code,
                "status": "waiting",
                "current_question_id": 0,
                "q_start_id": encoded_val,
                "q_end_id": e_id
            }
            
            if existing_room:
                safe_execute(supabase.table("rooms").update(room_payload).eq("room_code", room_code))
            else:
                safe_execute(supabase.table("rooms").insert(room_payload))
            
            safe_execute(supabase.table("players").delete().eq("room_code", room_code))
            
            sub_q = get_shuffled_questions(s_id, e_id, new_seed)
            st.success(f"ルーム `{room_code}` を初期化しました！ 問題ID {s_id}〜{e_id} の全 {len(sub_q)} 問をシャッフルしました。")
            st.rerun()

    with btn_col2:
        if st.button("🗑️ 参加者データのみクリア"):
            safe_execute(supabase.table("players").delete().eq("room_code", room_code))
            st.success("参加者データをクリアしました。")
            st.rerun()
        
    st.divider()
    
    room_res = safe_execute(supabase.table("rooms").select("*").eq("room_code", room_code))
    
    if room_res.data:
        room_data = room_res.data[0]
        current_status = room_data.get("status", "waiting")
        current_idx = int(room_data.get("current_question_id", 0))
        
        raw_start_val = room_data.get("q_start_id", min_q_id)
        s_id, seed = decode_start_and_seed(int(raw_start_val) if raw_start_val else min_q_id, min_q_id)
        e_id = int(room_data.get("q_end_id", max_q_id))
        
        question_order = get_shuffled_questions(s_id, e_id, seed)
        
        total_q = len(question_order)
        
        if total_q > 0 and current_idx < total_q:
            real_q_id = question_order[current_idx]
            q_row = df_raw_quiz[df_raw_quiz["q_id"] == real_q_id]
            current_question = q_row.iloc[0]["question"] if not q_row.empty else ""
            current_answer = q_row.iloc[0]["answer"] if not q_row.empty else ""
        else:
            real_q_id = "-"
            current_question = "出題可能な問題がありません"
            current_answer = ""
        
        st.markdown(f"**ステータス**: `{current_status}` | **進行状況**: {current_idx + 1} / {total_q} 問目 (出題中の問題ID: `{real_q_id}`)")
        
        if current_status == "waiting":
            st.warning("⏳ 参加者待機中です。「📢 クイズを出題」を押すとプレイヤー画面に出題されます。")
        elif current_status == "answer":
            st.info(f"❓ **現在の問題 ({current_idx + 1}/{total_q}問目):**\n\n### {current_question}\n\n💡 **正解:** **【 {current_answer} 】**")
        else:
            st.info(f"❓ **現在の問題 ({current_idx + 1}/{total_q}問目):**\n\n### {current_question}\n\n🔒 *(正解は「正答発表」を押すと表示されます)*")
        
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1:
            if st.button("📢 クイズを出題（進行中）"):
                safe_execute(supabase.table("players").update({"last_answer": ""}).eq("room_code", room_code))
                safe_execute(supabase.table("rooms").update({"status": "question"}).eq("room_code", room_code))
                st.rerun()
                
        with col_btn2:
            if st.button("⭕ 正答発表"):
                safe_execute(supabase.table("rooms").update({"status": "answer"}).eq("room_code", room_code))
                st.rerun()
                
        with col_btn3:
            if st.button("➡️ 次の問題へ"):
                next_idx = current_idx + 1
                if next_idx >= total_q:
                    safe_execute(supabase.table("rooms").update({"status": "finished"}).eq("room_code", room_code))
                else:
                    safe_execute(supabase.table("players").update({"last_answer": ""}).eq("room_code", room_code))
                    safe_execute(supabase.table("rooms").update({
                        "status": "question",
                        "current_question_id": next_idx
                    }).eq("room_code", room_code))
                st.rerun()
                
        if st.button("🏆 最終結果画面を表示"):
            safe_execute(supabase.table("rooms").update({"status": "finished"}).eq("room_code", room_code))
            st.rerun()
            
        st.divider()
        st.subheader("📊 参加者一覧と回答リアルタイム状況")
        
        players_res = safe_execute(supabase.table("players").select("player_name, last_answer, score, combo").eq("room_code", room_code).order("score", desc=True))
        if players_res.data:
            df_players = pd.DataFrame(players_res.data)
            
            def judge_answer(ans):
                if not ans or str(ans).strip() == "":
                    return "-"
                return "⭕ 正解" if check_is_correct(str(ans), current_answer) else "❌ 不正解"

            df_players["判定"] = df_players["last_answer"].apply(judge_answer)
            
            df_display = df_players[["player_name", "last_answer", "判定", "score", "combo"]].rename(columns={
                "player_name": "プレイヤー名",
                "last_answer": "送信された回答",
                "score": "現在のスコア",
                "combo": "コンボ数"
            })
            
            st.dataframe(df_display, use_container_width=True)
        else:
            st.info("現在参加者はいません。")
            
    time.sleep(1)
    st.rerun()

# --------------------------------------------------
# プレイヤー（参加者）画面
# --------------------------------------------------
else:
    st.title("👤 プレイヤースタンド")
    
    if "joined" not in st.session_state:
        st.session_state.joined = False
    if "player_name" not in st.session_state:
        st.session_state.player_name = ""
    if "room_code" not in st.session_state:
        st.session_state.room_code = "ROOM1"
    if "icon" not in st.session_state:
        st.session_state.icon = list(available_icons.values())[0]
    if "last_processed_idx" not in st.session_state:
        st.session_state.last_processed_idx = None
    if "submitted" not in st.session_state:
        st.session_state.submitted = False
        
    if not st.session_state.joined:
        st.subheader("参加情報の入力")
        c1, c2 = st.columns(2)
        with c1:
            st.session_state.room_code = st.text_input("ルームコード", value=st.session_state.room_code)
            st.session_state.player_name = st.text_input("プレイヤー名（必須）")
        with c2:
            selected_icon_key = st.selectbox("アイコンを選択", list(available_icons.keys()))
            st.session_state.icon = available_icons[selected_icon_key]
            st.markdown(f"選択中: {render_icon_html(st.session_state.icon, 80)}", unsafe_allow_html=True)
            
        if st.button("🎮 参加する", type="primary"):
            p_name = st.session_state.player_name.strip()
            r_code = st.session_state.room_code.strip()
            
            if not p_name:
                st.error("プレイヤー名を入力してください。")
            else:
                check_res = safe_execute(supabase.table("players").select("player_name").eq("room_code", r_code).eq("player_name", p_name))
                
                player_payload = {
                    "room_code": r_code,
                    "player_name": p_name,
                    "icon": st.session_state.icon,
                    "score": 0,
                    "combo": 0,
                    "last_answer": ""
                }
                
                if check_res.data:
                    safe_execute(supabase.table("players").update(player_payload).eq("room_code", r_code).eq("player_name", p_name))
                else:
                    safe_execute(supabase.table("players").insert(player_payload))
                    
                st.session_state.joined = True
                st.rerun()
    else:
        room_code = st.session_state.room_code
        room_res = safe_execute(supabase.table("rooms").select("*").eq("room_code", room_code))
        
        if not room_res.data:
            st.error("指定されたルームコードが存在しません。")
            if st.button("退出する"):
                st.session_state.joined = False
                st.rerun()
            st.stop()
            
        room_data = room_res.data[0]
        status = room_data.get("status", "waiting")
        current_idx = int(room_data.get("current_question_id", 0))
        
        raw_start_val = room_data.get("q_start_id", min_q_id)
        s_id, seed = decode_start_and_seed(int(raw_start_val) if raw_start_val else min_q_id, min_q_id)
        e_id = int(room_data.get("q_end_id", max_q_id))
        
        question_order = get_shuffled_questions(s_id, e_id, seed)
        
        if st.session_state.last_processed_idx != current_idx:
            st.session_state.submitted = False
            st.session_state.last_processed_idx = current_idx
        
        icon_html = render_icon_html(st.session_state.icon, 64)
        st.markdown(f"### {icon_html} **{st.session_state.player_name}** さんの画面 (ルーム: `{room_code}`)", unsafe_allow_html=True)
        
        if status == "waiting":
            st.info("⏳ オーナーがクイズを開始するのを待っています...")
            time.sleep(1)
            st.rerun()
            
        elif status == "question":
            if question_order and current_idx < len(question_order):
                real_q_id = question_order[current_idx]
                q_row = df_raw_quiz[df_raw_quiz["q_id"] == real_q_id]
                
                if not q_row.empty:
                    q_text = q_row.iloc[0]["question"]
                    correct_ans = str(q_row.iloc[0]["answer"]).strip()
                    
                    st.subheader(f"❓ 第 {current_idx + 1} 問")
                    st.markdown(f"#### {q_text}")
                    
                    user_input = st.text_input(
                        "回答を入力してください",
                        key=f"input_{current_idx}",
                        disabled=st.session_state.submitted
                    )
                    
                    if not st.session_state.submitted:
                        if st.button("解答を送信", type="primary"):
                            if not user_input.strip():
                                st.error("回答を入力してください。")
                            else:
                                p_res = safe_execute(supabase.table("players").select("score, combo").eq("room_code", room_code).eq("player_name", st.session_state.player_name))
                                if p_res.data:
                                    p_data = p_res.data[0]
                                    current_score = p_data.get("score", 0)
                                    current_combo = p_data.get("combo", 0)
                                    
                                    is_correct = check_is_correct(user_input, correct_ans)
                                    
                                    if is_correct:
                                        new_combo = current_combo + 1
                                        add_score = 100 + (new_combo - 1) * 20
                                        new_score = current_score + add_score
                                    else:
                                        new_combo = 0
                                        new_score = current_score
                                        
                                    safe_execute(supabase.table("players").update({
                                        "score": new_score,
                                        "combo": new_combo,
                                        "last_answer": user_input.strip()
                                    }).eq("room_code", room_code).eq("player_name", st.session_state.player_name))
                                    
                                    st.session_state.submitted = True
                                    st.rerun()
                    else:
                        st.success("✅ 回答を送信しました！正答発表をお待ちください。")
            
            time.sleep(1)
            st.rerun()
            
        elif status == "answer":
            if question_order and current_idx < len(question_order):
                real_q_id = question_order[current_idx]
                q_row = df_raw_quiz[df_raw_quiz["q_id"] == real_q_id]
                
                if not q_row.empty:
                    correct_ans = q_row.iloc[0]["answer"]
                    st.subheader(f"⭕ 第 {current_idx + 1} 問 の正解発表")
                    st.success(f"正解は **【 {correct_ans} 】** でした！")
                    
                    p_res = safe_execute(supabase.table("players").select("score, combo, last_answer").eq("room_code", room_code).eq("player_name", st.session_state.player_name))
                    if p_res.data:
                        p = p_res.data[0]
                        user_ans = p.get("last_answer", "")
                        
                        if check_is_correct(user_ans, correct_ans):
                            st.balloons()
                            st.markdown(f"🎉 **正解！** あなたの回答: `{user_ans}`")
                        else:
                            st.markdown(f"❌ **不正解...** あなたの回答: `{user_ans if user_ans else '未回答'}`")
                            
                        st.markdown(f"現在のスコア: **{p.get('score', 0)} pt** | コンボ: **{p.get('combo', 0)}**")
            
            time.sleep(1)
            st.rerun()
            
        elif status == "finished":
            st.title("🏆 最終結果発表 🏆")
            
            players_res = safe_execute(supabase.table("players").select("icon, player_name, score, combo").eq("room_code", room_code).order("score", desc=True))
            players_data = players_res.data
            
            if players_data:
                for idx, player in enumerate(players_data, 1):
                    rank_emoji = "🥇 1位" if idx == 1 else ("🥈 2位" if idx == 2 else ("🥉 3位" if idx == 3 else f"第 {idx} 位"))
                    
                    icon = player.get("icon", "")
                    name = player.get("player_name", "名無し")
                    score = player.get("score", 0)
                    combo = player.get("combo", 0)
                    
                    p_icon_html = render_icon_html(icon, 80)
                    st.markdown(f"### {rank_emoji} : {p_icon_html} **{name}** — `{score}` pt (最大コンボ: {combo})", unsafe_allow_html=True)
                    st.divider()
            else:
                st.info("参加者がいません。")
                
            if st.button("最初に戻る"):
                st.session_state.joined = False
                st.session_state.submitted = False
                st.session_state.last_processed_idx = None
                st.rerun()