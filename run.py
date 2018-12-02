import base64
import os
import settings
import requests
import talon
from apiclient import errors
from apiclient.discovery import build
from google.oauth2 import service_account
from talon import quotations


def list_messages_matching_query(service, user_id, query=''):
    """List all Messages of the user's mailbox matching the query.

    Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    query: String used to filter messages returned.
    Eg.- 'from:user@some_domain.com' for Messages from a particular sender.

    Returns:
    List of Messages that match the criteria of the query. Note that the
    returned list contains Message IDs, you must use get with the
    appropriate ID to get the details of a Message.
    """
    response = service.users().messages().list(userId=user_id,
                                               q=query).execute()

    messages = []
    if 'messages' in response:
        messages.extend(response['messages'])

    while 'nextPageToken' in response:
        page_token = response['nextPageToken']
        response = service.users().messages().list(
            userId=user_id, q=query, pageToken=page_token).execute()
        messages.extend(response['messages'])

    return messages


def get_message(service, user_id, message_id):
    """Get a message from the user's mailbox.

    Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    message_id: The message ID.
    """
    return service.users().messages().get(userId=user_id, id=message_id).execute()


def modify_message(service, user_id, message_id, modifications):
    """Add a label to a message.

    Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    message_id: The message ID.
    modifications: The modifications.
    """
    return service.users().messages().modify(userId=user_id, id=message_id, body=modifications).execute()


def create_service():
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.modify',
        'https://www.googleapis.com/auth/gmail.readonly',
    ]
    SERVICE_ACCOUNT_FILE = 'service-account-key.json'

    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    delegated_credentials = credentials.with_subject(os.getenv('INBOX'))

    return build('gmail', 'v1', credentials=delegated_credentials)


def get_header(message, header_name):
    for header in message['payload']['headers']:
        if header['name'] == header_name:
            return header['value']
    raise 'Header not present: ' + header_name


def get_body_by_mime_type(message, mime_type):
    for part in message['payload']['parts']:
        if part['mimeType'] == mime_type:
            return base64.urlsafe_b64decode(part['body']['data'].encode('ASCII'))
    raise 'Mime-type not present: ' + mime_type


def push_to_api(message):
    from_header = get_header(message, 'From')
    if '<' in from_header:
        from_email = from_header.split(' <')[1].split('>')[0]
        from_name = from_header.split(' <')[0]
    else:
        from_email = from_header
        from_email = None

    headers = {
        'authorization': os.getenv('API_AUTHORIZATION_HEADER'),
        'accept': 'application/vnd.faultfixers.v7+json',
        'content-type': 'application/json',
    }

    full_html = get_body_by_mime_type(message, 'text/html')
    full_text = get_body_by_mime_type(message, 'text/plain')

    payload = {
        'emailId': message['id'],
        'fromEmail': from_email,
        'fromName': from_name,
        'subject': get_header(message, 'Subject'),
        'fullHtml': full_html,
        'htmlReply': quotations.extract_from_html(full_html),
        'fullText': full_text,
        'textReply': quotations.extract_from_plain(full_text),
    }

    response = requests.post(os.getenv('API_ENDPOINT'), headers=headers, json=payload)

    response.raise_for_status()


def run():
    service = create_service()

    list_messages = list_messages_matching_query(
        service, 'me', os.getenv('GMAIL_QUERY') + ' AND NOT label:' + os.getenv('HANDLED_LABEL_NAME'))

    print '%d messages to process' % len(list_messages)

    if len(list_messages) == 0:
        return

    talon.init()

    for list_message in list_messages:
        print 'Getting message %s' % list_message['id']
        full_message = get_message(service, 'me', list_message['id'])
        print 'Message %s has snippet: %s' % (list_message['id'], full_message['snippet'])

        push_to_api(full_message)
        print 'Pushed message %s to API' % list_message['id']

        modify_message(service, 'me', list_message['id'], {
            'addLabelIds': [os.getenv('HANDLED_LABEL_ID')],
            'removeLabelIds': ['UNREAD'],
        })


try:
    run()
except errors.HttpError, error:
    print 'An error occurred: %s' % error
    print 'content: %s' % error.content
    print 'error_details: %s' % error.error_details
    print 'message: %s' % error.message
    print 'resp: %s' % error.resp
    print 'uri: %s' % error.uri
except requests.exceptions.HTTPError, error:
    print 'An error occurred: %s' % error
    print 'json: %s' % error.response.json()
