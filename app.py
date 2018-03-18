# -*- coding: utf-8 -*-

import os
import time
from datetime import timedelta

import flask
from flask import render_template
from flask import send_from_directory
from flask import jsonify

from flask_socketio import SocketIO, send, emit
from flask_pymongo import PyMongo

import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import youtube_client

from config import HOST, PORT, DEBUG

# The CLIENT_SECRETS_FILE variable specifies the name of a file that contains
# the OAuth 2.0 information for this application, including its client_id and
# client_secret.
CLIENT_SECRETS_FILE = "client_secret.json"

# This OAuth 2.0 access scope allows for full read/write access to the
# authenticated user's account and requires requests to use an SSL connection.
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

# set up path to static files
app = flask.Flask(__name__, static_url_path='')
app.secret_key = '\x03\xc3\x93\x85\xf1F\xdbA\xff\x0b\xc0>:\xff\xa4\x19\x0c\xd6 \xa2G\x1eza'

# Setup Socket IP
socketio = SocketIO(app, ping_timeout=100000)

# Setup mongodb
# Seems like storage isn't needed anymore
# app.config['MONGO_URI'] = 'mongodb://localhost:8080/'
# app.config['MONGO_PORT'] = 8080
# app.config['MONGO_DBNAME'] = 'test'
# mongo = PyMongo(app)

@app.before_request
def make_session_permanent():
  flask.session.permanent = True
  app.permanent_session_lifetime = timedelta(hours=12)

# Favicon
# TODO: Test when you are done with project
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                          'favicon.ico',mimetype='image/vnd.microsoft.icon')

@app.route('/')
def index():
  return render_template('index.html', pageName="index")
  # return render_template('loading.html', pageName="loading")

@app.route('/logout')
def logout():
  flask.session.clear()
  return flask.redirect('/')

@app.route('/auth/google')
def authorize():
  # Create a flow instance to manage the OAuth 2.0 Authorization Grant Flow
  # steps.
  flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
      CLIENT_SECRETS_FILE, scopes=SCOPES)
  flow.redirect_uri = flask.url_for('oauth2callback', _external=True)
  authorization_url, state = flow.authorization_url(
      # This parameter enables offline access which gives your application
      # both an access and refresh token.
      access_type='offline',

      # probably want to remove consent after user session is in place
      prompt='consent',

      # This parameter enables incremental auth.
      include_granted_scopes='true')

  # Store the state in the session so that the callback can verify that
  # the authorization server response.
  flask.session['state'] = state

  return flask.redirect(authorization_url)


@app.route('/auth/google/callback')
def oauth2callback():
  # Specify the state when creating the flow in the callback so that it can
  # verify the authorization server response.
  state = flask.session['state']
  flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
      CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
  flow.redirect_uri = flask.url_for('oauth2callback', _external=True)

  # Use the authorization server's response to fetch the OAuth 2.0 tokens.
  authorization_response = flask.request.url
  flow.fetch_token(authorization_response=authorization_response)

  # Store the credentials in the session.
  # ACTION ITEM for developers:
  #     Store user's access and refresh tokens in your data store if
  #     incorporating this code into your real app.
  credentials = flow.credentials
  flask.session['credentials'] = {
      'token': credentials.token,
      'refresh_token': credentials.refresh_token,
      'token_uri': credentials.token_uri,
      'client_id': credentials.client_id,
      'client_secret': credentials.client_secret,
      'scopes': credentials.scopes
  }

  return flask.redirect('/please-wait')

@app.route('/please-wait')
def pleaseWait():
  if 'credentials' not in flask.session:
    return flask.redirect('/auth/google')

  return render_template('loading.html', pageName="loading")

# LiveStream routes
@app.route('/liveStream')
def liveStream():
  if 'credentials' not in flask.session:
    return flask.redirect('/auth/google')

  # Load the credentials from the session.
  credentials = google.oauth2.credentials.Credentials(
      **flask.session['credentials'])

  youtube = youtube_client.build_client(credentials)

  response = youtube_client.list_top_active_gaming_live_streams(youtube)
  videoId = response['items'][0]['id']['videoId']

  return render_template('liveStream.html', pageName="liveStream", videoId=videoId)

# MongoDb
# NOTE: put this back in if search is needed
# def createOrUpdateUserChatMessages(username, message):
#   userChatCollection = mongo.db.userChatCollection

#   result = userChatCollection.find_one({'username': username})

#   if result == None:
#     userChatCollection.insert({'username': username, 'messages': [message]})
#   else:
#     _id = result['_id']
#     result['messages'].append(message)
#     messages = result['messages']
#     update = { '$set' : {'messages' : messages} }
#     userChatCollection.update_one({'username' : username }, update)

# Socket.io
@socketio.on('connect')
def connectEvent():
    print 'connected'

@socketio.on('disconnect')
def disconnect_user():
    flask.session.clear()

def startPolling(liveChatId, nextPageToken, pollingIntervalMillis):
  time.sleep(pollingIntervalMillis)
  
  # Load the credentials from the session.
  credentials = google.oauth2.credentials.Credentials(
      **flask.session['credentials'])

  youtube = youtube_client.build_client(credentials)
  response = youtube_client.list_live_chat_messages_by_id(youtube, liveChatId, nextPageToken)

  items = response['items'] # chatMessages
  newNextPageToken = response['nextPageToken']
  newPollingInterval = response['pollingIntervalMillis'] / 1000

  for item in items:
    usernameWithMessage = { 
      'username': item['authorDetails']['displayName'],
      'message': item['snippet']['displayMessage']
    }
    # TODO: - put this back in if search is needed
    # createOrUpdateUserChatMessages(usernameWithMessage['username'], usernameWithMessage['message'])
    # print usernameWithMessage
    socketio.emit('new message', usernameWithMessage)
  
  startPolling(liveChatId=liveChatId, nextPageToken=newNextPageToken, pollingIntervalMillis=newPollingInterval)

@socketio.on('startPolling')
def startPollingEvent(data):
  videoId = data['videoId']
  
  credentials = google.oauth2.credentials.Credentials(
      **flask.session['credentials'])

  youtube = youtube_client.build_client(credentials)
  response = youtube_client.list_videos_by_id(youtube, videoId)

  activeLiveChatId = response['items'][0]['liveStreamingDetails']['activeLiveChatId']
  startPolling(activeLiveChatId, '', 0)

# put this back in if storage is needed
# @socketio.on('search')
# def searchEvent(data):
  # username = data['username']
  # userChatCollection = mongo.db.userChatCollection
  # result = userChatCollection.find_one({ 'username': username })
  # emit('searchResults', {result})

if __name__ == '__main__':
  # When running locally, disable OAuthlib's HTTPs verification. When
  # running in production *do not* leave this option enabled.
  # os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
  socketio.run(app, host=HOST, port=PORT, debug=DEBUG)
