# ============================================================
# GOLD COT + SUPPLY & DEMAND BACKTEST
# Period: 2020 - 2026 (as close to today as possible)
# COT: Real CFTC data — Large Specs + Commercials
# S&D: Swing Demand Zones + Bullish Confirmation
# Direction: LONG only | RR: 1:3 | Risk: 1% per trade
# ============================================================

# !pip install yfinance pandas numpy matplotlib requests

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import requests, zipfile, io, warnings
from datetime import datetime, timedelta
warnings.filterwarnings('ignore')

TODAY     = datetime.today().strftime('%Y-%m-%d')
START_DATE = '2020-01-01'

print("=" * 60)
print("  GOLD COT + S&D BACKTEST — 2020 to TODAY")
print(f"  Running to: {TODAY}")
print("  COT: Real CFTC | S&D: Swing Demand | RR: 1:3")
print("=" * 60)

# ============================================================
# STEP 1: GOLD PRICE DATA
# ============================================================
print(f"\n[1/6] Downloading Gold data {START_DATE} → {TODAY}...")
df = yf.download("GC=F", start=START_DATE, end=TODAY, interval="1d")
df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
df = df[['Open','High','Low','Close','Volume']].dropna()
df.index = pd.to_datetime(df.index)
print(f"      Loaded: {len(df)} candles ({df.index[0].date()} → {df.index[-1].date()})")
actual_years = (df.index[-1] - df.index[0]).days / 365.25

# ============================================================
# STEP 2: COT DATA — ALL YEARS 2019-2025 + 2026 attempt
# ============================================================
print("\n[2/6] Downloading CFTC COT data...")

def download_cot(year):
    url = f"https://www.cftc.gov/files/dea/history/fut_fin_txt_{year}.zip"
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            z = zipfile.ZipFile(io.BytesIO(r.content))
            with z.open(z.namelist()[0]) as f:
                return pd.read_csv(f, low_memory=False)
    except:
        pass
    return None

all_cot = []
for year in range(2019, 2027):
    data = download_cot(year)
    if data is not None:
        all_cot.append(data)
        print(f"      {year}: {len(data)} rows")
    else:
        print(f"      {year}: not available yet")

# ============================================================
# STEP 3: PROCESS COT — FIND GOLD WITH MULTIPLE FALLBACKS
# ============================================================
print("\n[3/6] Processing COT signal...")
USE_REAL_COT = False
cot_signal   = None

if all_cot:
    raw = pd.concat(all_cot, ignore_index=True)
    print(f"      Total rows: {len(raw)}")

    # Try multiple Gold search strategies
    gold = pd.DataFrame()

    # Strategy 1: CFTC code 088691
    for col in raw.columns:
        if 'code' in col.lower():
            mask = raw[col].astype(str).str.contains('088691', na=False)
            if mask.sum() > 0:
                gold = raw[mask].copy()
                print(f"      Found via code 088691 in col '{col}': {len(gold)} rows")
                break

    # Strategy 2: Market name containing GOLD
    if len(gold) == 0:
        for col in raw.columns:
            if 'market' in col.lower() or 'name' in col.lower():
                mask = raw[col].astype(str).str.upper().str.contains('GOLD', na=False)
                if mask.sum() > 0:
                    gold = raw[mask].copy()
                    print(f"      Found via name '{col}': {len(gold)} rows")
                    print(f"      Unique names: {gold[col].unique()[:5]}")
                    break

    # Strategy 3: Any column with GOLD
    if len(gold) == 0:
        for col in raw.columns:
            mask = raw[col].astype(str).str.upper().str.contains('^GOLD', na=False)
            if mask.sum() > 0:
                gold = raw[mask].copy()
                print(f"      Found via '{col}': {len(gold)} rows")
                break

    if len(gold) > 0:
        # Find date column
        date_col = None
        for c in gold.columns:
            if 'date' in c.lower():
                try:
                    test = pd.to_datetime(gold[c].iloc[:5], errors='coerce')
                    if test.notna().sum() > 0:
                        date_col = c
                        break
                except:
                    pass

        if date_col:
            gold['date'] = pd.to_datetime(gold[date_col], errors='coerce')
            gold = gold.dropna(subset=['date']).sort_values('date').reset_index(drop=True)
            print(f"      Date range: {gold['date'].min().date()} → {gold['date'].max().date()}")

            # Find net position columns
            def find_col(df, keywords):
                for col in df.columns:
                    col_l = col.lower()
                    if all(k.lower() in col_l for k in keywords):
                        return col
                return None

            ls_l = find_col(gold, ['noncomm','long'])
            ls_s = find_col(gold, ['noncomm','short'])
            cm_l = find_col(gold, ['comm','long'])
            cm_s = find_col(gold, ['comm','short'])

            print(f"      LS Long: {ls_l} | LS Short: {ls_s}")
            print(f"      CM Long: {cm_l} | CM Short: {cm_s}")

            if all([ls_l, ls_s, cm_l, cm_s]):
                gold['ls_net'] = pd.to_numeric(gold[ls_l], errors='coerce') - \
                                  pd.to_numeric(gold[ls_s], errors='coerce')
                gold['cm_net'] = pd.to_numeric(gold[cm_l], errors='coerce') - \
                                  pd.to_numeric(gold[cm_s], errors='coerce')
                gold = gold.dropna(subset=['ls_net','cm_net'])

                # 52-week rolling percentile rank
                W = 52
                gold['ls_rank'] = gold['ls_net'].rolling(W).apply(
                    lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False)
                gold['cm_rank'] = gold['cm_net'].rolling(W).apply(
                    lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False)

                gold['ls_rising'] = gold['ls_net'].diff() > 0
                gold['cm_rising'] = gold['cm_net'].diff() > 0

                # Bullish: LS net in top 33% AND rising
                # Commercials contrarian: cm_net in BOTTOM 33% (most short) AND rising (reducing shorts)
                gold['ls_bull'] = (gold['ls_rank'] >= 0.67) & gold['ls_rising']
                gold['cm_bull'] = (gold['cm_rank'] <= 0.33) & gold['cm_rising']
                gold['cot_bull'] = gold['ls_bull'] & gold['cm_bull']

                cot_signal = gold.set_index('date')[['ls_net','cm_net',
                                                      'ls_rank','cm_rank',
                                                      'ls_bull','cm_bull','cot_bull']]
                USE_REAL_COT = True
                n_bull = gold['cot_bull'].sum()
                n_tot  = gold['cot_bull'].notna().sum()
                print(f"      COT bullish weeks: {n_bull}/{n_tot} ({n_bull/n_tot*100:.1f}%)")

# Synthetic fallback
if not USE_REAL_COT:
    print("      Using synthetic COT proxy (EMA trend)...")
    weekly   = df['Close'].resample('W').last()
    ema20    = weekly.ewm(span=20).mean()
    ema50    = weekly.ewm(span=50).mean()
    ls_net   = weekly - ema20
    cm_net   = ema20 - ema50
    ls_rank  = ls_net.rolling(52).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False)
    cm_rank  = cm_net.rolling(52).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False)
    ls_bull  = (ls_rank >= 0.67) & (ls_net.diff() > 0)
    cm_bull  = (cm_rank <= 0.33) & (cm_net.diff() > 0)
    cot_signal = pd.DataFrame({
        'ls_net': ls_net, 'cm_net': cm_net,
        'ls_rank': ls_rank, 'cm_rank': cm_rank,
        'ls_bull': ls_bull, 'cm_bull': cm_bull,
        'cot_bull': ls_bull & cm_bull
    }, index=weekly.index)
    n_bull = cot_signal['cot_bull'].sum()
    print(f"      Synthetic bullish weeks: {n_bull}/{len(cot_signal)} ({n_bull/len(cot_signal)*100:.1f}%)")

# Map weekly COT to daily bars
cot_daily = cot_signal['cot_bull'].reindex(df.index, method='ffill').fillna(False)
print(f"      COT mapped to {len(cot_daily)} daily bars")
print(f"      Source: {'Real CFTC' if USE_REAL_COT else 'Synthetic proxy'}")

# ============================================================
# STEP 4: SWING DEMAND ZONES
# ============================================================
print("\n[4/6] Detecting Swing Demand Zones...")

def calc_atr(df, p=14):
    tr = pd.concat([
        df['High'] - df['Low'],
        (df['High'] - df['Close'].shift()).abs(),
        (df['Low']  - df['Close'].shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(p).mean()

def get_demand_zones(df, window=5, mult=0.5):
    atr   = calc_atr(df)
    zones = []
    for i in range(window, len(df) - window):
        c = df.iloc[i]
        a = atr.iloc[i]
        if pd.isna(a) or a == 0:
            continue
        if c['Low'] == df['Low'].iloc[i-window:i+window+1].min():
            zones.append({
                'top': c['Low'] + mult * a,
                'bottom': c['Low'],
                'start_idx': i,
                'valid': True
            })
    return zones

zones = get_demand_zones(df)
print(f"      Zones: {len(zones)}")

# ============================================================
# STEP 5: BACKTEST
# ============================================================
print("\n[5/6] Running backtest...")

def bull_confirm(c):
    body = abs(c['Close'] - c['Open'])
    rng  = c['High'] - c['Low']
    if rng == 0: return False
    lw   = min(c['Open'], c['Close']) - c['Low']
    return ((body/rng > 0.6 and c['Close'] > c['Open']) or
            (lw > 2*body and c['Close'] > c['Open']))

def backtest(df, zones, cot_daily, rr=3.0, risk_pct=1.0, cap=10000):
    trades, capital, eq = [], cap, [cap]
    skipped = 0
    active  = [z.copy() for z in zones]

    for i in range(1, len(df)):
        cur  = df.iloc[i]
        date = df.index[i]

        if not cot_daily.iloc[i]:
            skipped += 1
            continue

        for z in active:
            if not z['valid'] or z['start_idx'] >= i:
                continue
            if not (cur['Low'] <= z['top'] and cur['Close'] >= z['bottom']):
                continue
            if not bull_confirm(cur):
                continue

            entry = cur['Close']
            sl    = z['bottom'] - (z['top'] - z['bottom']) * 0.1
            risk  = entry - sl
            if risk <= 0: continue
            tp    = entry + risk * rr
            size  = (capital * risk_pct / 100) / risk

            outcome = exit_p = exit_d = None
            for j in range(i+1, min(i+60, len(df))):
                f = df.iloc[j]
                if f['Low'] <= sl:
                    outcome, exit_p, exit_d = 'LOSS', sl, df.index[j]; break
                if f['High'] >= tp:
                    outcome, exit_p, exit_d = 'WIN',  tp, df.index[j]; break

            if outcome is None:
                k = min(i+59, len(df)-1)
                outcome, exit_p, exit_d = 'TIMEOUT', df.iloc[k]['Close'], df.index[k]

            pnl     = (exit_p - entry) * size
            capital += pnl
            eq.append(capital)

            trades.append({
                'entry_date': date, 'exit_date': exit_d,
                'entry': round(entry,2), 'sl': round(sl,2),
                'tp': round(tp,2), 'exit_price': round(exit_p,2),
                'outcome': outcome, 'pnl': round(pnl,2),
                'capital': round(capital,2)
            })
            z['valid'] = False
            break

    print(f"      Skipped (no COT): {skipped} / {len(df)}")
    return pd.DataFrame(trades), eq, capital

tdf, eq_curve, final_cap = backtest(df, zones, cot_daily)
print(f"      Trades executed: {len(tdf)}")

# ============================================================
# STEP 6: METRICS + CHARTS
# ============================================================
print("\n[6/6] Results...")

done  = tdf[tdf['outcome'].isin(['WIN','LOSS'])]
wins  = done[done['outcome']=='WIN']
loss  = done[done['outcome']=='LOSS']

n     = len(done)
wc    = len(wins)
lc    = len(loss)
wr    = wc/n*100 if n>0 else 0
pf    = wins['pnl'].sum()/abs(loss['pnl'].sum()) if loss['pnl'].sum()!=0 else float('inf')
aw    = wins['pnl'].mean() if wc>0 else 0
al    = loss['pnl'].mean() if lc>0 else 0
cap0  = 10000

eq_s  = pd.Series(eq_curve)
dd    = ((eq_s - eq_s.cummax()) / eq_s.cummax() * 100).min()
sr    = (done['pnl'].mean()/done['pnl'].std())*np.sqrt(252) if done['pnl'].std()!=0 else 0
ret   = (final_cap - cap0) / cap0 * 100
cagr  = ((final_cap/cap0)**(1/actual_years)-1)*100

print("\n" + "="*60)
print(f"  COT + S&D RESULTS — 2020 to {df.index[-1].date()}")
print("="*60)
print(f"  Total Trades       : {n}")
print(f"  Wins               : {wc}")
print(f"  Losses             : {lc}")
print(f"  Win Rate           : {wr:.1f}%  (breakeven = 25%)")
print(f"  Edge Above B/E     : +{wr-25:.1f}%")
print(f"  Profit Factor      : {pf:.2f}")
print(f"  Avg Win            : ${aw:,.2f}")
print(f"  Avg Loss           : ${al:,.2f}")
print(f"  Total PnL          : ${done['pnl'].sum():,.2f}")
print(f"  Starting Capital   : ${cap0:,.2f}")
print(f"  Final Capital      : ${final_cap:,.2f}")
print(f"  Total Return       : {ret:.1f}%")
print(f"  CAGR               : {cagr:.1f}%/year")
print(f"  Max Drawdown       : {dd:.1f}%")
print(f"  Sharpe Ratio       : {sr:.2f}")
print(f"  COT Source         : {'Real CFTC' if USE_REAL_COT else 'Synthetic proxy'}")
print("="*60)

# Yearly
print(f"\n  YEARLY BREAKDOWN:")
print(f"  {'Year':<8}{'Trades':>8}{'Wins':>6}{'Win%':>7}{'PnL':>13}")
print("  "+"-"*45)
done['year'] = pd.to_datetime(done['entry_date']).dt.year
for yr in sorted(done['year'].unique()):
    y  = done[done['year']==yr]
    yw = y[y['outcome']=='WIN']
    print(f"  {yr:<8}{len(y):>8}{len(yw):>6}{len(yw)/len(y)*100:>6.1f}%  ${y['pnl'].sum():>10,.2f}")

# ============================================================
# CHARTS
# ============================================================
fig, axes = plt.subplots(4, 1, figsize=(14, 20))
fig.patch.set_facecolor('#0d1117')
fig.suptitle(f'Gold COT + S&D | 2020–{df.index[-1].year} | {"Real CFTC" if USE_REAL_COT else "Synthetic COT"}',
             color='#f0c040', fontsize=13, fontweight='bold', y=0.99)

for ax in axes:
    ax.set_facecolor('#0d1117')
    ax.tick_params(colors='#c9d1d9', labelsize=8)
    for sp in ax.spines.values(): sp.set_color('#30363d')

# Chart 1: Price + COT shading + entries
ax1 = axes[0]
ax1.plot(df.index, df['Close'], color='#f0c040', lw=1.0, label='Gold', zorder=2)
prev, s0 = False, None
for date, val in cot_daily.items():
    if val and not prev: s0 = date
    elif not val and prev and s0:
        ax1.axvspan(s0, date, alpha=0.1, color='#44ff88', zorder=1)
        s0 = None
    prev = val
if s0: ax1.axvspan(s0, df.index[-1], alpha=0.1, color='#44ff88')

wt = done[done['outcome']=='WIN']
lt = done[done['outcome']=='LOSS']
ax1.scatter(pd.to_datetime(wt['entry_date']), wt['entry'], marker='^', color='#44ff88', s=60, zorder=5, label=f'Win ({wc})')
ax1.scatter(pd.to_datetime(lt['entry_date']), lt['entry'], marker='v', color='#ff4444', s=60, zorder=5, label=f'Loss ({lc})')
ax1.set_title('Gold Price + COT Bullish Periods (green) + Entries', color='#c9d1d9', fontsize=10, pad=8)
ax1.set_ylabel('Price (USD)', color='#c9d1d9')
ax1.legend(facecolor='#161b22', labelcolor='#c9d1d9', fontsize=8, loc='upper left')
ax1.grid(True, alpha=0.08, color='#30363d')

# Chart 2: COT net positions
ax2 = axes[1]
cs  = cot_signal.loc[START_DATE:]
if USE_REAL_COT:
    ax2.plot(cs.index, cs['ls_net'], color='#58a6ff', lw=1.2, label='Large Specs Net')
    ax2.plot(cs.index, cs['cm_net'], color='#ff9944', lw=1.2, label='Commercials Net')
    ax2.set_title('COT Net Positions — Large Speculators vs Commercials', color='#c9d1d9', fontsize=10, pad=8)
    ax2.set_ylabel('Net Contracts', color='#c9d1d9')
else:
    ax2.plot(cs.index, cs['ls_net'], color='#58a6ff', lw=1.2, label='EMA Spread (LS proxy)')
    ax2.plot(cs.index, cs['cm_net'], color='#ff9944', lw=1.2, label='EMA Diff (CM proxy)')
    ax2.set_title('Synthetic COT Proxy — EMA Trend Signals', color='#c9d1d9', fontsize=10, pad=8)
    ax2.set_ylabel('Value', color='#c9d1d9')
ax2.axhline(0, color='#8b949e', lw=0.8, ls='--')
ax2.legend(facecolor='#161b22', labelcolor='#c9d1d9', fontsize=8)
ax2.grid(True, alpha=0.08, color='#30363d')

# Chart 3: Equity curve
ax3 = axes[2]
ax3.plot(range(len(eq_s)), eq_s.values, color='#44ff88', lw=2.0, zorder=3)
ax3.fill_between(range(len(eq_s)), cap0, eq_s.values,
                 where=(eq_s>=cap0), alpha=0.15, color='#44ff88')
ax3.fill_between(range(len(eq_s)), cap0, eq_s.values,
                 where=(eq_s<cap0),  alpha=0.15, color='#ff4444')
ax3.axhline(cap0, color='#8b949e', ls='--', lw=0.8, label='$10,000 Start')
ax3.annotate(f'${final_cap:,.0f}',
             xy=(len(eq_s)-1, final_cap),
             xytext=(-90,15), textcoords='offset points',
             color='#44ff88', fontsize=9,
             arrowprops=dict(arrowstyle='->', color='#44ff88', lw=1))
ax3.set_title(f'Equity Curve | Return: {ret:.1f}% | CAGR: {cagr:.1f}%/yr | Max DD: {dd:.1f}%',
              color='#c9d1d9', fontsize=10, pad=8)
ax3.set_ylabel('Capital (USD)', color='#c9d1d9')
ax3.legend(facecolor='#161b22', labelcolor='#c9d1d9', fontsize=8)
ax3.grid(True, alpha=0.08, color='#30363d')

# Chart 4: Yearly PnL
ax4    = axes[3]
yearly = done.groupby('year')['pnl'].sum()
bc     = ['#44ff88' if v>=0 else '#ff4444' for v in yearly.values]
bars   = ax4.bar(yearly.index, yearly.values, color=bc, width=0.5, zorder=3)
for b, v in zip(bars, yearly.values):
    ax4.text(b.get_x()+b.get_width()/2,
             b.get_height()+(80 if v>=0 else -250),
             f'${v:,.0f}', ha='center', va='bottom', color='#c9d1d9', fontsize=8)
ax4.axhline(0, color='#8b949e', lw=0.8)
ax4.set_title('Yearly PnL', color='#c9d1d9', fontsize=10, pad=8)
ax4.set_ylabel('PnL (USD)', color='#c9d1d9')
ax4.set_xticks(yearly.index)
ax4.grid(True, alpha=0.08, color='#30363d', axis='y')

plt.tight_layout(rect=[0,0,1,0.98], pad=2.5)
plt.savefig('gold_cot_sd_2020_2026.png', dpi=150, bbox_inches='tight', facecolor='#0d1117')
plt.show()
print("\n  Chart: gold_cot_sd_2020_2026.png")
tdf.to_csv('gold_cot_sd_2020_2026_trades.csv', index=False)
print("  Trades: gold_cot_sd_2020_2026_trades.csv")
print("\n  COMPLETE.")