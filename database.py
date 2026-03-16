import os
import pandas as pd
import base64
from io import StringIO
from github import Github
from datetime import datetime

# 配置项：从 Streamlit Secrets 获取
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = os.getenv("GITHUB_REPO")  # 格式：username/repo-name
CSV_FILENAME = "inventory.csv"


def get_repo():
    """获取 GitHub 仓库对象"""
    if not GITHUB_TOKEN or not REPO_NAME:
        return None
    try:
        g = Github(GITHUB_TOKEN)
        return g.get_repo(REPO_NAME)
    except Exception as e:
        print(f"GitHub 连接错误: {e}")
        return None


def load_data():
    """从 GitHub 加载 CSV 数据"""
    repo = get_repo()

    # 如果未配置 Token，返回空结构（避免报错）
    if not repo:
        return get_empty_df()

    try:
        # 尝试获取文件内容
        file_content = repo.get_contents(CSV_FILENAME)
        # GitHub API 返回的是 base64 编码，需要解码
        decoded_content = base64.b64decode(file_content.content).decode('utf-8')
        df = pd.read_csv(StringIO(decoded_content))
        # 确保数据类型正确
        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0).astype(int)
        df['min_stock'] = pd.to_numeric(df['min_stock'], errors='coerce').fillna(5).astype(int)
        return df
    except Exception as e:
        # 如果文件不存在（404），返回空 DataFrame
        if "404" in str(e):
            return get_empty_df()
        print(f"加载数据失败: {e}")
        return get_empty_df()


def save_data(df):
    """将 DataFrame 保存为 CSV 推送到 GitHub"""
    repo = get_repo()
    if not repo:
        return False, "错误：未配置 GitHub Token 或仓库名。请在 Streamlit Secrets 中设置。"

    try:
        # 将 DataFrame 转为 CSV 字符串
        csv_str = df.to_csv(index=False)

        # 检查文件是否已存在，以获取 sha (更新文件必须提供 sha)
        try:
            file_content = repo.get_contents(CSV_FILENAME)
            sha = file_content.sha
            message = f"Update inventory: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            repo.update_file(CSV_FILENAME, message, csv_str, sha)
        except Exception:
            # 文件不存在，创建新文件
            message = "Initial commit: Create inventory database"
            repo.create_file(CSV_FILENAME, message, csv_str)

        return True, "✅ 数据已成功同步到 GitHub！"
    except Exception as e:
        return False, f"❌ 同步失败: {str(e)}"


def get_empty_df():
    """返回空的 DataFrame 结构"""
    columns = ['id', 'brand', 'name', 'category', 'warehouse', 'location',
               'quantity', 'min_stock', 'unit_price', 'batch_no', 'expiry_date',
               'created_at', 'updated_at']
    return pd.DataFrame(columns=columns)


# --- 业务逻辑接口 ---

def add_item(brand, name, category, warehouse, location, quantity, min_stock, unit_price, batch_no, expiry_date):
    df = load_data()

    # 生成新 ID
    new_id = 1 if df.empty else int(df['id'].max()) + 1
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    new_row = {
        'id': new_id,
        'brand': brand,
        'name': name,
        'category': category,
        'warehouse': warehouse,
        'location': location,
        'quantity': int(quantity),
        'min_stock': int(min_stock),
        'unit_price': float(unit_price),
        'batch_no': batch_no,
        'expiry_date': str(expiry_date) if expiry_date else "",
        'created_at': now,
        'updated_at': now
    }

    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    return save_data(df)


def update_item(item_id, **kwargs):
    df = load_data()

    if item_id not in df['id'].values:
        return False, "物品 ID 不存在"

    # 更新字段
    kwargs['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 确保数值类型
    if 'quantity' in kwargs: kwargs['quantity'] = int(kwargs['quantity'])
    if 'min_stock' in kwargs: kwargs['min_stock'] = int(kwargs['min_stock'])
    if 'unit_price' in kwargs: kwargs['unit_price'] = float(kwargs['unit_price'])
    if 'expiry_date' in kwargs: kwargs['expiry_date'] = str(kwargs['expiry_date']) if kwargs['expiry_date'] else ""

    for key, value in kwargs.items():
        df.loc[df['id'] == item_id, key] = value

    return save_data(df)


def delete_item(item_id):
    df = load_data()
    if item_id not in df['id'].values:
        return False, "物品 ID 不存在"

    df = df[df['id'] != item_id]
    return save_data(df)