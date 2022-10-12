from datetime import datetime
from pprint import pprint
import httplib2 
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
import os
import json

from .ConfigLoader import ConfigLoader

from .config import CREDENTIALS_FILE, CONFIG_FILENAME, EMAIL_ADDRS, \
  SOURCE_SPREADSHEET, TRACKED_SHEET_NAME, TRACKED_SHEET_HEADER_OFFSET, \
  START_COLUMN, END_COLUMN, CHUNK_SIZE, REQUEST_TIMEOUT, SECRETS_DIRECTORY


def gen_ss_link(ssID):
  return 'https://docs.google.com/spreadsheets/d/' + ssID

# Reading credentials
credentials = ServiceAccountCredentials.from_json_keyfile_name(
  os.path.join(SECRETS_DIRECTORY, CREDENTIALS_FILE), [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
])

class GSheets:
  def __init__(self):
    httpAuth = credentials.authorize(httplib2.Http(timeout=REQUEST_TIMEOUT)) # Авторизуемся в системе

    self.drive_service = build('drive', 'v3', http = httpAuth)
    self.sheets_service = build('sheets', 'v4', http = httpAuth) # Выбираем работу с таблицами и 4 версию API
    
    config = ConfigLoader(SECRETS_DIRECTORY, [CONFIG_FILENAME]).config.get(
      os.path.splitext(CONFIG_FILENAME)[0]
    )
    if config == None:
      config = {}

    self.spreadsheet_id = config.get('spreadsheetId')
    self.main_sheet_id = config.get('mainSheetId')
    self.start_page_token = config.get('startPageToken')
    self.page_token = config.get('startPageToken')
    self.last_update = config.get('lastUpdate')

    if not self.spreadsheet_id or not self.main_sheet_id or not self.start_page_token:
      print(f'GSheets: A config {CONFIG_FILENAME} doesn\'t match following format requirements')
      pprint({
        "spreadsheetId": 'spreadsheet id numbers as a string',
        "mainSheetId":   'main table sheet id numbers as a string',
        "start_page_token":   'changes tracking token',
      })
      self._create()
      

  def __str__(self):
    return f'link: {gen_ss_link(self.spreadsheet_id)}\nssId: {self.spreadsheet_id} | sheetId: {self.main_sheet_id}'
  

  def _create(self):
    # init
    spreadsheet = self.sheets_service.spreadsheets().create(body = {
      'properties': {'title': 'Копия источника', 'locale': 'ru_RU'},
    }).execute()

    self.spreadsheet_id = spreadsheet['spreadsheetId']
    print('GSheets: A spreadsheet created!\n>', gen_ss_link(self.spreadsheet_id))

    # track changes
    response = self.drive_service.changes().getStartPageToken().execute()
    self.start_page_token = response.get("startPageToken")
    self.page_token = response.get("startPageToken")
    
    # access rights
    # Select 3 version of Google Drive API
    for email in EMAIL_ADDRS:
      self.drive_service.permissions().create(
        fileId = self.spreadsheet_id,
        body = {
          # Granting access
          'type': 'user',
          'role': 'writer',
          'emailAddress': email,
        },
        fields = 'id'
      ).execute()

    self._init_source_spreadsheet()
    self._dump_config()


  def _dump_config(self):
    with open(os.path.join(SECRETS_DIRECTORY, CONFIG_FILENAME), 'w') as config_file:
      json.dump({
        "spreadsheetId": self.spreadsheet_id,
        "mainSheetId":   self.main_sheet_id,
        "startPageToken": self.start_page_token,
        "lastUpdate": self.last_update,
      }, config_file)


  def _init_source_spreadsheet(self):
    sheet_id = 0
    response = self.sheets_service.spreadsheets().sheets().copyTo(
      spreadsheetId = SOURCE_SPREADSHEET,
      sheetId = sheet_id,
      body = {
        'destinationSpreadsheetId': self.spreadsheet_id
    }).execute()

    self.main_sheet_id = response.get("sheetId")
    self.renameSheet(response.get("sheetId"), TRACKED_SHEET_NAME)


  def batch(self, requests: list):
    try:
      return self.sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=self.spreadsheet_id,
        body={
          'requests': requests
        }).execute()
    except Exception as e:
      print(f'GSheets error: unable to fetch {self.spreadsheet_id} table with Google Sheets API:', e)
      return {}


  def renameSheet(self, sheetId, newName):
    return self.batch({
      "updateSheetProperties": {
        "properties": {
          "sheetId": sheetId,
          "title": newName,
        },
        "fields": "title",
      }
    })
  

  def check_changes(self):
    '''
    This can only say if someone touched the table or not.
    '''
    self.page_token = self.start_page_token
    were_changes_in_a_file = False
    start_page_token = self.start_page_token

    try:
      while self.page_token is not None:

        response = self.drive_service.changes().list(
          pageToken=self.page_token,
          spaces='drive',
        ).execute()
        
        # skip all changes till the end and then update the DB with other metods
        for change in response.get('changes'):
          file_id =  change.get("fileId")
          # check if it is the tracked table 
          if file_id == self.spreadsheet_id:
            were_changes_in_a_file = True
        if 'newStartPageToken' in response:
          # Last page, save this token for the next polling interval
          self.start_page_token = response.get('newStartPageToken')
        self.page_token = response.get('nextPageToken')

      # save changeID of the last change 
      if start_page_token != self.start_page_token:
        self.last_update = f'{datetime.now():%X %d.%m.%Y}'
        self._dump_config()
    
    except Exception as e:
      print(f'GSheets error: unable to fetch {self.spreadsheet_id} table with Google Sheets API:', e)
    finally:
      return were_changes_in_a_file
    

  def get_chunk(self, start_idx):
    '''
    returns tuple:
    0: idx to continue iteration
    1: start row_idx in a google spreadsheet
    2: end row_idx in a google spreadsheets
    3: array of rows with values from START_COLUMN up to END_COLUMN
    or NONE, if chunk is empty
    '''
    range_from_to = (start_idx + TRACKED_SHEET_HEADER_OFFSET + 1,
                     start_idx + CHUNK_SIZE + TRACKED_SHEET_HEADER_OFFSET)
    try:
      response = self.sheets_service.spreadsheets().values().get(
        spreadsheetId=self.spreadsheet_id,
        range=f'{TRACKED_SHEET_NAME}!{START_COLUMN}{range_from_to[0]}:{END_COLUMN}{range_from_to[1]}'
      ).execute()
      return (start_idx + CHUNK_SIZE, *range_from_to, response.get("values"))

    except Exception as e:
      print(f'GSheets error: unable to fetch {self.spreadsheet_id} table with Google Sheets API:', e)
      return (start_idx + CHUNK_SIZE, *range_from_to, {})
