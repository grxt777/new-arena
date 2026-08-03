#!/usr/bin/env python3
import hashlib, json, logging, re, shutil, sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parent
INCOMING,ARCHIVE,REJECTED,LOGS=[ROOT/x for x in ('data/incoming','data/archive','data/rejected','logs')]
DB=ROOT/'atm_forecast.db'; CONFIG=json.loads((ROOT/'config/columns.json').read_text(encoding='utf-8')); SETTINGS=json.loads((ROOT/'config/settings.json').read_text(encoding='utf-8'))
for p in (INCOMING,ARCHIVE,REJECTED,LOGS): p.mkdir(parents=True,exist_ok=True)
logging.basicConfig(filename=LOGS/'importer.log',level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
SCHEMA='''
CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY,filename TEXT,sha256 TEXT UNIQUE,imported_at TEXT,status TEXT,error TEXT);
CREATE TABLE IF NOT EXISTS snapshots(id INTEGER PRIMARY KEY,file_id INTEGER,atm_id TEXT NOT NULL,serial_number TEXT,reported_at TEXT NOT NULL,collected_at TEXT NOT NULL,cash_total REAL,cash_total_usd REAL,status TEXT,address TEXT,city TEXT,latitude REAL,longitude REAL,raw_json TEXT,UNIQUE(atm_id,reported_at,file_id));
CREATE TABLE IF NOT EXISTS cassettes(id INTEGER PRIMARY KEY,snapshot_id INTEGER,cassette_no INTEGER,status TEXT,currency TEXT,denomination REAL,note_count INTEGER,amount REAL);
CREATE INDEX IF NOT EXISTS ix_snapshots_atm_time ON snapshots(atm_id,reported_at);
'''
def db():
 c=sqlite3.connect(DB); c.execute('PRAGMA journal_mode=WAL'); c.executescript(SCHEMA); return c
def norm(v): return str(v).strip().casefold().replace('ё','е').replace('\n',' ').replace('—','-') if pd.notna(v) else ''
def flat_columns(df):
 out=[]
 for c in df.columns:
  if isinstance(c,tuple):
   parts=[str(x).strip() for x in c if str(x).strip() and str(x).lower()!='nan']
   out.append(' '.join(parts))
  else: out.append(str(c).strip())
 df=df.copy(); df.columns=out; return df
def choose(df,names,required=False):
 normalized={norm(c).replace('|',' '):c for c in df.columns}
 for name in names:
  key=norm(name).replace('|',' ')
  if key in normalized:return normalized[key]
 # fallback: match a column that contains the requested phrase
 for name in names:
  key=norm(name).replace('|',' ')
  for n,c in normalized.items():
   if key and (key in n or n in key): return c
 if required: raise ValueError(f'Не найдена обязательная колонка: {names}')
 return None
def read_report(path):
 if path.suffix.lower()=='.csv':
  for enc in ('utf-8-sig','cp1251','utf-8'):
   try:return flat_columns(pd.read_csv(path,encoding=enc,sep=None,engine='python'))
   except UnicodeDecodeError:continue
  raise ValueError('Не удалось определить кодировку CSV')
 if path.suffix.lower() in ('.xlsx','.xlsm'):
  first=flat_columns(pd.read_excel(path,sheet_name=CONFIG.get('sheet_name',0),header=0))
  try: choose(first,CONFIG['columns']['atm_id'],True); choose(first,CONFIG['columns']['cash_total_uzs'],True); return first
  except ValueError:
   return flat_columns(pd.read_excel(path,sheet_name=CONFIG.get('sheet_name',0),header=1))
 raise ValueError('Поддерживаются только CSV и XLSX/XLSM')
def parse_time(value,fallback):
 if value is None or pd.isna(value) or str(value).strip()=='':return fallback
 t=pd.to_datetime(value,dayfirst=True,errors='coerce')
 if pd.isna(t):return fallback
 if getattr(t,'tzinfo',None) is None:t=t.tz_localize('Asia/Tashkent')
 return t.tz_convert('UTC').isoformat()
def filename_time(path, fallback):
 m=re.search(r'(20\d{2}-\d{2}-\d{2})[_ -](\d{2})[_:](\d{2})[_:](\d{2})',path.stem)
 if not m:return fallback
 try:
  naive=datetime.strptime(' '.join(m.groups()),'%Y-%m-%d %H %M %S')
  tz=ZoneInfo(SETTINGS.get('filename_timezone','UTC'))
  return naive.replace(tzinfo=tz).astimezone(timezone.utc).isoformat()
 except ValueError:return fallback
def num(value):
 if value is None or pd.isna(value) or str(value).strip()=='':return None
 if isinstance(value,str):value=value.replace(' ','').replace(',','.')
 try:return float(value)
 except (TypeError,ValueError):return None
def safe_move(path,directory,digest):
 target=directory/path.name
 if target.exists():target=directory/f'{path.stem}_{digest[:10]}{path.suffix}'
 shutil.move(str(path),str(target))
def process(path):
 digest=hashlib.sha256(path.read_bytes()).hexdigest(); c=db()
 if c.execute('SELECT id FROM files WHERE sha256=?',(digest,)).fetchone():c.close();path.unlink();return
 now=datetime.now(timezone.utc).isoformat(); file_id=c.execute('INSERT INTO files(filename,sha256,imported_at,status) VALUES(?,?,?,?)',(path.name,digest,now,'processing')).lastrowid
 try:
  df=read_report(path); a=CONFIG['columns']; cols={k:choose(df,v,k in ('atm_id','cash_total_uzs')) for k,v in a.items()}; inserted=0
  report_fallback=filename_time(path,now)
  for _,row in df.iterrows():
   atm=str(row[cols['atm_id']]).strip() if pd.notna(row[cols['atm_id']]) else ''; total=num(row[cols['cash_total_uzs']])
   if not atm or total is None:continue
   reported=parse_time(row[cols['reported_at']],report_fallback) if cols['reported_at'] else report_fallback
   def val(k):return row[cols[k]] if cols.get(k) else None
   raw={str(k):(None if pd.isna(v) else str(v)) for k,v in row.items()}
   c.execute('''INSERT OR IGNORE INTO snapshots(file_id,atm_id,serial_number,reported_at,collected_at,cash_total,cash_total_usd,status,address,city,latitude,longitude,raw_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(file_id,atm,str(val('serial_number') or ''),reported,now,total,num(val('cash_total_usd')),str(val('status') or ''),str(val('address') or ''),str(val('city') or ''),num(val('latitude')),num(val('longitude')),json.dumps(raw,ensure_ascii=False)))
   snapshot_id=c.execute('SELECT id FROM snapshots WHERE file_id=? AND atm_id=? AND reported_at=?',(file_id,atm,reported)).fetchone()[0]
   for n in range(1,int(CONFIG.get('cassette_count',4))+1):
    pat=CONFIG['cassette_patterns']; st=choose(df,[pat['status'].format(n=n)]); cur=choose(df,[pat['currency'].format(n=n)]); den=choose(df,[pat['denomination'].format(n=n)]); cnt=choose(df,[pat['count'].format(n=n)])
    if not any((st,cur,den,cnt)):continue
    denomination=num(row[den]) if den else None; notes=num(row[cnt]) if cnt else None
    c.execute('INSERT INTO cassettes(snapshot_id,cassette_no,status,currency,denomination,note_count,amount) VALUES(?,?,?,?,?,?,?)',(snapshot_id,n,str(row[st]) if st else '',str(row[cur]) if cur else '',denomination,int(notes) if notes is not None else None,(denomination*notes if denomination is not None and notes is not None else None)))
   inserted+=1
  if not inserted:raise ValueError('Не найдено корректных строк с TID и Total remaining amount UZS')
  c.execute('UPDATE files SET status=? WHERE id=?',('imported',file_id));c.commit();c.close();safe_move(path,ARCHIVE,digest);logging.info('Импортирован %s: %s ATM',path.name,inserted)
 except Exception as e:
  c.execute('UPDATE files SET status=?,error=? WHERE id=?',('rejected',str(e),file_id));c.commit();c.close();safe_move(path,REJECTED,digest);logging.exception('Ошибка %s',path.name)
def main():
 for p in sorted(INCOMING.iterdir()):
  if p.is_file() and p.suffix.lower() in ('.csv','.xlsx','.xlsm'):process(p)
if __name__=='__main__':main()
