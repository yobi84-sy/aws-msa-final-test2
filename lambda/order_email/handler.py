"""SNS/SQS 주문 이벤트 → SES. 비밀값/이메일/본문을 로그에 출력하지 않습니다."""
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone

class Busy(Exception):
    pass

def parse(body):
    event = json.loads(body)
    if isinstance(event, dict) and isinstance(event.get('Message'), str):
        event = json.loads(event['Message'])
    if not isinstance(event, dict) or event.get('schemaVersion') != 1 or event.get('eventType') != 'ORDER_CREATED':
        raise ValueError('Invalid event schema')
    if not re.fullmatch(r'[a-f0-9-]{36}', str(event.get('eventId', ''))):
        raise ValueError('Invalid event ID')
    if str(uuid.UUID(event['eventId'])) != event['eventId']:
        raise ValueError('Invalid canonical event ID')
    for field in ('orderId', 'memberId', 'quantity'):
        if type(event.get(field)) is not int or event[field] < 1:
            raise ValueError('Invalid order numbers')
    if type(event.get('total')) is not int or event['total'] < 0:
        raise ValueError('Invalid amount')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', str(event.get('recipientEmail', ''))):
        raise ValueError('Invalid recipient')
    name = event.get('productName')
    if not isinstance(name, str) or not name.strip() or len(name) > 255:
        raise ValueError('Invalid product')
    return event

def process(event, store, send, now=None):
    now = int(time.time()) if now is None else now
    failures = []
    for record in event.get('Records', []):
        token = None
        data = None
        try:
            data = parse(record['body'])
            token = str(uuid.uuid4())
            if not store.claim(data['eventId'], token, now):
                continue  # SENT인 이벤트만 성공 처리한다. 처리 중인 이벤트는 재시도한다.
            send(data)
            store.sent(data['eventId'], token)
        except Exception:
            # SES 수락 후 DB 완료 기록이 실패한 경우에도 중복 메일 가능성이 있다.
            # 이를 exactly-once로 표현하지 않는다.
            if data is not None and token is not None:
                try:
                    store.release(data['eventId'], token)
                except Exception:
                    pass
            failures.append({'itemIdentifier': record['messageId']})
    return {'batchItemFailures': failures}

class DynamoStore:
    def __init__(self, table):
        self.table = table

    def claim(self, event_id, token, now):
        try:
            self.table.update_item(
                Key={'eventId': event_id},
                UpdateExpression='SET #s=:processing, leaseToken=:token, leaseUntil=:lease, expiresAt=:ttl',
                ConditionExpression='attribute_not_exists(eventId) OR (#s <> :sent AND (attribute_not_exists(leaseUntil) OR leaseUntil < :now))',
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={':processing':'PROCESSING', ':sent':'SENT', ':token':token, ':lease':now+90, ':now':now, ':ttl':now+30*86400})
            return True
        except self.table.meta.client.exceptions.ConditionalCheckFailedException:
            item = self.table.get_item(Key={'eventId':event_id}, ConsistentRead=True).get('Item', {})
            if item.get('status') == 'SENT':
                return False
            raise Busy('Event is being processed')

    def sent(self, event_id, token):
        self.table.update_item(Key={'eventId':event_id}, UpdateExpression='SET #s=:sent REMOVE leaseToken, leaseUntil',
            ConditionExpression='leaseToken=:token', ExpressionAttributeNames={'#s':'status'},
            ExpressionAttributeValues={':sent':'SENT',':token':token})

    def release(self, event_id, token):
        self.table.update_item(Key={'eventId':event_id}, UpdateExpression='SET leaseUntil=:zero',
            ConditionExpression='leaseToken=:token', ExpressionAttributeValues={':zero':0,':token':token})

def handler(event, context):
    import boto3
    from botocore.config import Config
    config = Config(connect_timeout=2, read_timeout=5, retries={'max_attempts':1})
    store = DynamoStore(boto3.resource('dynamodb', config=config).Table(os.environ['DEDUP_TABLE']))
    ses = boto3.client('sesv2', config=config)
    def send(data):
        ses.send_email(FromEmailAddress=os.environ['SENDER_EMAIL'], Destination={'ToAddresses':[data['recipientEmail']]},
            Content={'Simple':{'Subject':{'Data':f"주문 완료 안내 #{data['orderId']}",'Charset':'UTF-8'},
            'Body':{'Text':{'Data':f"주문번호: {data['orderId']}\n상품: {data['productName']}\n수량: {data['quantity']}\n금액: {data['total']}원",'Charset':'UTF-8'}}}})
    return process(event, store, send)
