"""EDGAR PRisk: Hassan et al. eq. (1) on the primary document of each 10-K / 10-Q (definition: progress.md, EDGAR PRisk).

Run from the repo root:
  SEC_USER_AGENT="First Last you@school.edu" python signals/prisk/pull_prisk_edgar.py [--pilot] [--mdna]
The User-Agent (sec.gov returns 403 without a contact) is read from the environment; it is not saved.
In:  data/prisk/edgar/filings.parquet, ciklink.parquet, universe_gvkeys.parquet, political_bigrams.csv
Out: data/prisk/edgar/scores[_pilot].csv (one row per filing; resumable, appends)
Text is scored in memory and not stored. At most 8 requests/s (SEC limit 10).
"""
import argparse, csv, gzip, html, os, re, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np, pandas as pd

D = Path('data/prisk/edgar')
FORMS = {'10-K', '10-K405', '10-Q'}
SYN = set('''risk risks uncertainty variable chance possibility pending uncertainties uncertain doubt prospect bet variability exposed
likelihood threat probability unknown varying unclear unpredictable speculative fear reservation hesitant gamble risky instability
doubtful hazard tricky sticky dangerous tentative hazardous queries danger fluctuating unstable vague erratic query jeopardize unsettled
unpredictability dilemma skepticism hesitancy riskier unresolved unsure irregular jeopardy suspicion risking peril hesitating risked
unreliable unsafe hazy apprehension unforeseeable halting wager torn precarious undetermined insecurity debatable undecided dicey
indecision wavering iffy faltering endanger quandary insecure changeable riskiest hairy ambivalent dubious riskiness treacherous
oscillating perilous tentativeness unreliability wariness vagueness dodgy equivocation indecisive chancy menace qualm vacillating gnarly
disquiet ambivalence imperil vacillation incalculable untrustworthy equivocating diffident fickleness misgiving changeability
undependable incertitude fitful parlous unconfident defenseless unsureness fluctuant niggle diffidence precariousness doubtfulness'''.split())
WIN, RATE, COLS = 10, 8.0, ['cik', 'accession', 'form', 'fdate', 'rdate', 'secadate', 'doc', 'n_words', 'n_bigrams', 'n_syn',
                             'n_pol', 'n_pol_near', 'eprisk', 'eprisk_count', 'erisk', 'status']

class Limiter:
  """Shared rate limit across threads."""
  def __init__(self, rate):
    self.gap, self.next, self.lock = 1 / rate, time.monotonic(), threading.Lock()
  def wait(self):
    with self.lock:
      t = max(self.next, time.monotonic()); self.next = t + self.gap
    time.sleep(max(0, t - time.monotonic()))

def get(url, agent, lim, tries=4):
  """GET with rate limit and retry on 429/5xx."""
  for k in range(tries):
    lim.wait()
    try:
      req = urllib.request.Request(url, headers={'User-Agent': agent, 'Accept-Encoding': 'gzip'})
      with urllib.request.urlopen(req, timeout=60) as r:
        b = r.read()
        return (gzip.decompress(b) if r.headers.get('Content-Encoding') == 'gzip' else b).decode('latin-1')
    except urllib.error.HTTPError as e:
      if e.code == 404:
        return None
      time.sleep(2 ** k * (5 if e.code == 429 else 1))
    except Exception:
      time.sleep(2 ** k)
  return None

def primary_doc(cik, acc, form, agent, lim):
  """URL of the main 10-K/10-Q document from the filing index page."""
  base = f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace("-", "")}/'
  idx = get(base + f'{acc}-index.htm', agent, lim)
  if idx is None:
    return None
  for row in re.findall(r'<tr[^>]*>(.*?)</tr>', idx, re.S | re.I):
    cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S | re.I)
    href = re.search(r'href="([^"]+)"', row)
    if len(cells) >= 4 and href and re.sub('<[^>]+>', '', cells[3]).strip() in FORMS:
      h = href.group(1).replace('/ix?doc=', '')
      return 'https://www.sec.gov' + h if h.startswith('/') else base + h
  return None

def tokens(raw):
  """HTML/SGML -> lowercase tokens, punctuation removed (paper: 'after removing all punctuation')."""
  t = re.sub(r'<(script|style|ix:header)[^>]*>.*?</\1>', ' ', raw, flags=re.S | re.I)
  t = html.unescape(re.sub(r'<[^>]+>', ' ', t)).lower()
  t = re.sub(r"[^\w\s]", '', t.replace('\xa0', ' '))
  return t.split()

START = ['managements', 'discussion', 'and', 'analysis']
ENDS = [['quantitative', 'and', 'qualitative', 'disclosures'], ['financial', 'statements', 'and', 'supplementary'], ['controls', 'and', 'procedures']]

def find(tok, phrase):
  """Start positions of a token phrase."""
  k = len(phrase)
  return [i for i in range(len(tok) - k + 1) if tok[i] == phrase[0] and tok[i:i + k] == phrase]

def mdna(tok):
  """MD&A span: the start heading with the longest run to the next end heading (skips the table of contents)."""
  ends = sorted(j for e in ENDS for j in find(tok, e))
  best = (0, 0)
  for i in find(tok, START):
    j = next((j for j in ends if j > i), len(tok))
    if j - i > best[1] - best[0]:
      best = (i, j)
  return tok[best[0]:best[1]]

def score(tok, W):
  """Eq. (1): weighted political bigrams within WIN words of a risk synonym, over the number of bigrams."""
  n = len(tok) - 1
  if n < 100:
    return dict(n_words=len(tok), n_bigrams=max(n, 0), status='short')
  s = np.flatnonzero(np.fromiter((w in SYN for w in tok), bool, len(tok)))
  w = np.fromiter((W.get(tok[j] + '_' + tok[j + 1], 0.0) for j in range(n)), float, n)
  pol = np.flatnonzero(w)
  if len(s) and len(pol):
    k = np.clip(np.searchsorted(s, pol), 1, len(s)) - 1
    d = np.minimum(np.abs(pol - s[k]), np.abs(pol - s[np.minimum(k + 1, len(s) - 1)]))
    near = pol[d < WIN]
  else:
    near = np.array([], int)
  return dict(n_words=len(tok), n_bigrams=n, n_syn=len(s), n_pol=len(pol), n_pol_near=len(near),
              eprisk=w[near].sum() / n, eprisk_count=len(near) / n, erisk=len(s) / n, status='ok')

def todo(pilot):
  """Universe filings, CIK link valid at the filing date, minus those already scored."""
  f = pd.read_parquet(D / 'filings.parquet')
  f = f[f['form'].isin(FORMS)]
  l = pd.read_parquet(D / 'ciklink.parquet')
  l['gvkey'] = l['gvkey'].astype(str).str.zfill(6)
  u = pd.read_parquet(D / 'universe_gvkeys.parquet')['gvkey']
  if pilot:
    u = u.sample(50, random_state=0)
  l = l[l['gvkey'].isin(u)]
  m = f.merge(l[['cik', 'gvkey', 'link_start_date', 'link_end_date']], on='cik')
  fd = pd.to_datetime(m['fdate'])
  m = m[(fd >= pd.to_datetime(m['link_start_date']).fillna(pd.Timestamp('1900-01-01'))) &
        (fd <= pd.to_datetime(m['link_end_date']).fillna(pd.Timestamp('2100-01-01')))]
  if pilot:
    m = m[(fd.loc[m.index] >= '2015-01-01') & (fd.loc[m.index] <= '2019-12-31')]
  m = m.drop_duplicates('accession')
  return m.sort_values(['form', 'fdate'])      # 10-K / 10-K405 first, then 10-Q

if __name__ == '__main__':
  a = argparse.ArgumentParser()
  a.add_argument('--pilot', action='store_true'); a.add_argument('--mdna', action='store_true'); a.add_argument('--threads', type=int, default=16)
  args = a.parse_args()
  agent, lim = os.environ['SEC_USER_AGENT'], Limiter(RATE)
  out = D / (('scores_pilot' if args.pilot else 'scores') + ('_mdna' if args.mdna else '') + '.csv')
  done = set(pd.read_csv(out, usecols=['accession'])['accession']) if out.exists() else set()
  m = todo(args.pilot)
  m = m[~m['accession'].isin(done)]
  W = pd.read_csv(D / 'political_bigrams.csv').set_index('bigram')['politicaltbb'].astype(float).to_dict()
  print(f'{len(m):,} filings to score ({len(done):,} already done) -> {out}', flush=True)
  lock, fh = threading.Lock(), open(out, 'a', newline='')
  wr = csv.DictWriter(fh, COLS)
  if not done:
    wr.writeheader()

  def one(r):
    """Fetch, score and append one filing."""
    row = dict(cik=r.cik, accession=r.accession, form=r.form, fdate=r.fdate, rdate=r.rdate, secadate=r.secadate)
    doc = primary_doc(r.cik, r.accession, r.form, agent, lim)
    raw = get(doc, agent, lim) if doc else None
    row.update(doc=doc, **(score((mdna if args.mdna else list)(tokens(raw)), W) if raw else dict(status='no_doc' if doc is None else 'fetch_fail')))
    with lock:
      wr.writerow(row); fh.flush()

  t0 = time.time()
  with ThreadPoolExecutor(args.threads) as ex:
    for i, _ in enumerate(ex.map(one, m.itertuples(index=False)), 1):
      if i % 500 == 0:
        print(f'{i:,}/{len(m):,} in {(time.time() - t0) / 60:.0f} min', flush=True)
  fh.close()
  print('done', out)
