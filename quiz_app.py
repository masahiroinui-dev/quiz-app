import streamlit as st
from supabase import create_client, Client
import pandas as pd
import time
import base64
import os

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

# 視認性CSS（ダーク透過＋高透過率＋白文字）
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

    /* 入力フィールド全般（ダーク透過化強固指定） */
    div[data-baseweb="input"],
    div[data-baseweb="input"] > div,
    div[data-baseweb="base-input"],
    div[data-baseweb="select"],
    div[data-baseweb="select"] > div {
        background-color: rgba(15, 18, 30, 0.75) !important;
        border-radius: 8px !important;
        border: 1px solid rgba(255, 255, 255, 0.4) !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.6) !important;
    }

    input, select, textarea, div[data-baseweb="select"] span {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        text-shadow: none !important;
        font-weight: bold !important;
        background-color: transparent !important;
    }

    button[aria-label="Increase value"], button[aria-label="Decrease value"] {
        background-color: transparent !important;
        color: #ffffff !important;
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
def get_quiz_data():
    csv_file = "questions.csv"
    
    if os.path.exists(csv_file):
        try:
            df = pd.read_csv(csv_file, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(csv_file, encoding="shift-jis")
            
        df["id"] = range(1, len(df) + 1)
        return df
    else:
        st.error(f"クイズファイル `{csv_file}` が見つかりません。")
        st.stop()

df_quiz = get_quiz_data()

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
        q_start = st.number_input("開始問題ID", min_value=1, max_value=len(df_quiz), value=1)
    with col3:
        q_end = st.number_input("終了問題ID", min_value=1, max_value=len(df_quiz), value=len(df_quiz))
        
    btn_col1, btn_col2 = st.columns([2, 1])
    with btn_col1:
        if st.button("🚀 ルームを作成 / 初期化する（参加者データも消去）", type="primary"):
            st.cache_data.clear()
            safe_execute(supabase.table("rooms").upsert({
                "room_code": room_code,
                "status": "waiting",
                "current_question_id": int(q_start),
                "q_start_id": int(q_start),
                "q_end_id": int(q_end)
            }, on_conflict="room_code"))
            safe_execute(supabase.table("players").delete().eq("room_code", room_code))
            st.success(f"ルーム `{room_code}` と参加者データを初期化しました！（開始ID: {q_start} / 終了ID: {q_end}）")
            
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
        current_q_id = int(room_data.get("current_question_id", q_start))
        
        q_row = df_quiz[df_quiz["id"] == current_q_id]
        current_question = q_row.iloc[0]["question"] if not q_row.empty else "問題データがありません"
        current_answer = q_row.iloc[0]["answer"] if not q_row.empty else ""
        
        st.markdown(f"**現在のステータス**: `{current_status}` | **現在出題中の問題番号**: 第 `{current_q_id}` 問")
        
        # オーナー用 出題テキストの表示エリア
        st.info(f"❓ **出題中の問題 (第 {current_q_id} 問):**\n\n### {current_question}\n\n💡 **正解:** **【 {current_answer} 】**")
        
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
                next_id = current_q_id + 1
                max_end_id = int(room_data.get("q_end_id", q_end))
                
                if next_id > max_end_id:
                    safe_execute(supabase.table("rooms").update({"status": "finished"}).eq("room_code", room_code))
                else:
                    safe_execute(supabase.table("players").update({"last_answer": ""}).eq("room_code", room_code))
                    safe_execute(supabase.table("rooms").update({
                        "status": "question",
                        "current_question_id": next_id
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
                return "⭕ 正解" if str(ans).strip() == str(current_answer).strip() else "❌ 不正解"

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
            
    time.sleep(1)  # 待ち時間を1秒に短縮
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
            if not st.session_state.player_name.strip():
                st.error("プレイヤー名を入力してください。")
            else:
                query = supabase.table("players").insert({
                    "room_code": st.session_state.room_code,
                    "player_name": st.session_state.player_name,
                    "icon": st.session_state.icon,
                    "score": 0,
                    "combo": 0,
                    "last_answer": ""
                })
                safe_execute(query)
                st.session_state.joined = True
                st.rerun()
    else:
        room_code = st.session_state.room_code
        room_res = safe_execute(supabase.table("rooms").select("status, current_question_id").eq("room_code", room_code))
        
        if not room_res.data:
            st.error("指定されたルームコードが存在しません。")
            if st.button("退出する"):
                st.session_state.joined = False
                st.rerun()
            st.stop()
            
        room_data = room_res.data[0]
        status = room_data.get("status", "waiting")
        current_q_id = int(room_data.get("current_question_id", 1))
        
        icon_html = render_icon_html(st.session_state.icon, 64)
        st.markdown(f"### {icon_html} **{st.session_state.player_name}** さんの画面 (ルーム: `{room_code}`)", unsafe_allow_html=True)
        
        if status == "waiting":
            st.info("⏳ オーナーがクイズを開始するのを待っています...")
            time.sleep(1)
            st.rerun()
            
        elif status == "question":
            q_row = df_quiz[df_quiz["id"] == current_q_id]
            if not q_row.empty:
                q_text = q_row.iloc[0]["question"]
                correct_ans = q_row.iloc[0]["answer"]
                
                st.subheader(f"❓ 第 {current_q_id} 問")
                st.markdown(f"#### {q_text}")
                
                user_ans = st.text_input("回答を入力してください", key=f"ans_{current_q_id}")
                
                if st.button("解答を送信", type="primary"):
                    p_res = safe_execute(supabase.table("players").select("score, combo").eq("room_code", room_code).eq("player_name", st.session_state.player_name))
                    if p_res.data:
                        p_data = p_res.data[0]
                        current_score = p_data.get("score", 0)
                        current_combo = p_data.get("combo", 0)
                        
                        if user_ans.strip() == correct_ans.strip():
                            new_combo = current_combo + 1
                            add_score = 100 + (new_combo - 1) * 20
                            new_score = current_score + add_score
                            st.success(f"⭕ 送信完了！ (+{add_score}pt / {new_combo}コンボ)")
                        else:
                            new_combo = 0
                            new_score = current_score
                            st.warning("❌ 送信完了！")
                            
                        query = supabase.table("players").update({
                            "score": new_score,
                            "combo": new_combo,
                            "last_answer": user_ans
                        }).eq("room_code", room_code).eq("player_name", st.session_state.player_name)
                        safe_execute(query)
            
            time.sleep(1)  # 待ち時間を1秒に短縮
            st.rerun()
            
        elif status == "answer":
            q_row = df_quiz[df_quiz["id"] == current_q_id]
            if not q_row.empty:
                correct_ans = q_row.iloc[0]["answer"]
                st.subheader(f"⭕ 第 {current_q_id} 問 の正解発表")
                st.success(f"正解は **【 {correct_ans} 】** でした！")
                
                p_res = safe_execute(supabase.table("players").select("score, combo").eq("room_code", room_code).eq("player_name", st.session_state.player_name))
                if p_res.data:
                    p = p_res.data[0]
                    st.markdown(f"現在のスコア: **{p.get('score', 0)} pt** | コンボ: **{p.get('combo', 0)}**")
            
            time.sleep(1)  # 待ち時間を1秒に短縮
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
                st.rerun()