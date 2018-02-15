import os
import json

from notification import SnsNotification

region = os.getenv('AWS_REGION','ap-northeast-1')
SNS_ARN = os.environ['sns_arn']
CHANNEL = os.environ['channel']
lambda_icon = 'https://raw.githubusercontent.com/donnemartin/dev-setup-resources/master/res/aws_lambda.png'
notify = SnsNotification(region, SNS_ARN, CHANNEL, icon_url=lambda_icon)

# ex. { "Error": "AccessDeniedException", "Cause": "{}" }
def sfn_error(event, context):
    print("Received event: " + json.dumps(event, indent=2))

    channel = os.environ['channel']
    if 'icon_url' in os.environ:
        icon_url = os.environ['icon_url']
    else:
        icon_url = 'https://s3.amazonaws.com/csfiles/img/dark_hanya.jpg'
    username = 'angry deity'

    if ("Error" in event and "Cause" in event):
        try:
          cause = json.dumps(json.loads(event['Cause']), indent=2) 
        except:
          cause = str(event['Cause'])
        message = "*ERROR*: `" + event['Error'] + "`\n```" + cause + "```"
        notify.send(message, channel=channel, username=username, icon_url=icon_url)
        raise Exception("Step function failed and notified.")
    else:
        raise TypeError("Invalid step function json")

