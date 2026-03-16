import streamlit as st
import pandas as pd
import json
import os
import shutil
from datetime import datetime
import glob
from io import BytesIO

# --- 配置页面 ---
st.set_page_config(page_title="🎣 渔具多仓库库存管理系统 (Web版)", layout="wide", page_icon="🎣")


# --- 模拟数据库类 (基于 GitHub CSV) ---
class GitHubDB:
    def __init__(self):
        self.token = st.secrets.get("GITHUB_TOKEN", "")
        self.repo_name = st.secrets.get("GITHUB_REPO", "")
        self.file_path = "inventory.csv"
        self.history_file = "modification_history.json"  # 本地临时存储历史，或也可推送到GitHub

        # 初始化历史记录
        if not os.path.exists(self.history_file):
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump([], f)

    def load_data(self):
        """从 GitHub 加载 CSV 数据"""
        if not self.token or not self.repo_name:
            return pd.DataFrame()

        url = f"https://raw.githubusercontent.com/{self.repo_name}/main/{self.file_path}"
        try:
            df = pd.read_csv(url)
            # 确保列存在
            required_cols = ['warehouse', 'brand', 'item', 'quantity', 'image']
            for col in required_cols:
                if col not in df.columns:
                    df[col] = "" if col == 'image' else 0
            return df
        except Exception:
            # 如果文件不存在或出错，返回空 DataFrame
            return pd.DataFrame(columns=['id', 'warehouse', 'brand', 'item', 'quantity', 'image', 'updated_at'])

    def save_data(self, df):
        """保存数据到 GitHub CSV"""
        if not self.token or not self.repo_name:
            return False, "❌ 错误：未配置 GitHub Token 或 仓库名 (请检查 Secrets)"

        try:
            from github import Github, Auth

            # 【修复点】使用新的认证方式
            auth = Auth.Token(self.token)
            g = Github(auth=auth)

            # 测试连接：获取当前用户信息（验证 Token 有效性）
            try:
                user = g.get_user()
                # print(f"✅ Token 有效，当前用户：{user.login}") # 生产环境可注释掉以减少日志
            except Exception as auth_err:
                return False, f"❌ Token 无效或过期：{str(auth_err)}"

            # 获取仓库
            try:
                repo = g.get_repo(self.repo_name)
                # print(f"✅ 成功连接到仓库：{repo.full_name}")
            except Exception as repo_err:
                return False, f"❌ 无法访问仓库 '{self.repo_name}'：{str(repo_err)}\n(请检查仓库名格式是否为 '用户名/仓库名' 且 Token 有权限)"

            # 准备文件内容
            csv_buffer = BytesIO()
            # 确保包含所有必要列，防止列丢失
            required_cols = ['id', 'warehouse', 'brand', 'item', 'quantity', 'image', 'updated_at']
            for col in required_cols:
                if col not in df.columns:
                    if col == 'quantity':
                        df[col] = 0
                    elif col == 'id':
                        # 如果没ID列，尝试生成一个简单的序列
                        df[col] = range(1, len(df) + 1)
                    else:
                        df[col] = ""

            # 重新排列列顺序，确保一致性
            df = df[required_cols]

            df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
            content = csv_buffer.getvalue()

            # 获取现有文件 SHA (如果是更新)
            sha = None
            file_exists = True
            try:
                # 明确指定分支为 main
                contents = repo.get_contents(self.file_path, ref="main")
                sha = contents.sha
            except Exception:
                file_exists = False

            # 提交操作
            message = f"Update inventory: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            if file_exists:
                repo.update_file(
                    path=self.file_path,
                    message=message,
                    content=content,
                    sha=sha,
                    branch="main"
                )
            else:
                repo.create_file(
                    path=self.file_path,
                    message=f"Create inventory: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    content=content,
                    branch="main"
                )

            return True, "✅ 保存成功！数据已同步至 GitHub。"

        except Exception as e:
            # 捕获所有未知错误并返回详细信息
            error_msg = f"💥 发生未知错误：{type(e).__name__}: {str(e)}"
            # 在 Streamlit 日志中打印，方便调试
            import sys
            print(f"ERROR DETAILS: {error_msg}", file=sys.stderr)
            return False, error_msg

    def add_history(self, action, details):
        """添加修改历史 (本地存储，简化版)"""
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)

            record = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "action": action,
                "details": details
            }
            history.append(record)
            if len(history) > 100:
                history = history[-100:]

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


# 初始化数据库对象
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
    # 尝试从数据中获取实际存在的仓库
    if not db.token:
        st.warning("⚠️ 请先在 Secrets 中配置 GitHub Token")

    current_warehouse = st.radio("选择当前查看的仓库:", warehouses, index=0)

    st.divider()
    st.header("🛠️ 功能菜单")
    menu = ["📦 库存总览", "➕ 新增/入库", "✏️ 修改数量", "🔄 跨仓调拨", "❌ 删除物品",
            "📥 Excel导入", "📤 Excel导出", "📝 修改历史", "🔧 系统状态"]
    choice = st.radio("导航", menu, label_visibility="collapsed")


# --- 主界面逻辑 ---

def render_inventory_view(df, warehouse, show_all=False):
    st.header(f"{'🌍 全仓汇总' if show_all else f'📦 {warehouse} 库存总览'}")

    if df.empty:
        st.info("暂无数据，请点击上方菜单进行新增或导入。")
        return

    # 过滤数据
    if not show_all:
        df_view = df[df['warehouse'] == warehouse].copy()
    else:
        df_view = df.copy()
        # 汇总逻辑：相同品牌+物品 合并数量和仓库列表
        if not df_view.empty:
            df_view['warehouse_list'] = df_view['warehouse']
            agg_df = df_view.groupby(['brand', 'item']).agg({
                'quantity': 'sum',
                'warehouse_list': lambda x: ', '.join(sorted(set(x))),
                'image': 'first'
            }).reset_index()
            agg_df.rename(columns={'warehouse_list': '分布仓库'}, inplace=True)
            df_view = agg_df

    if df_view.empty:
        st.warning(f"{'全仓' if show_all else warehouse} 暂无库存记录。")
        return

    # 显示表格
    st.dataframe(df_view, use_container_width=True, hide_index=True)

    # 统计信息
    total_qty = df_view['quantity'].sum()
    total_items = len(df_view)
    st.metric(label="总数量" if show_all else f"{warehouse} 总数量", value=f"{total_qty} 件")
    st.metric(label="物品种类" if show_all else f"{warehouse} 种类", value=f"{total_items} 种")


def render_add_item():
    st.header("➕ 新增/入库")

    if not db.token:
        st.error("请先配置 GitHub Token。")
        return

    with st.form("add_form"):
        c1, c2 = st.columns(2)
        with c1:
            brand = st.selectbox("品牌", get_default_brands(), index=0)
            # 允许手动输入新品牌
            if st.checkbox("输入新品牌"):
                brand = st.text_input("新品牌名称", value=brand)

            item = st.selectbox("物品名称", get_default_items(), index=0)
            if st.checkbox("输入新物品"):
                item = st.text_input("新物品名称", value=item)

            warehouse = st.selectbox("目标仓库", get_default_warehouses(), index=0)
            quantity = st.number_input("入库数量", min_value=1, value=1)

        with c2:
            image_path = st.text_input("图片路径 (可选)", placeholder="例如：gear_images/bkk_软饵.jpg")
            st.info("💡 图片路径仅记录文本，实际图片文件需自行上传至仓库或本地对应目录。")

        submitted = st.form_submit_button("💾 确认入库")

        if submitted:
            if not brand or not item:
                st.error("品牌和物品名称不能为空！")
            else:
                df = db.load_data()

                # 检查是否存在
                mask = (df['brand'] == brand) & (df['item'] == item) & (df['warehouse'] == warehouse)
                if df[mask].empty:
                    # 新增
                    new_id = df['id'].max() + 1 if 'id' in df.columns and not df.empty else 1
                    new_row = pd.DataFrame([{
                        'id': new_id,
                        'warehouse': warehouse,
                        'brand': brand,
                        'item': item,
                        'quantity': quantity,
                        'image': image_path,
                        'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }])
                    df = pd.concat([df, new_row], ignore_index=True)
                    msg = f"新增成功：{warehouse} - {brand} {item} x {quantity}"
                else:
                    # 累加
                    df.loc[mask, 'quantity'] += quantity
                    df.loc[mask, 'updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    msg = f"入库成功：{warehouse} - {brand} {item} 数量增加 {quantity}"

                success, err = db.save_data(df)
                if success:
                    st.success(msg)
                    db.add_history("新增/入库", msg)
                    st.rerun()
                else:
                    st.error(f"保存失败：{err}")


def render_update_qty():
    st.header("✏️ 修改数量")
    if not db.token: st.stop()

    df = db.load_data()
    if df.empty: st.warning("无数据"); return

    # 过滤当前仓库
    df_wh = df[df['warehouse'] == current_warehouse]
    if df_wh.empty: st.warning(f"{current_warehouse} 无数据"); return

    # 创建选择器
    options = [f"{row['brand']} - {row['item']} (现有: {row['quantity']})" for _, row in df_wh.iterrows()]
    selected = st.selectbox("选择要修改的物品", options)

    if selected:
        parts = selected.split(" (现有: ")
        name_part = parts[0]
        b, i = name_part.split(" - ")
        current_qty = int(parts[1].replace(")", ""))

        new_qty = st.number_input("新数量", min_value=0, value=current_qty)

        if st.button("更新数量"):
            mask = (df['brand'] == b) & (df['item'] == i) & (df['warehouse'] == current_warehouse)
            df.loc[mask, 'quantity'] = new_qty
            df.loc[mask, 'updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            success, err = db.save_data(df)
            if success:
                st.success(f"已更新 {b} - {i} 数量为 {new_qty}")
                db.add_history("修改数量", f"{current_warehouse}: {b}-{i} -> {new_qty}")
                st.rerun()
            else:
                st.error(err)


def render_transfer():
    st.header("🔄 跨仓调拨")
    if not db.token: st.stop()

    df = db.load_data()
    if df.empty: st.warning("无数据"); return

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("源仓库")
        src_wh = st.selectbox("从哪个仓库？", get_default_warehouses(), key="src")
        df_src = df[df['warehouse'] == src_wh]
        if not df_src.empty:
            src_options = [f"{row['brand']} - {row['item']} (剩: {row['quantity']})" for _, row in df_src.iterrows()]
            src_sel = st.selectbox("选择物品", src_options, key="sel_src")
        else:
            st.warning("该仓库无库存")
            src_sel = None

    with c2:
        st.subheader("目标仓库")
        dst_wh = st.selectbox("调入哪个仓库？", get_default_warehouses(), key="dst",
                              index=(1 if src_wh != get_default_warehouses()[1] else 0))
        if dst_wh == src_wh:
            st.error("目标仓库不能与源仓库相同")

    if src_sel and dst_wh != src_wh:
        parts = src_sel.split(" (剩: ")
        b, i = parts[0].split(" - ")
        max_qty = int(parts[1].replace(")", ""))

        qty = st.number_input("调拨数量", min_value=1, max_value=max_qty, value=1)

        if st.button("执行调拨"):
            # 1. 减少源
            mask_src = (df['brand'] == b) & (df['item'] == i) & (df['warehouse'] == src_wh)
            df.loc[mask_src, 'quantity'] -= qty

            # 如果减到0，可以选择删除行或保留0 (这里保留0或根据需求删除，简单起见保留)
            if df.loc[mask_src, 'quantity'].values[0] <= 0:
                if st.checkbox("数量为0时自动删除记录", value=True):
                    df = df[~mask_src]

            # 2. 增加目标
            mask_dst = (df['brand'] == b) & (df['item'] == i) & (df['warehouse'] == dst_wh)
            if df[mask_dst].empty:
                new_id = df['id'].max() + 1 if 'id' in df.columns and not df.empty else 1
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
                st.success(f"调拨成功：{qty} 件 {b}-{i} 从 {src_wh} -> {dst_wh}")
                db.add_history("跨仓调拨", f"{qty}件 {b}-{i}: {src_wh} -> {dst_wh}")
                st.rerun()
            else:
                st.error(err)


def render_delete():
    st.header("❌ 删除物品")
    if not db.token: st.stop()

    df = db.load_data()
    df_wh = df[df['warehouse'] == current_warehouse]

    if df_wh.empty:
        st.warning("无数据可删")
        return

    options = [f"{row['brand']} - {row['item']} (数量: {row['quantity']})" for _, row in df_wh.iterrows()]
    sel = st.selectbox("选择要删除的记录", options)

    if sel and st.button("确认删除", type="primary"):
        parts = sel.split(" (数量: ")
        b, i = parts[0].split(" - ")

        mask = (df['brand'] == b) & (df['item'] == i) & (df['warehouse'] == current_warehouse)
        df = df[~mask]

        success, err = db.save_data(df)
        if success:
            st.success("删除成功")
            db.add_history("删除物品", f"{current_warehouse}: {b}-{i}")
            st.rerun()
        else:
            st.error(err)


def render_import_excel():
    st.header("📥 Excel 导入")
    st.info("Excel 必须包含列：['品牌', '物品', '数量']。可选列：['图片路径']")

    uploaded = st.file_uploader("上传 Excel 文件", type=['xlsx', 'xls'])
    target_wh = st.selectbox("导入到仓库", get_default_warehouses())

    if uploaded:
        try:
            df_in = pd.read_excel(uploaded)
            # 列名映射
            mapping = {'品牌': 'brand', '物品': 'item', '数量': 'quantity', '图片路径': 'image'}
            # 检查必要列
            if not all(k in df_in.columns for k in ['品牌', '物品', '数量']):
                st.error("Excel 缺少必要列：品牌，物品，数量")
                st.stop()

            df_in = df_in.rename(columns=mapping)
            df_in['warehouse'] = target_wh
            df_in['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if 'image' not in df_in.columns:
                df_in['image'] = ""

            # 加载现有数据
            df_curr = db.load_data()

            count_add = 0
            count_upd = 0

            for _, row in df_in.iterrows():
                mask = (df_curr['brand'] == row['brand']) & (df_curr['item'] == row['item']) & (
                            df_curr['warehouse'] == target_wh)
                if df_curr[mask].empty:
                    # 新增
                    new_id = df_curr['id'].max() + 1 if 'id' in df_curr.columns and not df_curr.empty else 1
                    new_row = pd.DataFrame([{
                        'id': new_id,
                        'warehouse': target_wh,
                        'brand': row['brand'],
                        'item': row['item'],
                        'quantity': int(row['quantity']),
                        'image': row.get('image', ''),
                        'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }])
                    df_curr = pd.concat([df_curr, new_row], ignore_index=True)
                    count_add += 1
                else:
                    # 累加
                    df_curr.loc[mask, 'quantity'] += int(row['quantity'])
                    df_curr.loc[mask, 'updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    count_upd += 1

            success, err = db.save_data(df_curr)
            if success:
                st.success(f"导入完成！新增 {count_add} 条，更新 {count_upd} 条。")
                db.add_history("Excel导入", f"导入 {uploaded.name} 到 {target_wh}, 新增{count_add}, 更新{count_upd}")
                st.rerun()
            else:
                st.error(err)

        except Exception as e:
            st.error(f"读取失败：{str(e)}")


def render_export_excel():
    st.header("📤 Excel 导出")
    df = db.load_data()
    if df.empty:
        st.warning("无数据可导出")
        return

    # 格式化导出列
    export_df = df[['warehouse', 'brand', 'item', 'quantity', 'image']].copy()
    export_df.columns = ['仓库', '品牌', '物品', '数量', '图片路径']

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        export_df.to_excel(writer, index=False, sheet_name='Inventory')

    st.download_button(
        label="下载 Excel 文件",
        data=buffer.getvalue(),
        file_name=f"inventory_export_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def render_history():
    st.header("📝 修改历史")
    history = db.get_history()
    if not history:
        st.info("暂无历史记录")
    else:
        # 倒序显示
        for record in reversed(history[-20:]):  # 只显示最近20条
            st.markdown(f"**[{record['timestamp']}] {record['action']}**: {record['details']}")
            st.divider()


def render_status():
    st.header("🔧 系统状态")
    if db.token:
        st.success("✅ GitHub Token 已配置")
        st.success(f"✅ 连接仓库：{db.repo_name}")

        df = db.load_data()
        st.metric("总记录数", len(df))
        st.metric("最后更新时间", df['updated_at'].max() if not df.empty else "无")
    else:
        st.error("❌ 未配置 GitHub Token")
        st.info("请在 Streamlit Cloud 的 Secrets 中添加 `GITHUB_TOKEN` 和 `GITHUB_REPO`")


# --- 路由分发 ---
if choice == "📦 库存总览":
    tab1, tab2 = st.tabs(["当前仓库视图", "全仓汇总视图"])
    with tab1:
        render_inventory_view(db.load_data(), current_warehouse, show_all=False)
    with tab2:
        render_inventory_view(db.load_data(), "", show_all=True)

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