import os
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime

# ==========================================
# 1. 獲取美股 Nike (NKE) 存貨周轉天數 (DIO)
# ==========================================
def get_nike_dio():
    try:
        print("🔍 正在獲取 Nike (NKE) 財報數據...")
        nike = yf.Ticker("NKE")
        bs = nike.quarterly_balance_sheet
        inc = nike.quarterly_income_stmt
        
        # 抓取最新一季存貨與營業成本
        latest_inventory = bs.loc['Inventory'].iloc[0]
        latest_cogs = inc.loc['Cost Of Revenue'].iloc[0]
        
        # 計算 DIO = (存貨 / 營業成本) * 90天
        dio = (latest_inventory / latest_cogs) * 90
        print(f"✅ 取得 Nike 最新 DIO: {round(dio, 1)} 天")
        return round(dio, 1)
    except Exception as e:
        print(f"❌ 獲取 Nike 財報失敗: {e}")
        return None

# ==========================================
# 2. 爬取越南鞋類出口數據 (Vietnam Footwear Exports)
# ==========================================
def get_vietnam_comtrade_yoy():
    print("🔍 正在透過 UN Comtrade API 獲取越南出口數據...")
    
    api_key = os.environ.get("COMTRADE_API_KEY")
    if not api_key:
        print("❌ 找不到 COMTRADE_API_KEY，請先設定環境變數。")
        return None, None

    url = "https://comtradeapi.un.org/data/v1/get/C/M/HS"
    
    # 自動生成過去 25 個月的查詢期間 (多抓一點確保基期資料存在)
    end_date = pd.Timestamp.now()
    start_date = end_date - pd.DateOffset(months=25)
    all_periods = pd.date_range(start=start_date, end=end_date, freq='ME').strftime('%Y%m').tolist()
    
    # 將期間拆分為最多 12 個月一組 (Comtrade API 的限制)
    period_chunks = [all_periods[i:i + 12] for i in range(0, len(all_periods), 12)]

    params = {
        "reporterCode": "704",      # 越南
        "partnerCode": "0",         # 全球
        "cmdCode": "6404",          # 紡織面料鞋靴
        "flowCode": "X",            # 出口
        "format": "JSON"
    }

    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        "User-Agent": "QuantBot/1.0"
    }

    all_data = []
    
    try:
        # 分批發送請求並合併資料
        for chunk in period_chunks:
            params["period"] = ",".join(chunk)
            response = requests.get(url, params=params, headers=headers, timeout=20)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('data'):
                    all_data.extend(data['data'])
            else:
                print(f"⚠️ API 請求失敗，狀態碼: {response.status_code}，區間: {chunk[0]}~{chunk[-1]}")
            
            # 避免觸發 API 頻率限制
            time.sleep(1)

        if not all_data:
            print("⚠️ 聯合國資料庫目前查無越南近期的 6404 出口數據 (可能尚未更新)。")
            return None, None

        # 將合併後的 JSON 轉為 Pandas DataFrame
        df = pd.DataFrame(all_data)
        
        df = df[['period', 'primaryValue']].copy()
        df['Date'] = pd.to_datetime(df['period'].astype(str), format='%Y%m')
        df = df.sort_values('Date', ascending=False).reset_index(drop=True)
        
        latest = df.iloc[0]
        last_year_df = df[df['Date'] == (latest['Date'] - pd.DateOffset(years=1))]
        
        if last_year_df.empty:
            print("❌ 找不到去年同月的基期資料，無法計算 YoY。")
            return None, None
            
        last_year = last_year_df.iloc[0]
        
        latest_val = float(latest['primaryValue'])
        last_year_val = float(last_year['primaryValue'])
        
        yoy = ((latest_val - last_year_val) / last_year_val) * 100
        month_str = latest['Date'].strftime('%Y-%m')
        
        print(f"✅ 最新 {month_str} 越南 6404 鞋類出口: {latest_val / 1e6:.2f} 百萬美元")
        print(f"✅ 去年同期出口: {last_year_val / 1e6:.2f} 百萬美元")
        print(f"🚀 Comtrade 權威出口 YoY: {round(yoy, 2)}%")
        
        return round(yoy, 2), month_str

    except Exception as e:
        print(f"❌ 解析 Comtrade API 發生錯誤: {e}")
        return None, None

# ==========================================
# 3. 法人策略分析矩陣 (Nike DIO vs Vietnam YoY)
# ==========================================
def analyze_shoe_strategy(dio, yoy):
    status = "未知狀態"
    action = "持續觀察"
    
    # Nike 健康 DIO 基準線通常設為 105 天
    if yoy > 0 and dio <= 105:
        status = "🟢 【黃金爆發期：訂單強勁且通路暢通】"
        action = "終端需求真實。強烈建議佈局台灣製鞋代工廠 (豐泰 9910、寶成 9904)。"
    elif yoy > 0 and dio > 105:
        status = "🔴 【塞貨陷阱期：代工廠出貨，但品牌塞港】"
        action = "高風險警示！代工營收亮眼但品牌庫存飆升，未來一季極可能發生暴力砍單，建議獲利了結。"
    elif yoy < 0 and dio > 105:
        status = "⚫ 【庫存去化期：產業寒冬】"
        action = "品牌廠努力去化舊庫存，全面停止下單。避開所有製鞋供應鏈。"
    elif yoy < 0 and dio <= 105:
        status = "🟡 【復甦前夕期：庫存見底】"
        action = "品牌廠庫存已降至健康水位，隨時重啟拉貨潮。逢低建立代工廠基本部位。"
        
    return status, action

# ==========================================
# 4. Discord Webhook 警報推送
# ==========================================
def send_discord_alert(dio, yoy, month_str, status, action):
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("⚠️ 未設定 DISCORD_WEBHOOK_URL，僅於終端機顯示報告。")
        return

    content = f"""
**👟 【法人級：製鞋供應鏈量化監控 (Nike vs 豐泰)】**
> **觀測時間：** {datetime.now().strftime("%Y-%m-%d")}

**1. 美國終端庫存指標 (NKE)**
* Nike 最新存貨周轉天數 (DIO)：**{dio} 天** (健康水位: <105天)

**2. 亞洲生產端高頻數據 (Vietnam GSO)**
* 越南鞋類最新出口月份：**{month_str}**
* 越南鞋類出口 YoY：**{yoy}%**

**3. 量化策略判定**
* **當前狀態：** {status}
* **執行建議：** {action}

*以上內容由自動化程式生成，僅供產業研究參考，不構成任何投資建議。*
"""
    try:
        response = requests.post(webhook_url, json={"content": content})
        if response.status_code == 204:
            print("✅ Discord 警報發送成功！")
    except Exception as e:
        print(f"❌ Discord 發送失敗: {e}")

# ==========================================
# 主程式執行
# ==========================================
if __name__ == "__main__":
    print("啟動【製鞋業台美股連動】分析引擎...")
    dio_val = get_nike_dio()
    yoy_val, data_month = get_vietnam_comtrade_yoy()
    
    if dio_val is not None and yoy_val is not None:
        status, action = analyze_shoe_strategy(dio_val, yoy_val)
        send_discord_alert(dio_val, yoy_val, data_month, status, action)
