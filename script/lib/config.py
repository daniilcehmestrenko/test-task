from pprint import pprint
from .ConfigLoader import ConfigLoader

# files not to share
SECRETS_DIRECTORY = 'secret/'
CREDENTIALS_FILE = 'credentials.json'           # Google service account credentials.
                                                # Relative to SECRETS_DIRECTORY
CONFIG_FILENAME = 'gsheets_cached_config.json'  # Script creates new table on launch and writes its
                                                # params here. If the file exists, new table.
                                                # Relative to SECRETS_DIRECTORY

config = ConfigLoader(SECRETS_DIRECTORY, [
  'db.json',
]).config

if not config.get('db'):
  print('there is no db.json in', SECRETS_DIRECTORY)
  exit(1)
# keys for DB connecting
try:
  DB_NAME = config['db']['DB_NAME']
  USER = config['db']['USER']
  PSWD = config['db']['PSWD']
  HOST = config['db']['HOST']
except KeyError as ke:
  print('DB: config error. missing field', ke)
except Exception as e:
  print('DB: config error', e)
  exit(1)

print('App started with config:')
pprint(config)
print()

# /////////////////////////
# 
#        DB config
# 
# /////////////////////////

# DB and Googlesheets will be held with {CHUNK_SIZE} rows. 1000 is a default size of Google spreadsheet
# on creating (Max rows: 1000, max columns: 26).
CHUNK_SIZE = 1000

MAIN_TABLE_NAME = 'orders' # Postgres table name 

# match with Postgres field name and column index in the Google spreadsheet
# 2 column are extra: table_row_index = 4 and cost_rub = 5 are not supposed to be changed
MAIN_TABLE_FIELD_NAME__GOOGLE_SPREADSHEET_COLUMN_IDX__MAP = {
  "table_row_index": 4,
  "table_row_number": 0,
  "order_number": 1,
  "cost_usd": 2,
  "cost_rub": 5,
  "delivery_date": 3,
}

# same match as MAIN_TABLE_FIELD_NAME__GOOGLE_SPREADSHEET_COLUMN_IDX__MAP with type cast
MAIN_TABLE_FIELD_NAME__MAIN_TABLE_FIELD_TYPE = {
  "table_row_index": '',
  "table_row_number": '',
  "order_number": '',
  "cost_usd": '::NUMERIC(12, 2)',
  "cost_rub": '::NUMERIC(12, 2)',
  "delivery_date": '::CHAR(10)',
}

# all operations on multiple fields on rows from the Google spreadsheet must be done in following order,
# e.g.
# INSERT INTO Orders(table_row_index, table_row_number, order_number, cost_usd, cost_rub, delivery_date) VALUES(3, 2, 1338, 250, 15000, '05.07.2022');
DEFAULT_ORDER = (
  'table_row_index',
  'table_row_number',
  'order_number',
  'cost_usd',
  'cost_rub',
  'delivery_date',
)



# /////////////////////////
# 
# Google spreadsheet config
# 
# /////////////////////////

# CREDENTIALS_FILE = 'secret/credentials.json'  # Google service account credentials. see above
# CONFIG_FILENAME = 'gsheets_cached_config.json'# Script creates new table on launch and writes its
                                                # params here. If the file exists, new table. see above
                                                # is not being created
EMAIL_ADDRS = ['daniilcehmestrenko21217@gmail.com', 'acc-791@testtask-364310.iam.gserviceaccount.com']
                                                # gmails which granded with privelages to edit the
                                                # Google spreadsheet after a creating
SOURCE_SPREADSHEET = '1AiQWniVnLfnzzDahP3m-YRTCdw-hyELj17BGp5Zm5NA' # the origin Google spreadsheet
TRACKED_SHEET_NAME = 'SourceSheet'              # a name of sheet containing data from SOURCE_SPREADSHEET
TRACKED_SHEET_HEADER_OFFSET = 1                 # TRACKED_SHEET_HEADER_OFFSET rows of header are skipped
START_COLUMN = 'A'                              # reading request takes values in a range START_COLUMN:END_COLUMN
END_COLUMN = 'D'


# /////////////////////////
# 
#          net config
# 
# /////////////////////////

REQUEST_TIMEOUT = 200      # seconds
CRB_POLLING_INTERVAL = 1   # hours
GS_POLLING_INTERVAL =  15  # the Google spreadsheet POLLING_INTERVAL, minutes



# /////////////////////////
# 
#  cbr info parsing config
# 
# /////////////////////////

VALUTE_CHAR_CODE = 'USD'                    # this valute is exchanged to RUBs
VALUTE_INFO_OPEN_TAG = '<CharCode>'         # API-depending information. see CRB.py if API has been changed
VALUTE_INFO_VALUE_OPEN_TAG = '<Value>'
VALUTE_INFO_VALUE_CLOSE_TAG = '</Value>'
VALUTE_INFO_NOMINAL_OPEN_TAG = '<Nominal>'
VALUTE_INFO_NOMINAL_CLOSE_TAG = '</Nominal>'
