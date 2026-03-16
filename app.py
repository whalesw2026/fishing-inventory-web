import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from io import BytesIO
import time

# --- 配置页面 ---
st.set_page_config(page_title="🎣 渔具多仓库库存管理系统 (Web版)", layout="wide", page_icon="🎣")


# --- 缓存管理 (增加 clear 机制) ---
@st.cache_data(ttl=60)
def load_data_cached(token, repo_name, file_path, _force_refresh=False):
    if not token or not repo_name:
        return pd.DataFrame()

    # 强制刷新时添加时间戳打破缓存
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
        df = df[required_cols]
        return df
    except Exception as e:
        st.error(f"读取CSV失败: {e}")
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
        # 强制刷新时清除缓存
        if force_refresh:
            load_data_cached.clear()
        return load_data_cached(self.token, self.repo_name, self.file_path, force_refresh)

    def save_data(self, df, max_retries=3):
        if not self.token or not self.repo_name:
            return False, "❌ 未配置 GitHub Token 或 仓库名"

        from github import Github, Auth
        from github.GithubException import GithubException

        attempt = 0
        last_error = ""

        while attempt < max_retries:
            try:
                auth = Auth.Token(self.token)
                g = Github(auth=auth)
                repo = g.get_repo(self.repo_name)

                csv_buffer = BytesIO()
                required_cols = ['id', 'warehouse', 'brand', 'item', 'quantity', 'image', 'updated_at']

                for col in required_cols:
                    if col not in df.columns:
                        if col == 'id':
                            df[col] = range(1, len(df) + 1)
                        elif col == 'quantity':
                            df[col] = 0
                        else:
                            df[col] = ""

                df = df[required_cols]
                # 显式指定 encoding 和 index
                df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                content = csv_buffer.getvalue()

                sha = None
                file_exists = True
                try:
                    contents = repo.get_contents(self.file_path, ref="main")
                    sha = contents.sha
                except Exception as e:
                    file_exists = False
                    last_error = f"获取文件SHA失败: {e}"

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

                # 成功后强制清除缓存
                load_data_cached.clear()
                return True, "✅ 保存成功！"

            except GithubException as e:
                last_error = f"GitHub API 错误 ({e.status}): {str(e)}"
                if e.status == 409 and "does not match" in str(e):
                    attempt += 1
                    if attempt < max_retries:
                        time.sleep(0.5)
                        continue
                    else:
                        return False, f"💥 冲突失败：重试 {max_retries} 次后仍冲突。{last_error}"
                else:
                    return False, last_error
            except Exception as e:
                last_error = f"💥 未知严重错误：{type(e).__name__} - {str(e)}"
                # 遇到未知错误直接返回，不重试，以便用户看到具体错误
                return False, last_error

        return False, f"💥 循环结束仍未成功。最后错误：{last_error}"

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

    current_warehouse = st.radio("选择当前查看的仓库:", warehouses, index=1)  # 默认选猎鳜方便测试

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

    st.dataframe(df_view, width="stretch", hide_index=True)

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
                    st.info("💡 请检查上方红色报错信息。如果是 409 冲突，已自动重试；如果是其他错误，需手动解决。")


def render_update_qty():
    st.header("✏️ 修改数量")
    if not db.token: st.stop()
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
            df = db.load_data(force_refresh=True)
            mask_src = (df['brand'] == b) & (df['item'] == i) & (df['warehouse'] == src_wh)

            if not df[mask_src].empty and df.loc[mask_src, 'quantity'].values[0] >= qty:
                df.loc[mask_src, 'quantity'] -= qty
                if df.loc[mask_src, 'quantity'].values[0] <= 0:
                    df = df[~mask_src]

                mask_dst = (df['brand'] == b) & (df['item'] == i) & (df['warehouse'] == dst_wh)
                if df[mask_dst].empty:
                    new_id = int(df['id'].max()) + 1 if not df.empty and 'id' in df.columns else 1
                    new_row = pd.DataFrame([{
                        'id': new_id, 'warehouse': dst_wh, 'brand': b, 'item': i,
                        'quantity': qty, 'image': '', 'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }])
                    df = pd.concat([df, new_row], ignore_index=True)
                else:
                    df.loc[mask_dst, 'quantity'] += qty
                    df.loc[mask_dst, 'updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                success, err = db.save_data(df)
                if success:
                    st.success(f"调拨成功：{qty} 件 {b}-{i} -> {dst_wh}")
                    db.add_history("调拨", f"{qty}件 {b}-{i}: {src_wh}->{dst_wh}")
                    st.rerun()
                else:
                    st.error(err)
            else:
                st.error("库存不足或物品不存在。")
                st.rerun()


def render_delete():
    st.header("❌ 删除物品 (调试模式)")
    if not db.token:
        st.stop()

    st.info(f"🔍 当前操作仓库：**{current_warehouse}**")

    # 1. 强制刷新获取最新数据
    df = db.load_data(force_refresh=True)

    if df.empty:
        st.warning("整个库存表为空！")
        return

    df_wh = df[df['warehouse'] == current_warehouse]

    if df_wh.empty:
        st.warning(f"⚠️ **{current_warehouse}** 仓库目前没有数据。")
        st.write("当前表中所有仓库列表:", df['warehouse'].unique())
        return

    # 2. 生成选项
    options = [f"{row['brand']} - {row['item']} (数量: {row['quantity']})" for _, row in df_wh.iterrows()]

    if not options:
        st.warning("解析后的选项列表为空。")
        return

    sel = st.selectbox("选择要删除的记录", options, key="del_sel")

    if sel:
        st.write(f"🎯 准备删除：**{sel}**")

        if st.button("🔴 确认删除并强制同步", type="primary", key="del_btn"):
            parts = sel.split(" (数量: ")
            if len(parts) != 2:
                st.error("❌ 无法解析选项格式。")
                return

            b_i_part = parts[0].split(" - ")
            if len(b_i_part) != 2:
                st.error("❌ 无法解析品牌/物品名称。")
                return

            b, i = b_i_part[0].strip(), b_i_part[1].strip()

            st.write(f"正在查找匹配项 -> 品牌:`{b}`, 物品:`{i}`, 仓库:`{current_warehouse}`...")

            # 3. 再次强制刷新，确保基于最新状态操作
            df = db.load_data(force_refresh=True)
            mask = (df['brand'] == b) & (df['item'] == i) & (df['warehouse'] == current_warehouse)

            matched_count = df[mask].shape[0]
            st.write(f"找到匹配行数：{matched_count}")

            if matched_count > 0:
                # 显示即将被删除的数据预览
                st.write("即将删除的数据行：")
                st.dataframe(df[mask], width="stretch")

                # 执行删除
                df_new = df[~mask]
                st.write(f"删除后剩余总行数：{len(df_new)} (原:{len(df)})")

                # 4. 保存
                with st.spinner("正在提交到 GitHub..."):
                    success, err = db.save_data(df_new)

                if success:
                    st.success("✅ **删除成功！** 正在刷新页面...")
                    db.add_history("删除", f"{b}-{i} from {current_warehouse}")
                    # 强制清除缓存并刷新
                    load_data_cached.clear()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"💥 **保存失败！** 请查看下方详细错误：")
                    st.code(err)
                    st.info("💡 如果看到 409 错误，说明有冲突，代码已自动重试。如果看到其他错误，请截图反馈。")
            else:
                st.warning("⚠️ 在最新数据中未找到该物品。可能已经被其他人删除了。")
                st.rerun()


def render_import_excel():
    st.header("📥 Excel 导入")
    uploaded = st.file_uploader("上传 Excel", type=['xlsx', 'xls'], key="imp_file")
    target_wh = st.selectbox("导入到", get_default_warehouses(), key="imp_wh")

    if uploaded:
        try:
            df_in = pd.read_excel(uploaded)
            if not all(k in df_in.columns for k in ['品牌', '物品', '数量']):
                st.error("缺少列：品牌，物品，数量")
                st.stop()

            df_in = df_in.rename(columns={'品牌': 'brand', '物品': 'item', '数量': 'quantity', '图片路径': 'image'})
            df_in['warehouse'] = target_wh
            df_in['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if 'image' not in df_in.columns: df_in['image'] = ""

            df_curr = db.load_data(force_refresh=True)
            count_add, count_upd = 0, 0

            for _, row in df_in.iterrows():
                mask = (df_curr['brand'] == row['brand']) & (df_curr['item'] == row['item']) & (
                            df_curr['warehouse'] == target_wh)
                if df_curr[mask].empty:
                    new_id = int(df_curr['id'].max()) + 1 if not df_curr.empty and 'id' in df_curr.columns else 1
                    new_row = pd.DataFrame([{
                        'id': new_id, 'warehouse': target_wh, 'brand': row['brand'], 'item': row['item'],
                        'quantity': int(row['quantity']), 'image': row.get('image', ''),
                        'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }])
                    df_curr = pd.concat([df_curr, new_row], ignore_index=True)
                    count_add += 1
                else:
                    df_curr.loc[mask, 'quantity'] += int(row['quantity'])
                    df_curr.loc[mask, 'updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    count_upd += 1

            success, err = db.save_data(df_curr)
            if success:
                st.success(f"导入完成：新增 {count_add}, 更新 {count_upd}")
                db.add_history("导入", f"{uploaded.name}: +{count_add}, ~{count_upd}")
                st.rerun()
            else:
                st.error(err)
        except Exception as e:
            st.error(f"读取失败：{e}")


def render_export_excel():
    st.header("📤 Excel 导出")
    df = db.load_data()
    if df.empty: st.warning("无数据"); return

    export_df = df[['warehouse', 'brand', 'item', 'quantity', 'image']].copy()
    export_df.columns = ['仓库', '品牌', '物品', '数量', '图片路径']

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        export_df.to_excel(writer, index=False)

    st.download_button("下载 Excel", buffer.getvalue(), f"inventory_{datetime.now().strftime('%Y%m%d')}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_btn")


def render_history():
    st.header("📝 修改历史")
    history = db.get_history()
    if not history:
        st.info("暂无记录")
    else:
        for r in reversed(history[-20:]):
            st.markdown(f"**[{r['timestamp']}] {r['action']}**: {r['details']}")
            st.divider()


def render_status():
    st.header("🔧 系统状态")
    if db.token:
        st.success("✅ Token 已配置")
        st.success(f"✅ 仓库：{db.repo_name}")
        if st.button("强制刷新数据缓存"):
            load_data_cached.clear()
            st.rerun()
        df = db.load_data()
        st.metric("记录数", len(df))
        st.write("所有仓库列表:", df['warehouse'].unique())
    else:
        st.error("❌ 未配置 Token")


# --- 路由 ---
if choice == "📦 库存总览":
    tab1, tab2 = st.tabs(["当前仓库", "全仓汇总"])
    with tab1:
        render_inventory_view(db.load_data(), current_warehouse, False)
    with tab2:
        render_inventory_view(db.load_data(), "", True)
elif choice == "➕ 新增/入库":
    render_add_item()
elif choice == "✏️ 修改数量":
    render_update_qty()
elif choice == "🔄 跨仓调拨":
    render_transfer()
elif choice == "❌ 删除物品":
    render_delete()
elif choice == "📥 Excel导入":
    render_import_excel()
elif choice == "📤 Excel导出":
    render_export_excel()
elif choice == "📝 修改历史":
    render_history()
elif choice == "🔧 系统状态":
    render_status()