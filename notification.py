import boto3
import json

class SnsNotification:
   def __init__(self, region, sns_arn, channel, username='lambda', icon_url=None):
       self.sns = boto3.client('sns', region_name=region)
       self.sns_arn = sns_arn
       self.payload = {
                          "channel": channel,
                          "username": username
                      }
       if icon_url:
           self.payload['icon_url'] =  icon_url

   def send(self, message, channel=None, username=None, icon_url=None):
       self.payload['text'] = message
       if channel:
           self.payload['channel'] = channel
       if username:
           self.payload['username'] = username
       if icon_url:
           self.payload['icon_url'] = icon_url

       response = self.sns.publish(
           TopicArn=self.sns_arn,
           Message=json.dumps({"default": json.dumps(self.payload)}),
           MessageStructure='json'
       )
        
       print(str(response))
