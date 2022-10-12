import psycopg2

from .config import MAIN_TABLE_FIELD_NAME__GOOGLE_SPREADSHEET_COLUMN_IDX__MAP, \
  MAIN_TABLE_FIELD_NAME__MAIN_TABLE_FIELD_TYPE, \
  DEFAULT_ORDER, DB_NAME, USER, PSWD, HOST, \
  TRACKED_SHEET_HEADER_OFFSET, MAIN_TABLE_NAME

FIELDS_NUM = len(MAIN_TABLE_FIELD_NAME__GOOGLE_SPREADSHEET_COLUMN_IDX__MAP)



def _gen_value_string(row, order = DEFAULT_ORDER):
  result = '('
  last_field = order[-1]
  for field in order:
    if field == 'delivery_date':
      result += '\''
    result += str(row[MAIN_TABLE_FIELD_NAME__GOOGLE_SPREADSHEET_COLUMN_IDX__MAP[field]])
    if field == 'delivery_date':
      result += '\''
    result += MAIN_TABLE_FIELD_NAME__MAIN_TABLE_FIELD_TYPE[field]
    if field != last_field:
      result += ', '
  return result + ')'


class DB:
  def __init__(self):
    self.connected = False
    self.conn = None
    self.cursor = None
    pass

  def _safely_execute(self, q):
    # all error types:
    # https://www.psycopg.org/docs/errors.html
    try:
      self.cursor.execute(q)
    except Exception as e:
      print('DB: Postgre execution error:', e)
  

  def _connect(self):
    self.connected = True
    self.conn = psycopg2.connect(dbname=DB_NAME, user=USER, 
                                 password=PSWD, host=HOST)
    self.cursor = self.conn.cursor()
    self.conn.autocommit = True

    self._safely_execute("select relname from pg_class where relkind='r' and relname !~ '^(pg_|sql_)';")
    tables = map(lambda x: x[0], self.cursor.fetchall())
    if not MAIN_TABLE_NAME.lower() in tables:
      print(f'DB: Table {MAIN_TABLE_NAME} is missing in {DB_NAME}!')
      self._close()


  def _close(self):
    self.connected = False

    self.cursor.close()
    self.conn.close()

    self.conn = None
    self.cursor = None


  def __enter__(self):
    self._connect()
    return self    


  def __exit__(self, exc_type, exc_val, exc_tb):
    self._close()


  def connect(self):
    self._connect()


  def close(self):
    self._close()


  def upsert(self, values):
    if not self.connected:
      self._connect()

    q = ''
    for value in values:
      if len(value) < FIELDS_NUM:
        if len(value) > 0:
          print('\tDB.upsert:\tmissing values:', value, '\trequired length is', FIELDS_NUM)
        continue
      q += f'SELECT upsert_orders{_gen_value_string(value)};\n'
    
    self._safely_execute(q)


  def get_chunk(self, from_idx, to_idx):
    if not self.connected:
      self._connect()

    q = f'''
SELECT * FROM {MAIN_TABLE_NAME}
WHERE table_row_index >= {from_idx + TRACKED_SHEET_HEADER_OFFSET + 1} AND table_row_index <= {to_idx + TRACKED_SHEET_HEADER_OFFSET};
'''
    self._safely_execute(q)
    return self.cursor.fetchall()

  
  def update_cost_rub(self, price):
    if not self.connected:
      self._connect()

    q = f'''
UPDATE {MAIN_TABLE_NAME}
SET cost_rub = cost_usd * {price};
    '''

    self._safely_execute(q)
