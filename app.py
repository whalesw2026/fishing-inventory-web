import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from io import BytesIO
import time

# --- 配置页面 ---
st.set_page_config(page_title="🎣 渔具多仓库库存管理系统 (Web版)", layout="wide", page_icon="🎣")


# --- 缓存管理 ---
@st.cache_data(ttl=60)
def load_data_cached(token, repo_name, file_path, _force_refresh=False):
    """
    加载数据。_force_refresh 用于强制绕过缓存重新请求（通过添加时间戳参数实现）
    """
    if not token or not repo_name:
        return pd.DataFrame()

    # 添加随机数防止浏览器缓存 CSV
    ts = datetime.now().timestamp() if _force_refresh else 0
    url = f"https://raw.githubusercontent.com/{repo_name}/main/{file_path}?t={ts}"

    try:
        df = pd.read_csv(url)
        required_cols = ['id', 'warehouse', 'brand', 'item', 'quantity', 'image', 'updated_at']
        for col in required_cols:
            if col not in df.columns:
                if col == 'id':
                    df[col] = range(1, len(df) + 1)
                elif col == 'quantity':
                    df[col] = 0
                else:
                    df[col] = ""
        # 确保列顺序
        df = df[required_cols]
        return df
    except Exception as e:
        # 如果文件不存在，返回空结构
        return pd.DataFrame(columns=['id', 'warehouse', 'brand', 'item', 'quantity', 'image', 'updated_at'])


class GitHubDB:
    def __init__(self):
        self.token = st.secrets.get("GITHUB_TOKEN", "")
        self.repo_name = st.secrets.get("GITHUB_REPO", "")
        self.file_path = "inventory.csv"
        self.history_file = "modification_history.json"

        if not os.path.exists(self.history_file):
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump([], f)

    def load_data(self, force_refresh=False):
        return load_data_cached(self.token, self.repo_name, self.file_path, force_refresh)

    def save_data(self, df, max_retries=3):
        """
        保存数据到 GitHub，包含自动冲突重试机制
        """
        if not self.token or not self.repo_name:
            return False, "❌ 未配置 GitHub Token 或 仓库名"

        from github import Github, Auth
        from github.GithubException import GithubException

        attempt = 0
        while attempt < max_retries:
            try:
                auth = Auth.Token(self.token)
                g = Github(auth=auth)
                repo = g.get_repo(self.repo_name)

                # 1. 准备数据
                csv_buffer = BytesIO()
                required_cols = ['id', 'warehouse', 'brand', 'item', 'quantity', 'image', 'updated_at']

                # 确保列完整
                for col in required_cols:
                    if col not in df.columns:
                        if col == 'id':
                            df[col] = range(1, len(df) + 1)
                        elif col == 'quantity':
                            df[col] = 0
                        else:
                            df[col] = ""

                df = df[required_cols]
                df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                content = csv_buffer.getvalue()

                # 2. 获取当前最新的 SHA
                sha = None
                file_exists = True
                try:
                    contents = repo.get_contents(self.file_path, ref="main")
                    sha = contents.sha
                except Exception:
                    file_exists = False

                # 3. 尝试提交
                msg_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                if file_exists:
                    repo.update_file(
                        path=self.file_path,
                        message=f"Update: {msg_time}",
                        content=content,
                        sha=sha,
                        branch="main"
                    )
                else:
                    repo.create_file(
                        path=self.file_path,
                        message=f"Create: {msg_time}",
                        content=content,
                        branch="main"
                    )

                # 成功！清除缓存
                load_data_cached.clear()
                return True, "✅ 保存成功！"

            except GithubException as e:
                if e.status == 409 and "does not match" in str(e):
                    # 发生冲突 (409)
                    attempt += 1
                    if attempt < max_retries:
                        # 等待一小会儿，然后重试循环会自动重新获取最新 SHA
                        time.sleep(0.5)
                        continue
                    else:
                        return False, f"💥 冲突失败：经过 {max_retries} 次重试仍无法解决冲突。可能有人正在频繁修改。请刷新页面后重试。"
                else:
                    # 其他错误直接返回
                    return False, f"💥 GitHub 错误 ({e.status}): {str(e)}"
            except Exception as e:
                return False, f"💥 未知错误：{type(e).__name__} - {str(e)}"

        return False, "💥 未知循环错误"

    def add_history(self, action, details):
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            history.append(
                {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "action": action, "details": details})
            if len(history) > 100: history = history[-100:]
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=4)
        except:
            pass

    def get_history(self):
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []


db = GitHubDB()


# --- 辅助函数 ---
def get_default_brands():
    return ["阿布", "bkk", "蓝旗鱼", "达瓦", "ewe", "霖胜", "绫罗", "贝库曼", "名魔", "大河之路", "黑坑"]


def get_default_items():
    return ["软饵", "亮片", "假饵", "内德", "面罩", "盒装鱼钩", "虾", "小包钩", "帆布包",
            "9050铅头钩", "王道", "帽子", "pe线", "子线付", "T恤", "vib", "束杆带",
            "主线付", "米诺", "8003钩", "口罩", "银刀", "控鱼器", "毛巾", "鬼飞2代",
            "美夏t尾", "毒眼", "挂件", "邪道铁板", "硬饵", "长袖T恤", "钓鱼帽", "鸦语钢弹", "手缠带"]


def get_default_warehouses():
    return ["破龟人", "猎鳜", "星程", "淡定"]


# --- 侧边栏 ---
with st.sidebar:
    st.header("🏬 仓库选择")
    warehouses = get_default_warehouses()
    if not db.token:
        st.error("⚠️ 请先配置 Secrets")

    current_warehouse = st.radio("选择当前查看的仓库:", warehouses, index=0)

    st.divider()
    st.header("🛠️ 功能菜单")
    menu = ["📦 库存总览", "➕ 新增/入库", "✏️ 修改数量", "🔄 跨仓调拨", "❌ 删除物品",
            "📥 Excel导入", "📤 Excel导出", "📝 修改历史", "🔧 系统状态"]
    choice = st.radio("导航", menu, label_visibility="collapsed")


# --- 主界面逻辑 ---

def render_inventory_view(df, warehouse, show_all=False):
    title = '🌍 全仓汇总' if show_all else f'📦 {warehouse} 库存总览'
    st.header(title)

    if df.empty:
        st.info("暂无数据。")
        return

    df_view = df[df['warehouse'] == warehouse].copy() if not show_all else df.copy()

    if not show_all and df_view.empty:
        st.warning(f"{warehouse} 暂无库存。")
        return

    if show_all and not df_view.empty:
        df_view['warehouse_list'] = df_view['warehouse']
        agg_df = df_view.groupby(['brand', 'item']).agg({
            'quantity': 'sum',
            'warehouse_list': lambda x: ', '.join(sorted(set(x))),
            'image': 'first'
        }).reset_index()
        agg_df.rename(columns={'warehouse_list': '分布仓库'}, inplace=True)
        df_view = agg_df

    st.dataframe(df_view, use_container_width=True, hide_index=True)

    total_qty = df_view['quantity'].sum()
    st.metric("总数量", f"{total_qty} 件")


def render_add_item():
    st.header("➕ 新增/入库")
    if not db.token:
        st.error("请先配置 GitHub Token。")
        return

    with st.form("add_form"):
        c1, c2 = st.columns(2)
        with c1:
            brand = st.selectbox("品牌", get_default_brands(), index=0, key="add_brand")
            if st.checkbox("输入新品牌", key="cb_brand"):
                brand = st.text_input("新品牌名称", value=brand, key="txt_brand")

            item = st.selectbox("物品名称", get_default_items(), index=0, key="add_item")
            if st.checkbox("输入新物品", key="cb_item"):
                item = st.text_input("新物品名称", value=item, key="txt_item")

            warehouse = st.selectbox("目标仓库", get_default_warehouses(), index=0, key="add_wh")
            quantity = st.number_input("入库数量", min_value=1, value=1, key="add_qty")

        with c2:
            image_path = st.text_input("图片路径 (可选)", placeholder="gear_images/xxx.jpg", key="add_img")

        submitted = st.form_submit_button("💾 确认入库")

        if submitted:
            if not brand or not item:
                st.error("品牌和物品不能为空！")
            else:
                # 每次操作前强制刷新一次数据，确保基于最新版本修改
                df = db.load_data(force_refresh=True)
                mask = (df['brand'] == brand) & (df['item'] == item) & (df['warehouse'] == warehouse)

                if df[mask].empty:
                    new_id = int(df['id'].max()) + 1 if not df.empty and 'id' in df.columns else 1
                    new_row = pd.DataFrame([{
                        'id': new_id, 'warehouse': warehouse, 'brand': brand, 'item': item,
                        'quantity': quantity, 'image': image_path,
                        'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }])
                    df = pd.concat([df, new_row], ignore_index=True)
                    msg = f"新增：{warehouse} - {brand} {item} x {quantity}"
                else:
                    df.loc[mask, 'quantity'] += quantity
                    df.loc[mask, 'updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    msg = f"累加：{warehouse} - {brand} {item} + {quantity}"

                success, err = db.save_data(df)
                if success:
                    st.success(msg)
                    db.add_history("新增/入库", msg)
                    st.rerun()
                else:
                    st.error(err)
                    if "409" in err:
                        st.info("💡 提示：数据冲突已自动重试。如果仍然失败，请点击侧边栏刷新或手动刷新浏览器页面。")


def render_update_qty():
    st.header("✏️ 修改数量")
    if not db.token: st.stop()
    # 强制刷新获取最新数据
    df = db.load_data(force_refresh=True)
    if df.empty: st.warning("无数据"); return

    df_wh = df[df['warehouse'] == current_warehouse]
    if df_wh.empty: st.warning(f"{current_warehouse} 无数据"); return

    options = [f"{row['brand']} - {row['item']} (现有: {row['quantity']})" for _, row in df_wh.iterrows()]
    selected = st.selectbox("选择物品", options, key="upd_sel")

    if selected:
        parts = selected.split(" (现有: ")
        b, i = parts[0].split(" - ")
        current_qty = int(parts[1].replace(")", ""))
        new_qty = st.number_input("新数量", min_value=0, value=current_qty, key="upd_qty")

        if st.button("更新", key="upd_btn"):
            # 再次确保拿到最新数据以防万一
            df = db.load_data(force_refresh=True)
            mask = (df['brand'] == b) & (df['item'] == i) & (df['warehouse'] == current_warehouse)

            if not df[mask].empty:
                df.loc[mask, 'quantity'] = new_qty
                df.loc[mask, 'updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                success, err = db.save_data(df)
                if success:
                    st.success("更新成功")
                    db.add_history("修改数量", f"{b}-{i} -> {new_qty}")
                    st.rerun()
                else:
                    st.error(err)
            else:
                st.warning("物品未找到，可能已被删除。")
                st.rerun()


def render_transfer():
    st.header("🔄 跨仓调拨")
    if not db.token: st.stop()
    df = db.load_data(force_refresh=True)
    if df.empty: st.warning("无数据"); return

    c1, c2 = st.columns(2)
    with c1:
        src_wh = st.selectbox("源仓库", get_default_warehouses(), key="src")
        df_src = df[df['warehouse'] == src_wh]
        src_options = [f"{row['brand']} - {row['item']} (剩: {row['quantity']})" for _, row in
                       df_src.iterrows()] if not df_src.empty else []
        src_sel = st.selectbox("选择物品", src_options, key="sel_src") if src_options else None
    with c2:
        dst_wh = st.selectbox("目标仓库", get_default_warehouses(), key="dst",
                              index=(1 if src_wh != get_default_warehouses()[1] else 0))

    if src_sel and dst_wh != src_wh:
        parts = src_sel.split(" (剩: ")
        b, i = parts[0].split(" - ")
        max_qty = int(parts[1].replace(")", ""))
        qty = st.number_input("数量", min_value=1, max_value=max_qty, value=1, key="trans_qty")

        if st.button("执行调拨", key="trans_btn"):
            df = db.load_data(force_refresh=True)  # 再次刷新
            mask_src = (df['brand'] == b) & (df['item'] == i) & (df['warehouse'] == src_wh)

            if not df[mask_src].empty and df.loc[mask_src, 'quantity'].values[0] >= qty:
                df.loc[mask_src, 'quantity'] -= qty
                if df.loc[mask_src, 'quantity'].values[0] <= 0:
                    df = df[~mask_src]

                mask_dst = (df['brand'] == b) & (df['item'] == i) & (df['warehouse'] == dst_wh)
                if df[mask_dst].empty:
                    new_id = int(df['id'].max()) + 1 if not df.empty and 'id' in df.columns else 1
                    new_row = pd.DataFrame([{
                        'id': new_id, 'warehouse': dst_wh, 'brand':