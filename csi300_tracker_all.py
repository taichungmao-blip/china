import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import requests
import io
import os
import sys
import time
from deep_translator import GoogleTranslator

# ================= 設定區 =================
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Yahoo Finance 產業版塊中英對照表
SECTOR_MAP = {
    'Technology': '科技',
    'Financial Services': '金融服務',
    'Consumer Defensive': '必需消費',
    'Consumer Cyclical': '非必需消費',
    'Healthcare': '醫療保健',
    'Industrials': '工業',
    'Basic Materials': '原物料',
    'Energy': '能源',
    'Utilities': '公用事業',
    'Real Estate': '房地產',
    'Communication Services': '通訊服務'
}

if not WEBHOOK_URL:
    print("錯誤：找不到 DISCORD_WEBHOOK_URL 環境變數！")
    sys.exit(1)
# ==========================================

def get_company_details(ticker, close_price):
    """獲取簡介、精準股息率、公司名稱與產業別"""
    try:
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info
        
        company_name = info.get('shortName', info.get('longName', ticker))
        sector_en = info.get('sector', 'Unknown')
        
        pe_ratio = info.get('trailingPE', info.get('forwardPE', 'N/A'))
        if isinstance(pe_ratio, (int, float)):
            pe_ratio = f"{pe_ratio:.2f}"
            
        trailing_div_rate = info.get('trailingAnnualDividendRate')
        if isinstance(trailing_div_rate, (int, float)) and close_price > 0:
            div_yield = (trailing_div_rate / close_price) * 100
            div_yield_str = f"{div_yield:.2f}%" if div_yield > 0 else "0.00%"
        else:
            raw_yield = info.get('dividendYield')
            if isinstance(raw_yield, (int, float)):
                div_yield_str = f"{raw_yield:.2f}%" if raw_yield > 0.3 else f"{raw_yield * 100:.2f}%"
            else:
                div_yield_str = "N/A"

        summary_en = info.get('longBusinessSummary', '')
        if not summary_en:
            return "暫無簡介", pe_ratio, div_yield_str, company_name, sector_en
        if len(summary_en) > 300:
            summary_en = summary_en[:300]

        translator = GoogleTranslator(source='auto', target='zh-TW')
        summary_zh = translator.translate(summary_en) + "..."
        
        return summary_zh, pe_ratio, div_yield_str, company_name, sector_en
    except Exception as e:
        print(f"資料獲取或翻譯失敗 ({ticker}): {e}")
        return "無法獲取簡介", "N/A", "N/A", ticker, "Unknown"

def send_to_discord(ticker, company_name, sector_en, close_price, pct_change, image_buffer, summary, pe_ratio, div_yield):
    sector_cn = SECTOR_MAP.get(sector_en, sector_en)
    
    trend_emoji = "📈" if pct_change > 0 else "📉"
    trend_text = "漲幅" if pct_change > 0 else "跌幅"
    
    message_content = (
        f"{trend_emoji} **{ticker} - {company_name}**\n"
        f"🏢 版塊: {sector_cn} ({sector_en})\n"
        f"📊 本益比 (P/E): **{pe_ratio}** |  💰 股息率: **{div_yield}**\n"
        f"📝 簡介: {summary}\n"
        f"🔹 收盤價: ¥{close_price:.2f}\n" 
        f"{trend_emoji} {trend_text}: **{pct_change * 100:.2f}%**" 
    )
    
    payload = {"content": message_content}
    image_buffer.seek(0)
    files = {"file": (f"{ticker}_1Y.png", image_buffer, "image/png")}
    requests.post(WEBHOOK_URL, data=payload, files=files)

def process_and_send_list(stock_series, title_msg, line_color):
    if stock_series.empty:
        print(f"{title_msg} 無符合資料")
        return
        
    print(f"\n--- {title_msg} ---")
    requests.post(WEBHOOK_URL, json={"content": f"📊 **{title_msg}** 📊"})
    time.sleep(1)
    
    for rank, (ticker, pct) in enumerate(stock_series.items(), start=1):
        try:
            stock_data = yf.download(ticker, period="9mo", progress=False)
            if stock_data.empty: continue
            
            close_price = stock_data['Close'].iloc[-1].item()
            
            summary, pe_ratio, div_yield, company_name, sector_en = get_company_details(ticker, close_price)
            
            plt.figure(figsize=(10, 5))
            plt.plot(stock_data.index, stock_data['Close'], color=line_color, linewidth=1.5)
            plt.title(f"{ticker} {company_name} - 1 Year Trend", fontsize=14)
            plt.grid(True, linestyle='--', alpha=0.5)
            plt.tight_layout()
            
            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            plt.close()
            
            send_to_discord(ticker, company_name, sector_en, close_price, pct, buf, summary, pe_ratio, div_yield)
            time.sleep(2) 
        except Exception as e:
            print(f"處理 {ticker} 時發生錯誤: {e}")

def main():
    # 擴充為 250 檔主要權值股 (140檔上海 .SS + 110檔深圳 .SZ)
    sh_tickers = [
        '600000', '600009', '600010', '600011', '600015', '600016', '600018', '600019', '600025', '600028',
        '600029', '600030', '600031', '600036', '600039', '600048', '600050', '600061', '600089', '600104',
        '600111', '600115', '600150', '600176', '600183', '600188', '600196', '600276', '600299', '600309',
        '600332', '600346', '600362', '600383', '600406', '600426', '600436', '600438', '600489', '600519',
        '600522', '600547', '600570', '600584', '600585', '600588', '600606', '600660', '600690', '600703',
        '600732', '600741', '600745', '600754', '600760', '600795', '600803', '600809', '600837', '600848',
        '600863', '600887', '600893', '600900', '600905', '600918', '600919', '600941', '600958', '600989',
        '600999', '601006', '601009', '601012', '601066', '601088', '601100', '601111', '601117', '601138',
        '601155', '601166', '601169', '601186', '601211', '601225', '601231', '601238', '601288', '601318',
        '601319', '601328', '601336', '601377', '601390', '601398', '601555', '601600', '601601', '601618',
        '601628', '601633', '601658', '601668', '601688', '601689', '601698', '601728', '601766', '601788',
        '601800', '601808', '601816', '601818', '601838', '601857', '601877', '601881', '601888', '601898',
        '601899', '601901', '601916', '601939', '601988', '601989', '601995', '601998', '603160', '603259',
        '603260', '603288', '603392', '603486', '603501', '603658', '603806', '603833', '603899', '603986'
    ]
    sz_tickers = [
        '000001', '000002', '000063', '000069', '000100', '000157', '000166', '000301', '000333', '000338',
        '000408', '000425', '000538', '000568', '000596', '000625', '000630', '000651', '000708', '000725',
        '000733', '000768', '000776', '000786', '000792', '000800', '000858', '000876', '000895', '000938',
        '000963', '000977', '000999', '001979', '002001', '002007', '002027', '002044', '002049', '002050',
        '002064', '002120', '002128', '002129', '002142', '002152', '002157', '002179', '002180', '002202',
        '002230', '002236', '002241', '002242', '002250', '002252', '002271', '002304', '002311', '002352',
        '002371', '002384', '002410', '002415', '002422', '002459', '002460', '002466', '002475', '002493',
        '002555', '002594', '002602', '002607', '002624', '002714', '002736', '002812', '002821', '002841',
        '002916', '002920', '002938', '003816', '300014', '300015', '300033', '300059', '300122', '300124',
        '300142', '300207', '300274', '300316', '300347', '300408', '300413', '300433', '300450', '300454',
        '300498', '300601', '300628', '300677', '300750', '300759', '300760', '300782', '300896', '300919'
    ]
    
    tickers = [f"{t}.SS" for t in sh_tickers] + [f"{t}.SZ" for t in sz_tickers]
    
    print(f"共載入 {len(tickers)} 檔滬深300權值股，正在下載股價資料...")
    data = yf.download(tickers, period="5d", progress=False)['Close']
    
    if data.empty:
        print("錯誤：無法下載資料")
        return

    returns = data.pct_change().iloc[-1].dropna()
    
    gainers = returns[returns > 0]
    losers = returns[returns < 0]
    
    top_10_gainers = gainers.nlargest(10)
    top_10_losers = losers.nsmallest(10)
    
    process_and_send_list(top_10_gainers, "今日 滬深300 (Top 250) 漲幅前十名個股報告", '#1f77b4')
    process_and_send_list(top_10_losers, "今日 滬深300 (Top 250) 跌幅最重個股報告", 'green')

if __name__ == "__main__":
    main()
