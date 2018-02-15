from __future__ import print_function
from datetime import date, datetime

import os
import json
import boto3

sfn = boto3.client('stepfunctions', region_name=os.environ['AWS_REGION'])

def respond(err, res=None):
    return {
        'statusCode': '400' if err else '200',
        'body': err.message if err else json.dumps(res),
        'headers': {
            'Content-Type': 'application/json',
        },
    }

def json_serial(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))

def sfn_json(data, stg):
    json = {
        'vpc_id': os.environ['vpc_id'],
        'cluster': os.environ['cluster'],
        'container_name': os.environ['container_name'], 'container_port': os.environ['container_port'],
        'task_def': os.environ['task_def'],
        'lb_arn': os.environ['lb_arn'],
        'port_range': os.environ['port_range'],
        'health_check': {
            'protocol': os.environ['health_check_protocol'],
            'port': os.environ['health_check_port'],
            'path': os.environ['health_check_path'],
            'interval': os.environ['health_check_interval'],
            'timeout': os.environ['health_check_timeout'],
            'healthy_count': os.environ['health_check_healthy_count'],
            'unhealthy_count': os.environ['health_check_unhealthy_count'],
            'matcher': os.environ['health_check_matcher']
        },
        'stage': stg,
        'body': data
    }
    print(json)
    return json

def step_function(event, context):
    print("Received event: " + json.dumps(event, indent=2))
    body = json.loads(event['body'])
    headers = json.loads(json.dumps(event['headers']))
    stage = event['requestContext']['stage']
    print("stage: " + stage)
    if headers['X-GitHub-Event'] in ('create', 'delete') and body['ref_type'] == 'branch':
        gh_event = headers['X-GitHub-Event']
        print("branch " + gh_event + " request!")

        if not applicable_branch(body['ref']):
            return respond(None, {"branch": "not applicable"})

        sfn_arn = gh_event + '_sfn_arn'
        res = sfn.start_execution(
            stateMachineArn = os.environ[sfn_arn],
            name = stage + "-" + headers['X-Amzn-Trace-Id'],
            input = json.dumps(sfn_json(body, stage))
        )
        j = json.loads(json.dumps(res, default=json_serial))
        print(j)
        return respond(None, j)
    else:
        return respond(ValueError("Invalid GitHub event type"))

def applicable_branch(branch):
    branch_prefix = os.environ['branch_prefix']
    if branch.split('/')[0] != branch_prefix:
        return False
    return True
    

