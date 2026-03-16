import streamlit as st
import pandas as pd
import database as db
from datetime import datetime

# 页面配置
st.set_page_config(page_title="🎣 渔具库存管理系统 (GitHub 版)", page_icon="🎣", layout="wide")

# 标题
st.title("🎣 智能渔具库存管理系统 (永久存储版)")
st.markdown("""
<style>
    .metric-card {background-color: #f0f2f6; padding: 10px; border-radius: 10px;}
</style>
""", unsafe_allow_html=True)

# 侧边栏
menu = ["📦 库存总览", "➕ 新增物品", "✏️ 编辑/出入库", "⚠️ 库存预警", "🔧 系统状态"]
choice = st.sidebar.selectbox("功能菜单", menu)


# --- 辅助函数 ---
@st.cache_data(ttl=60)  # 缓存 60 秒，避免频繁请求 GitHub
def get_cached_data():
    return db.load_data()


def refresh_data():
    st.cache_data.clear()
    st.rerun()


# --- 页面逻辑 ---

if choice == "📦 库存总览":
    st.header("当前库存概览")

    # 检查配置
    if not db.GITHUB_TOKEN:
        st.error("⚠️ **未检测到 GitHub Token！** 请在 Streamlit 后台 Secrets 中配置 `GITHUB_TOKEN` 和 `GITHUB_REPO`。")
        st.stop()

    df = get_cached_data()

    if df.empty:
        st.info("📭 暂无库存数据。请点击左侧菜单【新增物品】添加第一批渔具。")
    else:
        # 统计卡片
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("物品种类", len(df))
        c2.metric("总库存数量", df['quantity'].sum())
        c3.metric("仓库分布", df['warehouse'].nunique())
        low_stock = len(df[df['quantity'] <= df['min_stock']])
        c4.metric("低库存预警", low_stock, delta_color="inverse")

        # 搜索过滤
        col1, col2 = st.columns([3, 1])
        with col1:
            search = st.text_input("🔍 搜索 (品牌/名称/类别)", "")
        with col2:
            wh_filter = st.selectbox("筛选仓库", ["全部"] + sorted(df['warehouse'].unique()))

        # 过滤逻辑
        mask = (df['brand'].str.contains(search, case=False, na=False) |
                df['name'].str.contains(search, case=False, na=False) |
                df['category'].str.contains(search, case=False, na=False))
        if wh_filter != "全部":
            mask &= (df['warehouse'] == wh_filter)

        view_df = df[mask].copy()


        # 状态列
        def get_status(qty, min_q):
            return "⚠️ 缺货" if qty <= min_q else "✅ 充足"


        view_df['状态'] = view_df.apply(lambda x: get_status(x['quantity'], x['min_stock']), axis=1)


        # 样式高亮
        def color_status(val):
            return 'background-color: #ffcccc' if val == "⚠️ 缺货" else ''


        st.dataframe(
            view_df.style.applymap(color_status, subset=['状态']),
            use_container_width=True,
            hide_index=True
        )

elif choice == "➕ 新增物品":
    st.header("新增入库")

    if not db.GITHUB_TOKEN:
        st.error("请先配置 GitHub Token (见🔧 系统状态)。")
        st.stop()

    with st.form("add_form"):
        c1, c2 = st.columns(2)
        with c1:
            brand = st.text_input("品牌 (Brand)*", required=True)
            name = st.text_input("物品名称 (Name)*", required=True)
            category = st.selectbox("类别", ["鱼钩", "鱼线", "拟饵", "配件", "鱼竿", "其他"])
            warehouse = st.selectbox("所属仓库", ["主仓库", "分店A", "车载箱", "家中"])
            location = st.text_input("库位 (如 A-01)", "")
            quantity = st.number_input("初始数量", min_value=0, value=0)
        with c2:
            min_stock = st.number_input("最低库存预警", min_value=0, value=5)
            unit_price = st.number_input("单价 (元)", min_value=0.0, step=0.1)
            batch_no = st.text_input("批次号", "")
            expiry_date = st.date_input("过期日期 (可选)", value=None)

        submitted = st.form_submit_button("💾 保存并同步到 GitHub")

        if submitted:
            with st.spinner("正在连接 GitHub 并写入数据..."):
                success, msg = db.add_item(brand, name, category, warehouse, location, quantity, min_stock, unit_price,
                                           batch_no, expiry_date)
                if success:
                    st.success(msg)
                    refresh_data()
                else:
                    st.error(msg)

elif choice == "✏️ 编辑/出入库":
    st.header("编辑与快速出入库")

    if not db.GITHUB_TOKEN:
        st.error("请先配置 GitHub Token。")
        st.stop()

    df = get_cached_data()
    if df.empty:
        st.warning("暂无数据可编辑。")
    else:
        # 选择物品
        df['display'] = df['id'].astype(str) + " - " + df['brand'] + " " + df['name'] + " (" + df['warehouse'] + ")"
        selected_str = st.selectbox("选择物品", df['display'])

        if selected_str:
            selected_id = int(selected_str.split(" - ")[0])
            item = df[df['id'] == selected_id].iloc[0]

            st.subheader(f"当前库存: **{item['quantity']}** (预警线: {item['min_stock']})")

            # 快速出入库
            with st.expander("⚡ 快速出入库 (不修改其他信息)"):
                c1, c2, c3 = st.columns([1, 1, 2])
                with c1:
                    change_qty = st.number_input("数量", min_value=1, value=1)
                with c2:
                    action = st.selectbox("类型", ["入库 (+)", "出库 (-)"])
                with c3:
                    reason = st.text_input("备注", "手动调整")

                if st.button("执行变动"):
                    new_qty = item['quantity'] + change_qty if "入库" in action else item['quantity'] - change_qty
                    if new_qty < 0:
                        st.error("❌ 库存不能为负数！")
                    else:
                        with st.spinner("同步中..."):
                            success, msg = db.update_item(selected_id, quantity=new_qty)
                            if success:
                                st.success(f"{msg} 新库存: {new_qty}")
                                refresh_data()
                            else:
                                st.error(msg)

            st.divider()

            # 完整编辑
            st.write("### 📝 完整信息编辑")
            with st.form("edit_full"):
                ec1, ec2 = st.columns(2)
                with ec1:
                    ed_brand = st.text_input("品牌", value=item['brand'])
                    ed_name = st.text_input("名称", value=item['name'])
                    ed_cat = st.selectbox("类别", ["鱼钩", "鱼线", "拟饵", "配件", "鱼竿", "其他"],
                                          index=["鱼钩", "鱼线", "拟饵", "配件", "鱼竿", "其他"].index(item['category']) if item[
                                                                                                                    'category'] in [
                                                                                                                    "鱼钩",
                                                                                                                    "鱼线",
                                                                                                                    "拟饵",
                                                                                                                    "配件",
                                                                                                                    "鱼竿",
                                                                                                                    "其他"] else 5)
                    ed_wh = st.text_input("仓库", value=item['warehouse'])
                    ed_loc = st.text_input("库位", value=item['location'])
                with ec2:
                    ed_min = st.number_input("最低库存", value=int(item['min_stock']))
                    ed_price = st.number_input("单价", value=float(item['unit_price']))
                    ed_batch = st.text_input("批次", value=item['batch_no'])
                    # 处理日期
                    try:
                        ed_exp_val = datetime.strptime(str(item['expiry_date']), "%Y-%m-%d").date() if item[
                                                                                                           'expiry_date'] and str(
                            item['expiry_date']) != "nan" else None
                    except:
                        ed_exp_val = None
                    ed_exp = st.date_input("过期日", value=ed_exp_val)

                col_del, col_save = st.columns([1, 4])
                with col_del:
                    if st.button("🗑️ 删除此物品", type="secondary"):
                        if st.checkbox("确认删除？此操作不可逆"):
                            with st.spinner("删除中..."):
                                success, msg = db.delete_item(selected_id)
                                if success:
                                    st.success("已删除")
                                    refresh_data()
                                else:
                                    st.error(msg)
                with col_save:
                    if st.form_submit_button("💾 保存修改"):
                        with st.spinner("同步中..."):
                            success, msg = db.update_item(
                                selected_id,
                                brand=ed_brand, name=ed_name, category=ed_cat,
                                warehouse=ed_wh, location=ed_loc,
                                min_stock=ed_min, unit_price=ed_price,
                                batch_no=ed_batch, expiry_date=ed_exp
                            )
                            if success:
                                st.success(msg)
                                refresh_data()
                            else:
                                st.error(msg)

elif choice == "⚠️ 库存预警":
    st.header("低库存预警列表")
    df = get_cached_data()
    if df.empty:
        st.info("无数据")
    else:
        warning_df = df[df['quantity'] <= df['min_stock']]
        if warning_df.empty:
            st.success("🎉 所有库存充足！无需补货。")
        else:
            st.dataframe(warning_df[['brand', 'name', 'warehouse', 'quantity', 'min_stock']], use_container_width=True)
            st.bar_chart(warning_df.set_index('name')['quantity'])

elif choice == "🔧 系统状态":
    st.header("系统配置检查")

    st.write("### 1. GitHub 连接状态")
    if db.GITHUB_TOKEN and db.REPO_NAME:
        st.success("✅ Token 和 仓库名 已配置")
        st.info(f"当前仓库: `{db.REPO_NAME}`")
        st.write("💡 **提示**: 数据将保存在该仓库的 `inventory.csv` 文件中。您可以去 GitHub 查看该文件验证数据。")

        # 测试连接
        repo = db.get_repo()
        if repo:
            st.success("✅ 成功连接到 GitHub 仓库！")
            try:
                content = repo.get_contents("inventory.csv")
                st.success(f"✅ 找到数据文件 `inventory.csv` (大小: {content.size} bytes)")
            except:
                st.warning("⚠️ 暂未找到 `inventory.csv` 文件。这是正常的，当您第一次添加物品时会自动创建。")
        else:
            st.error("❌ 无法连接 GitHub。请检查 Token 是否有 `repo` 权限，以及仓库名是否正确。")
    else:
        st.error("❌ 缺少配置。请按以下步骤操作：")
        st.code("""
        1. 点击 Streamlit 页面右上角的三个点 (...) -> Secrets
        2. 输入以下内容：

        GITHUB_TOKEN = "ghp_你的长串Token"
        GITHUB_REPO = "你的用户名/你的仓库名"
        """)

    st.divider()
    st.write("### 2. 关于数据持久化")
    st.markdown("""
    - **原理**: 每次保存时，程序会自动向您的 GitHub 仓库提交一个 `inventory.csv` 文件的更新。
    - **安全性**: 数据存储在 GitHub 服务器上，即使 Streamlit 重启，数据也不会丢失。
    - **版本控制**: 您可以在 GitHub 仓库的 "Commits" 中看到每一次库存变动的记录，随时可以回滚到旧版本。
    """)