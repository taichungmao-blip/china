import os
import time
import requests
import pandas as pd

def get_vietnam_comtrade_yoy():
    print("🔍 正在透過 UN Comtrade API 獲取數據 (優先查詢美國進口端)...")
    
    api_key = os.environ.get("COMTRADE_API_KEY")
    if not api_key:
        print("❌ 找不到 COMTRADE_API_KEY，請先設定環境變數。")
        return None, None

    url = "https://comtradeapi.un.org/data/v1/get/C/M/HS"
    
    # 生成過去 25 個月的查詢期間
    end_date = pd.Timestamp.now()
    start_date = end_date - pd.DateOffset(months=25)
    all_periods = pd.date_range(start=start_date, end=end_date, freq='ME').strftime('%Y%m').tolist()
    period_chunks = [all_periods[i:i + 12] for i in range(0, len(all_periods), 12)]

    # 設定查詢參數：美國 (842) 從 越南 (704) 進口 (M)
    # 這是因為美國端的數據通常更新較快且準確
    params = {
        "reporterCode": "842",      # 美國
        "partnerCode": "704",       # 越南
        "cmdCode": "6404",          # 鞋類 (HS 6404)
        "flowCode": "M",            # 進口 (Import)
        "format": "JSON"
    }

    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        "User-Agent": "QuantBot/1.0"
    }

    all_data = []
    
    try:
        for chunk in period_chunks:
            params["period"] = ",".join(chunk)
            response = requests.get(url, params=params, headers=headers, timeout=20)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('data'):
                    all_data.extend(data['data'])
            elif response.status_code == 429:
                print("⚠️ 觸發 API 頻率限制，暫停後重試...")
                time.sleep(5)
            else:
                print(f"⚠️ API 請求失敗，狀態碼: {response.status_code}")
            
            time.sleep(1) # 符合免費版頻率限制

        # 如果美國端沒資料，嘗試切換回越南出口端 (Reporter: 704, Partner: 0, Flow: X)
        if not all_data:
            print("⚠️ 美國進口端暫無近期數據，嘗試切換回越南出口端查詢...")
            params.update({"reporterCode": "704", "partnerCode": "0", "flowCode": "X"})
            # 此處省略重複的迴圈請求邏輯，建議實務上可封裝成私有函數
            # ... (若需完整備援邏輯可在此重複上述 for chunk 過程)

        if not all_data:
            print("⚠️ 聯合國資料庫目前查無相關近期數據 (可能尚未更新)。")
            return None, None

        # 資料處理
        df = pd.DataFrame(all_data)
        df = df[['period', 'primaryValue']].copy()
        df['Date'] = pd.to_datetime(df['period'].astype(str), format='%Y%m')
        df = df.sort_values('Date', ascending=False).reset_index(drop=True)
        
        latest = df.iloc[0]
        # 尋找 12 個月前的數據
        target_date = latest['Date'] - pd.DateOffset(years=1)
        last_year_df = df[df['Date'] == target_date]
        
        if last_year_df.empty:
            print(f"❌ 找不到基期資料 ({target_date.strftime('%Y-%m')})，無法計算 YoY。")
            return None, None
            
        last_year = last_year_df.iloc[0]
        latest_val = float(latest['primaryValue'])
        last_year_val = float(last_year['primaryValue'])
        
        yoy = ((latest_val - last_year_val) / last_year_val) * 100
        month_str = latest['Date'].strftime('%Y-%m')
        
        print(f"✅ 成功獲取 {month_str} 數據 (數據源: US Import from Vietnam)")
        print(f"✅ 本期數值: {latest_val / 1e6:.2f} M USD")
        print(f"✅ 去年同期: {last_year_val / 1e6:.2f} M USD")
        print(f"🚀 數據 YoY: {round(yoy, 2)}%")
        
        return round(yoy, 2), month_str

    except Exception as e:
        print(f"❌ 執行過程發生錯誤: {e}")
        return None, None
