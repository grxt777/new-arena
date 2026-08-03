#!/usr/bin/env python3
import html, json, sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parent; DB=ROOT/'atm_forecast.db'; SETTINGS=json.loads((ROOT/'config/settings.json').read_text())

def get_rows():
    if not DB.exists(): return []
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    rows=c.execute('''WITH latest AS (SELECT s.*, ROW_NUMBER() OVER(PARTITION BY atm_id ORDER BY reported_at DESC) n FROM snapshots s) SELECT * FROM latest WHERE n=1 ORDER BY cash_total ASC''').fetchall()
    result=[]
    for r in rows:
        hist=c.execute('SELECT cash_total, reported_at FROM snapshots WHERE atm_id=? ORDER BY reported_at DESC LIMIT 100', (r['atm_id'],)).fetchall()
        points=list(reversed(hist)); daily=None
        if len(points)>=3:
            first,last=points[0],points[-1]
            days=max((datetime.fromisoformat(last['reported_at'])-datetime.fromisoformat(first['reported_at'])).total_seconds()/86400, 1/24)
            decrease=sum(max(0, points[i-1]['cash_total']-points[i]['cash_total']) for i in range(1,len(points)))
            daily=decrease/days
        burn=daily or SETTINGS['default_daily_burn']; safety=SETTINGS['safety_cash']
        days_left=(r['cash_total']-safety)/burn if burn>0 else None
        result.append((r, burn, days_left))
    c.close(); return result

def page():
    rows=get_rows(); now=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    trs=[]
    for r,burn,days in rows:
        risk='Недостаточно истории' if days is None else ('КРИТИЧЕСКИЙ' if days<=SETTINGS['critical_days'] else ('ВЫСОКИЙ' if days<=3 else 'Низкий'))
        color='#ffd6d6' if risk=='КРИТИЧЕСКИЙ' else ('#fff0c2' if risk=='ВЫСОКИЙ' else '#e7f5e8')
        daytxt='—' if days is None else f'{max(days,0):.1f} дн.'
        trs.append(f'<tr style="background:{color}"><td>{html.escape(r["atm_id"])}</td><td>{html.escape(r["address"] or r["city"] or "—")}</td><td>{r["cash_total"]:,.0f}</td><td>{burn:,.0f}</td><td>{daytxt}</td><td>{risk}</td><td>{html.escape(r["reported_at"])}</td></tr>')
    return f'''<!doctype html><html lang="ru"><meta charset="utf-8"><title>ATM Forecast</title><style>body{{font-family:Arial;margin:32px;background:#f5f7fa;color:#1f2937}}table{{border-collapse:collapse;width:100%;background:white}}th,td{{padding:10px;border:1px solid #ddd;text-align:left}}th{{background:#172554;color:#fff}}.card{{display:inline-block;background:#fff;padding:16px;margin:0 12px 18px 0;border-radius:8px}}small{{color:#667085}}</style><h1>Прогноз пополнения банкоматов</h1><small>Обновлено: {now}. Новые отчеты обрабатываются отдельным importer.py.</small><div><div class="card"><b>Банкоматов</b><br>{len(rows)}</div><div class="card"><b>Критический риск</b><br>{sum(1 for _,_,d in rows if d is not None and d<=SETTINGS["critical_days"])}</div></div><table><tr><th>ATM</th><th>Локация</th><th>Остаток</th><th>Расход/день</th><th>До порога</th><th>Риск</th><th>Последний отчет</th></tr>{''.join(trs) or '<tr><td colspan="7">Данных пока нет. Положите CSV/XLSX в data/incoming и запустите importer.py.</td></tr>'}</table></html>'''

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body=page().encode('utf-8'); self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *_): pass

if __name__=='__main__':
    print('Открыть http://127.0.0.1:8080')
    HTTPServer(('127.0.0.1',8080), Handler).serve_forever()
