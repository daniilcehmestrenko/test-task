from lib.DBConnector import DB
from lib.CRB import CRB
from lib.GSheets import GSheets
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from lib.config import CRB_POLLING_INTERVAL, GS_POLLING_INTERVAL


if __name__ == '__main__':
  scheduler = AsyncIOScheduler()
  sheet = GSheets()
  print(sheet, '\n')
  crb = CRB()
  with DB() as db:
    db.update_cost_rub(crb.currency_rate)
    print('USD currency rate:', crb.currency_rate, '\n')


  async def sheet_check_job():
    print('[sheet_check_job] checking the spreadsheet')
    if not sheet.check_changes():
      print('[sheet_check_job] no changes')
      return

    with DB() as db:
      print('[sheet_check_job] committing changes')
      rows = ['']
      idx = 0
      while True:
        idx, ss_start_row_idx, _, rows = sheet.get_chunk(idx)
        if not rows:
          break
        for i, row in enumerate(rows):
          # rows like [] or rows with spaces
          if (len(row) < 4):
            continue
          row.extend((ss_start_row_idx + i, 0))
        db.upsert(rows)
      print('[sheet_check_job] done!')

  async def currency_rate_check_job():
    with DB() as db:
      db.update_cost_rub(crb.fetch_currency_rate())
      print('[currency_rate_check_job] the USD-RUB currency rate has been updated:', crb.currency_rate)
      

  # perhaps using CRON mode would be better
  scheduler.add_job(currency_rate_check_job, "interval", hours=CRB_POLLING_INTERVAL)
  scheduler.add_job(sheet_check_job, "interval", minutes=GS_POLLING_INTERVAL)
  scheduler.start()

  print('Press Ctrl+C to exit\n')

  # Execution will block here until Ctrl+C (Ctrl+Break on Windows) is pressed.
  try:
    asyncio.get_event_loop().run_forever()
  except (KeyboardInterrupt, SystemExit):
    scheduler.shutdown()
    asyncio.get_event_loop().stop()
