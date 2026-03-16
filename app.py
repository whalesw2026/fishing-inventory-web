import streamlit as st
import pandas as pd
import database as db
import os
from datetime import datetime

# 页面配置
st.set_page_config(page_title="渔具库存管理系统", page_icon="🎣", layout="wide")

# 标题
st.title("🎣 智能渔具库存管理系统 (Web版)")

# 侧边栏：功能选择
menu = ["库存总览", "新增物品", "编辑/出入库", "库存预警", "出入库日志"]
choice = st.sidebar.selectbox("功能菜单", menu)


# --- 辅助函数 ---
def load_data():
    rows = db.get_all_items()
    if not rows:
        return pd.DataFrame()

    # 转换为 DataFrame
    columns = [col[0] for col in rows[0].keys()]
    df = pd.DataFrame(rows, columns=columns)

    # 计算状态列
    df['状态'] = df.apply(lambda x: '⚠️ 缺货' if x['quantity'] <= x['min_stock'] else '✅ 充足', axis=1)
    return df


# --- 页面逻辑 ---

if choice == "库存总览":
    st.header("📦 当前库存概览")

    df = load_data()

    if df.empty:
        st.info("暂无库存数据，请去'新增物品'添加。")
    else:
        # 统计卡片
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("物品种类", len(df))
        col2.metric("总库存数量", df['quantity'].sum())
        col3.metric("仓库总数", df['warehouse'].nunique())
        low_stock_count = len(df[df['quantity'] <= df['min_stock']])
        col4.metric("低库存预警", low_stock_count, delta_color="inverse")

        # 搜索与过滤
        col_search, col_wh = st.columns([3, 1])
        with col_search:
            search_term = st.text_input("🔍 搜索 (品牌/名称/类别)", "")
        with col_wh:
            wh_filter = st.selectbox("筛选仓库", ["全部"] + list(df['warehouse'].unique()))

        # 应用过滤
        mask = (df['brand'].str.contains(search_term, case=False) |
                df['name'].str.contains(search_term, case=False) |
                df['category'].str.contains(search_term, case=False))
        if wh_filter != "全部":
            mask &= (df['warehouse'] == wh_filter)

        filtered_df = df[mask]


        # 显示表格 (使用样式高亮低库存)
        def color_low_stock(val):
            color = '#ffcccc' if val == '⚠️ 缺货' else '#ffffff'
            return f'background-color: {color}'


        st.dataframe(
            filtered_df.style.applymap(color_low_stock, subset=['状态']),
            use_container_width=True,
            hide_index=True
        )

elif choice == "新增物品":
    st.header("➕ 新增入库")

    with st.form("add_form"):
        col1, col2 = st.columns(2)
        with col1:
            brand = st.text_input("品牌 (Brand)*", required=True)
            name = st.text_input("物品名称 (Name)*", required=True)
            category = st.selectbox("类别", ["鱼钩", "鱼线", "拟饵", "配件", "竿稍", "其他"])
            warehouse = st.selectbox("所属仓库", ["主仓库", "分店A", "分店B", "车载箱"])
            location = st.text_input("库位 (如 A-01-2)", "")
            quantity = st.number_input("初始数量", min_value=0, value=0)
        with col2:
            min_stock = st.number_input("最低库存预警值", min_value=0, value=5)
            unit_price = st.number_input("单价 (元)", min_value=0.0, step=0.1)
            batch_no = st.text_input("生产批次号", "")
            expiry_date = st.date_input("过期日期 (可选)", value=None)
            # 图片上传 (简化版：仅存文件名，实际需配置上传文件夹)
            # uploaded_file = st.file_uploader("上传产品图", type=['png', 'jpg'])

        submitted = st.form_submit_button("保存入库")

        if submitted:
            try:
                db.add_item(brand, name, category, warehouse, location, quantity, min_stock, unit_price, batch_no,
                            expiry_date)
                st.success(f"✅ {brand} - {name} 已成功入库！")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 发生错误: {e}")

elif choice == "编辑/出入库":
    st.header("✏️ 编辑与快速出入库")

    df = load_data()
    if df.empty:
        st.warning("暂无数据。")
    else:
        # 选择物品
        item_list = df['id'].astype(str) + " - " + df['brand'] + " " + df['name'] + " (" + df['warehouse'] + ")"
        selected_option = st.selectbox("选择要操作的物品", item_list)

        if selected_option:
            selected_id = int(selected_option.split(" - ")[0])
            item_data = df[df['id'] == selected_id].iloc[0]

            st.subheader(f"当前库存: {item_data['quantity']} (预警线: {item_data['min_stock']})")

            # 快速出入库
            col_q1, col_q2, col_q3 = st.columns([1, 1, 2])
            with col_q1:
                change_qty = st.number_input("变动数量", min_value=1, value=1)
            with col_q2:
                action_type = st.selectbox("操作类型", ["入库 (+)", "出库 (-)"])
            with col_q3:
                reason = st.text_input("备注原因", "日常补货/销售")

            if st.button("执行变动"):
                new_qty = item_data['quantity'] + change_qty if "入库" in action_type else item_data[
                                                                                             'quantity'] - change_qty
                if new_qty < 0:
                    st.error("❌ 库存不能为负数！")
                else:
                    # 更新数据库
                    db.update_item(
                        selected_id, item_data['brand'], item_data['name'], item_data['category'],
                        item_data['warehouse'], item_data['location'], new_qty,
                        item_data['min_stock'], item_data['unit_price'],
                        item_data['batch_no'], item_data['expiry_date']
                    )
                    st.success(f"✅ 操作成功！新库存: {new_qty}")
                    st.rerun()

            st.divider()

            # 完整编辑表单
            st.write("### 完整信息编辑")
            with st.form("edit_form"):
                c1, c2 = st.columns(2)
                with c1:
                    ed_brand = st.text_input("品牌", value=item_data['brand'])
                    ed_name = st.text_input("名称", value=item_data['name'])
                    ed_cat = st.selectbox("类别", ["鱼钩", "鱼线", "拟饵", "配件", "竿稍", "其他"],
                                          index=["鱼钩", "鱼线", "拟饵", "配件", "竿稍", "其他"].index(item_data['category']) if
                                          item_data['category'] in ["鱼钩", "鱼线", "拟饵", "配件", "竿稍", "其他"] else 5)
                    ed_wh = st.text_input("仓库", value=item_data['warehouse'])
                    ed_loc = st.text_input("库位", value=item_data['location'])
                with c2:
                    ed_min = st.number_input("最低库存", value=int(item_data['min_stock']))
                    ed_price = st.number_input("单价", value=float(item_data['unit_price']))
                    ed_batch = st.text_input("批次", value=item_data['batch_no'] if item_data['batch_no'] else "")
                    ed_exp = st.date_input("过期日", value=item_data['expiry_date'] if item_data['expiry_date'] else None)

                col_del, col_save = st.columns([1, 4])
                with col_del:
                    if st.button("🗑️ 删除此物品", type="secondary"):
                        if st.checkbox("确认删除？"):
                            db.delete_item(selected_id)
                            st.success("已删除")
                            st.rerun()
                with col_save:
                    if st.form_submit_button("💾 保存修改"):
                        # 注意：这里直接保存会覆盖刚才的快速出入库结果，实际逻辑应更严谨
                        # 为简化演示，这里只更新非数量字段，数量由上面的快速出入库控制
                        # 若要全量更新，需重新获取最新数量
                        current_row = db.get_all_items()  # 重新拉取最新
                        # 简单处理：直接用表单里的数量（如果用户改了）或者保持原样
                        # 此处为了逻辑清晰，建议只允许在表单里改属性，数量用上面的按钮
                        # 但为了功能完整，我们假设用户可能在这里也改了数量
                        final_qty = st.session_state.get('final_qty',
                                                         item_data['quantity'])  # 这里需要更复杂的session状态管理，简化起见略过

                        # 简单调用更新，实际项目中应合并逻辑
                        db.update_item(selected_id, ed_brand, ed_name, ed_cat, ed_wh, ed_loc, item_data['quantity'],
                                       ed_min, ed_price, ed_batch, ed_exp)
                        st.success("信息已更新")
                        st.rerun()

elif choice == "库存预警":
    st.header("⚠️ 低库存预警列表")
    df = load_data()
    if df.empty:
        st.info("无数据")
    else:
        warning_df = df[df['quantity'] <= df['min_stock']]
        if warning_df.empty:
            st.success("🎉 所有库存充足！")
        else:
            st.dataframe(warning_df[['brand', 'name', 'warehouse', 'location', 'quantity', 'min_stock', '状态']],
                         use_container_width=True)

            # 简单的图表
            st.bar_chart(warning_df.set_index('name')['quantity'])

elif choice == "出入库日志":
    st.header("📜 操作审计日志")
    conn = db.get_connection()
    log_df = pd.read_sql_query("SELECT * FROM logs ORDER BY timestamp DESC LIMIT 50", conn)
    conn.close()
    st.dataframe(log_df, use_container_width=True)