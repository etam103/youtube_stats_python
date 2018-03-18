import time
import sys
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery

API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'

def retry(func):
  def retried_func(*args, **kwargs):
      MAX_TRIES = sys.maxint
      tries = 0
      while True:
          resp = func(*args, **kwargs)
          if len(resp['items']) == 0 and tries < MAX_TRIES:
              tries += 1
              time.sleep(5)
              continue
          break
      return resp
  return retried_func

def build_client(credentials):
  youtube = googleapiclient.discovery.build(
    API_SERVICE_NAME, API_VERSION, credentials=credentials)
  
  return youtube

@retry
def list_videos_by_id(youtube, videoId):
  list_video_response = youtube.videos().list(
    part='id, snippet,contentDetails, statistics, liveStreamingDetails',
    id=videoId
  ).execute()

  return list_video_response

def list_live_chat_messages_by_id(youtube, liveChatId, pageToken):
  list_live_chat_messages_response = youtube.liveChatMessages().list(
    part='id, snippet, authorDetails',
    liveChatId=liveChatId,
    pageToken=pageToken
  ).execute()

  return list_live_chat_messages_response

@retry
def list_top_active_gaming_live_streams(youtube):
  list_search_response = youtube.search().list(
    part='snippet',
    eventType='live',
    type='video',
    videoCategoryId=20,
    order='viewCount'
  ).execute()

  return list_search_response