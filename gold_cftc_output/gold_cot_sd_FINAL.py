# ============================================================
# GOLD COT + S&D BACKTEST — CLEAN REBUILD
# Period: 2020 - Today
# ============================================================

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import requests, zipfile, io, warnings
from datetime import datetime
warnings.filterwarnings('ignore')

TODAY      = datetime.today().strftime('%Y-%m-%d')
START_DATE = '2020-01-01'

print("=" * 60)
print("  GOLD COT + S&D FINAL BACKTEST v2")
print(f"  Period: {START_DATE} to {TODAY}")
print("=" * 60)

# ============================================================
# 1. GOLD PRICE
# ============================================================
print("\n[1/6] Downloading Gold price data...")
df = yf.download("GC=F", start=START_DATE, end=TODAY, interval="1d")
df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
df = df[['Open','High','Low','Close','Volume']].dropna()
df.index = pd.to_datetime(df.index)
print(f"      {len(df)} candles | {df.index[0].date()} to {df.index[-1].date()}")
actual_years = (df.index[-1] - df.index[0]).days / 365.25

# ============================================================
# 2. DOWNLOAD COT
# ============================================================
print("\n[2/6] Downloading CFTC Disaggregated COT data...")

def get_cot(year):
    url = f"https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip"
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            z = zipfile.ZipFile(io.BytesIO(r.content))
            with z.open(z.namelist()[0]) as f:
                return pd.read_csv(f, low_memory=False)
    except: pass
    return None

frames = []
for yr in range(2019, 2027):
    d = get_cot(yr)
    if d is not None:
        frames.append(d)
        print(f"      {yr}: {len(d)} rows")
    else:
        print(f"      {yr}: not available")

raw = pd.concat(frames, ignore_index=True)
print(f"      Total: {len(raw)} rows")

# ============================================================
# 3. EXTRACT GOLD + BUILD COT SIGNAL
# ============================================================
print("\n[3/6] Building COT signal...")

# Filter Gold
gold = raw[raw['Market_and_Exchange_Names'].str.upper().str.contains('GOLD - COMMODITY', na=False)].copy()
print(f"      Gold rows: {len(gold)}")

# Parse date
gold['date'] = pd.to_datetime(gold['As_of_Date_In_Form_YYMMDD'].astype(str).str.zfill(6), format='%y%m%d', errors='coerce')
gold = gold.dropna(subset=['date']).sort_values('date').drop_duplicates('date').reset_index(drop=True)
print(f"      Date range: {gold['date'].min().date()} to {gold['date'].max().date()}")

# Find position columns
def fc(df, kws):
    for c in df.columns:
        if all(k.lower() in c.lower() for k in kws):
            return c
    return None

mm_l = fc(gold, ['money','long'])
mm_s = fc(gold, ['money','short'])
pm_l = fc(gold, ['prod','long'])
pm_s = fc(gold, ['prod','short'])

print(f"      MM Long={mm_l} | MM Short={mm_s}")
print(f"      PM Long={pm_l} | PM Short={pm_s}")

# Calculate net positions
gold['mm_net'] = pd.to_numeric(gold[mm_l], errors='coerce') - pd.to_numeric(gold[mm_s], errors='coerce')
gold['pm_net'] = pd.to_numeric(gold[pm_l], errors='coerce') - pd.to_numeric(gold[pm_s], errors='coerce')
gold = gold.dropna(subset=['mm_net','pm_net'])

# Simple signal: both net positions rising week over week
gold['mm_rising'] = gold['mm_net'].diff() > 0
gold['pm_rising'] = gold['pm_net'].diff() > 0
gold['cot_bull']  = gold['mm_rising'] & gold['pm_rising']

print(f"      COT bullish weeks: {gold['cot_bull'].sum()} / {len(gold)}")
print(f"      MM net: {gold['mm_net'].min():,.0f} to {gold['mm_net'].max():,.0f}")
print(f"      PM net: {gold['pm_net'].min():,.0f} to {gold['pm_net'].max():,.0f}")

# ============================================================
# 4. MAP COT TO DAILY BARS
# ============================================================
gold_indexed = gold.set_index('date')['cot_bull']
# Remove any remaining duplicates
gold_indexed = gold_indexed[~gold_indexed.index.duplicated(keep='last')]
# Reindex to daily price index
cot_daily = gold_indexed.reindex(df.index, method='ffill').fillna(False)
print(f"      COT bullish days: {cot_daily.sum()} / {len(cot_daily)} ({cot_daily.sum()/len(cot_daily)*100:.1f}%)")

# ============================================================
# 5. SWING DEMAND ZONES
# ============================================================
print("\n[4/6] Detecting Swing Demand Zones...")

def calc_atr(df, p=14):
    tr = pd.concat([
        df['High'] - df['Low'],
        (df['High'] - df['Close'].shift()).abs(),
        (df['Low']  - df['Close'].shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(p).mean()

def get_zones(df, window=5, mult=0.5):
    atr   = calc_atr(df)
    zones = []
    for i in range(window, len(df) - window):
        c = df.iloc[i]
        a = atr.iloc[i]
        if pd.isna(a) or a == 0: continue
        if c['Low'] == df['Low'].iloc[i-window:i+window+1].min():
            zones.append({'top': c['Low']+mult*a, 'bottom': c['Low'],
                          'start_idx': i, 'valid': True})
    return zones

zones = get_zones(df)
print(f"      Zones: {len(zones)}")

# ============================================================
# 6. BACKTEST
# ============================================================
print("\n[5/6] Running backtest...")

def bull_confirm(c):
    body = abs(c['Close'] - c['Open'])
    rng  = c['High'] - c['Low']
    if rng == 0: return False
    lw = min(c['Open'], c['Close']) - c['Low']
    return ((body/rng > 0.6 and c['Close'] > c['Open']) or
            (lw > 2*body    and c['Close'] > c['Open']))

trades, capital, eq = [], 10000, [10000]
skipped = 0
active  = [z.copy() for z in zones]

for i in range(1, len(df)):
    cur  = df.iloc[i]
    date = df.index[i]

    if not cot_daily.iloc[i]:
        skipped += 1
        continue

    for z in active:
        if not z['valid'] or z['start_idx'] >= i: continue
        if not (cur['Low'] <= z['top'] and cur['Close'] >= z['bottom']): continue
        if not bull_confirm(cur): continue

        entry = cur['Close']
        sl    = z['bottom'] - (z['top'] - z['bottom']) * 0.1
        risk  = entry - sl
        if risk <= 0: continue
        tp   = entry + risk * 3.0
        size = (capital * 0.01) / risk

        outcome = exit_p = exit_d = None
        for j in range(i+1, min(i+60, len(df))):
            f = df.iloc[j]
            if f['Low'] <= sl:
                outcome, exit_p, exit_d = 'LOSS', sl, df.index[j]; break
            if f['High'] >= tp:
                outcome, exit_p, exit_d = 'WIN', tp, df.index[j]; break

        if outcome is None:
            k = min(i+59, len(df)-1)
            outcome, exit_p, exit_d = 'TIMEOUT', df.iloc[k]['Close'], df.index[k]

        pnl      = (exit_p - entry) * size
        capital += pnl
        eq.append(capital)

        trades.append({'entry_date': date, 'exit_date': exit_d,
                       'entry': round(entry,2), 'sl': round(sl,2),
                       'tp': round(tp,2), 'exit_price': round(exit_p,2),
                       'outcome': outcome, 'pnl': round(pnl,2),
                       'capital': round(capital,2)})
        z['valid'] = False
        break

print(f"      Skipped (no COT): {skipped} / {len(df)}")
print(f"      Trades: {len(trades)}")

# ============================================================
# 7. RESULTS
# ============================================================
print("\n[6/6] Results...")

tdf  = pd.DataFrame(trades)
cap0 = 10000

if len(tdf) == 0:
    print("No trades generated.")
else:
    done = tdf[tdf['outcome'].isin(['WIN','LOSS'])]
    wins = done[done['outcome']=='WIN']
    loss = done[done['outcome']=='LOSS']

    n   = len(done)
    wc  = len(wins)
    lc  = len(loss)
    wr  = wc/n*100 if n>0 else 0
    pf  = wins['pnl'].sum()/abs(loss['pnl'].sum()) if loss['pnl'].sum()!=0 else float('inf')
    aw  = wins['pnl'].mean() if wc>0 else 0
    al  = loss['pnl'].mean() if lc>0 else 0

    eq_s = pd.Series(eq)
    dd   = ((eq_s - eq_s.cummax()) / eq_s.cummax() * 100).min()
    sr   = (done['pnl'].mean()/done['pnl'].std())*np.sqrt(252) if done['pnl'].std()!=0 else 0
    ret  = (capital - cap0) / cap0 * 100
    cagr = ((capital/cap0)**(1/actual_years)-1)*100

    print("\n" + "="*60)
    print(f"  RESULTS — 2020 to {df.index[-1].date()}")
    print(f"  COT: REAL CFTC DISAGGREGATED DATA")
    print("="*60)
    print(f"  Total Trades    : {n}")
    print(f"  Wins            : {wc}")
    print(f"  Losses          : {lc}")
    print(f"  Win Rate        : {wr:.1f}%  (breakeven = 25%)")
    print(f"  Edge Above B/E  : +{wr-25:.1f}%")
    print(f"  Profit Factor   : {pf:.2f}")
    print(f"  Avg Win         : ${aw:,.2f}")
    print(f"  Avg Loss        : ${al:,.2f}")
    print(f"  Total PnL       : ${done['pnl'].sum():,.2f}")
    print(f"  Final Capital   : ${capital:,.2f}")
    print(f"  Total Return    : {ret:.1f}%")
    print(f"  CAGR            : {cagr:.1f}%/year")
    print(f"  Max Drawdown    : {dd:.1f}%")
    print(f"  Sharpe Ratio    : {sr:.2f}")
    print("="*60)

    # Yearly
    print(f"\n  {'Year':<8}{'Trades':>8}{'Wins':>6}{'Win%':>7}{'PnL':>13}")
    print("  "+"-"*44)
    done['year'] = pd.to_datetime(done['entry_date']).dt.year
    for yr in sorted(done['year'].unique()):
        y  = done[done['year']==yr]
        yw = y[y['outcome']=='WIN']
        print(f"  {yr:<8}{len(y):>8}{len(yw):>6}{len(yw)/len(y)*100:>6.1f}%  ${y['pnl'].sum():>10,.2f}")

    # Charts
    fig, axes = plt.subplots(3, 1, figsize=(14, 15))
    fig.patch.set_facecolor('#0d1117')
    fig.suptitle(f'Gold COT+S&D | Real CFTC | 2020–{df.index[-1].year} | Long Only | 1:3 RR',
                 color='#f0c040', fontsize=13, fontweight='bold', y=0.99)

    for ax in axes:
        ax.set_facecolor('#0d1117')
        ax.tick_params(colors='#c9d1d9', labelsize=8)
        for sp in ax.spines.values(): sp.set_color('#30363d')

    ax1 = axes[0]
    ax1.plot(df.index, df['Close'], color='#f0c040', lw=1.0, label='Gold')
    prev, s0 = False, None
    for date, val in cot_daily.items():
        if val and not prev: s0 = date
        elif not val and prev and s0:
            ax1.axvspan(s0, date, alpha=0.1, color='#44ff88'); s0=None
        prev = val
    if s0: ax1.axvspan(s0, df.index[-1], alpha=0.1, color='#44ff88')
    wt = done[done['outcome']=='WIN']
    lt = done[done['outcome']=='LOSS']
    ax1.scatter(pd.to_datetime(wt['entry_date']), wt['entry'], marker='^', color='#44ff88', s=70, zorder=5, label=f'Win ({wc})')
    ax1.scatter(pd.to_datetime(lt['entry_date']), lt['entry'], marker='v', color='#ff4444', s=70, zorder=5, label=f'Loss ({lc})')
    ax1.set_title('Gold + COT Bullish Windows (green) + Entries', color='#c9d1d9', fontsize=10)
    ax1.set_ylabel('Price (USD)', color='#c9d1d9')
    ax1.legend(facecolor='#161b22', labelcolor='#c9d1d9', fontsize=8)
    ax1.grid(True, alpha=0.08, color='#30363d')

    ax2 = axes[1]
    eq_s = pd.Series(eq)
    ax2.plot(range(len(eq_s)), eq_s.values, color='#44ff88', lw=2.0)
    ax2.fill_between(range(len(eq_s)), cap0, eq_s.values, where=(eq_s>=cap0), alpha=0.15, color='#44ff88')
    ax2.fill_between(range(len(eq_s)), cap0, eq_s.values, where=(eq_s<cap0),  alpha=0.15, color='#ff4444')
    ax2.axhline(cap0, color='#8b949e', ls='--', lw=0.8)
    ax2.set_title(f'Equity Curve | Return:{ret:.1f}% | CAGR:{cagr:.1f}%/yr | MaxDD:{dd:.1f}%', color='#c9d1d9', fontsize=10)
    ax2.set_ylabel('Capital (USD)', color='#c9d1d9')
    ax2.grid(True, alpha=0.08, color='#30363d')

    ax3 = axes[2]
    yearly = done.groupby('year')['pnl'].sum()
    bc = ['#44ff88' if v>=0 else '#ff4444' for v in yearly.values]
    bars = ax3.bar(yearly.index, yearly.values, color=bc, width=0.5, zorder=3)
    for b,v in zip(bars, yearly.values):
        ax3.text(b.get_x()+b.get_width()/2, b.get_height()+(50 if v>=0 else -200),
                 f'${v:,.0f}', ha='center', color='#c9d1d9', fontsize=9)
    ax3.axhline(0, color='#8b949e', lw=0.8)
    ax3.set_title('Yearly PnL', color='#c9d1d9', fontsize=10)
    ax3.set_ylabel('PnL (USD)', color='#c9d1d9')
    ax3.set_xticks(yearly.index)
    ax3.grid(True, alpha=0.08, color='#30363d', axis='y')

    plt.tight_layout(rect=[0,0,1,0.98], pad=2.5)
    plt.savefig('gold_FINAL_v2.png', dpi=150, bbox_inches='tight', facecolor='#0d1117')
    plt.show()

    tdf.to_csv('gold_FINAL_v2_trades.csv', index=False)
    print("\n  Chart: gold_FINAL_v2.png")
    print("  Trades: gold_FINAL_v2_trades.csv")
    print("\n  COMPLETE.")