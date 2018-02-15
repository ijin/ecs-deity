import os
import json
import random
import boto3
from time import sleep

from notification import SnsNotification

region = os.getenv('AWS_REGION','ap-northeast-1')
SNS_ARN = os.environ['sns_arn']
CHANNEL = os.environ['channel']
alb = boto3.client('elbv2', region_name=region)
ecs = boto3.client('ecs', region_name=region)
icon = 'https://s3-us-west-2.amazonaws.com/assets.site.serverless.com/blog/step-functions.png'
notify = SnsNotification(region, SNS_ARN, CHANNEL, username='ecs deity', icon_url=icon)


#-----------CREATE-------------
def create(event, context):
    print("Received event: " + json.dumps(event, indent=2))

    vpc_id = event['vpc_id']
    cluster = event['cluster']
    lb_arn = event['lb_arn']
    health_check = event['health_check']
    container_name = event['container_name']
    container_port = int(event['container_port'])
    # using existing taskdef for now
    task_def = event['task_def']

    body = event['body']
    branch = body['ref']
    app = body['repository']['name']
    tg_branch = branch.rsplit('/', 1)[-1]
    tg = app + '-' + tg_branch + '-tg'
    service = app + '-' + tg_branch + '-service'
    port_range = event['port_range']
    port = get_available_port(lb_arn, port_range)

    msg = "Creating " + app + " environment for `" + branch + "` branch..."
    notify.send(msg)

    tg_arn = create_alb_target_group(tg, vpc_id, health_check=health_check)
    listener_arn = create_alb_listener(lb_arn, tg_arn, port)
    ecs_response = create_ecs_service(cluster, service, task_def, tg_arn, container_name=container_name, container_port=container_port, count=2)

    if not ecs_response:
        event['branch'] = "none"
    else:
        event['branch'] = branch
        event['service'] = service
        event['port'] = port
    return event

# ex. port_range = "8000-8100"
def get_available_port(lb_arn, port_range):
    listeners = alb.describe_listeners(LoadBalancerArn=lb_arn)['Listeners']
    used_ports = [ (l['Port']) for l in listeners ]
    start_port = int(port_range.split('-')[0])
    end_port = int(port_range.split('-')[-1])
    port = random.choice([i for i in range(start_port, end_port) if i not in used_ports])
    return port

def create_alb_target_group(name, vpc_id, port=80, protocol='HTTP', health_check=None, target_type='instance', deregistration_delay=30):
    current_tgs = alb.describe_target_groups()['TargetGroups']
    existing_tg = [ (t) for t in current_tgs if t.get('TargetGroupName', None) == name ]
    if existing_tg:
        notify.send('> :ghost: Target Group already exists: ' + name)
        tg_arn = existing_tg[0]['TargetGroupArn']
        return tg_arn

    if health_check['protocol'] == '':
        health_check['protocol'] = 'HTTP'
    # TODO
    #if health_check['port'] is "":
    #    health_check['port'] = 'traffic-port'
    health_check['port'] = 'traffic-port'
    if health_check['path'] == '':
        health_check['path'] = '/'
    if health_check['interval'] == '':
        health_check['interval'] = 30
    if health_check['timeout'] == '':
        health_check['timeout'] = 5
    if health_check['healthy_count'] == '':
        health_check['healthy_count'] = 5
    if health_check['unhealthy_count'] == '':
        health_check['unhealthy_count'] = 2
    if health_check['matcher'] == '':
        health_check['matcher'] = '200'

    response = alb.create_target_group(
                    Name=name,
                    Protocol=protocol,
                    Port=int(port),
                    VpcId=vpc_id,
                    HealthCheckProtocol=health_check['protocol'],
                    HealthCheckPort=health_check['port'],
                    HealthCheckPath=health_check['path'],
                    HealthCheckIntervalSeconds=int(health_check['interval']),
                    HealthCheckTimeoutSeconds=int(health_check['timeout']),
                    HealthyThresholdCount=int(health_check['healthy_count']),
                    UnhealthyThresholdCount=int(health_check['unhealthy_count']),
                    Matcher={'HttpCode': health_check['matcher']},
                    TargetType=target_type
                )
    
    tg_arn = response['TargetGroups'][0]['TargetGroupArn']
    
    alb.modify_target_group_attributes(
        TargetGroupArn=tg_arn,
        Attributes=[
            {
                'Key': 'deregistration_delay.timeout_seconds',
                'Value': str(deregistration_delay)
            }
        ]
    )
    notify.send("> ALB target group: " + name)
    return tg_arn

def create_alb_listener(lb_arn, tg_arn, port, protocol='HTTP', policy=None, certs=None):
    current_listeners = alb.describe_listeners(LoadBalancerArn=lb_arn)['Listeners']
    existing_listeners = [ (l) for l in current_listeners if l['DefaultActions'][0]['TargetGroupArn'] == tg_arn ]
    if existing_listeners:
        listener_arn = existing_listeners[0]['ListenerArn']
        notify.send('> :ghost: Listener already exists: ' + listener_arn)
        return listener_arn

    kwargs = {}
    if policy is not None:
        kwargs['SslPolicy'] = policy
    if certs is not None:
        kwargs['Certificates'] = certs
    response = alb.create_listener(
                LoadBalancerArn=lb_arn,
                Protocol=protocol,
                Port=port,
                DefaultActions=[
                    {
                        'Type': 'forward',
                        'TargetGroupArn': tg_arn
                    },
                ],
                **kwargs
            )
    arn = response['Listeners'][0]['ListenerArn']
    notify.send("> ALB listener: " + arn)
    return arn

def create_ecs_service(cluster, service, taskdef, tg_arn, container_name='app', container_port=80, count=1, launch_type='EC2', role='ecsServiceRole', min_pct=50, max_pct=200, **kwargs):
    current_services = ecs.describe_services(cluster=cluster, services=[service])['services']
    if any(s.get('status', None) != 'INACTIVE' for s in current_services):
        notify.send("> :ghost: ECS service already exists: " + service)
        return None
    
    response = ecs.create_service(
                    cluster=cluster,
                    serviceName=service,
                    taskDefinition=taskdef,
                    loadBalancers=[
                        {
                            'targetGroupArn': tg_arn,
                            'containerName': container_name,
                            'containerPort': container_port
                        },
                    ],
                    desiredCount=count,
                    launchType=launch_type,
                    role=role,
                    deploymentConfiguration={
                        'minimumHealthyPercent': min_pct,
                        'maximumPercent': max_pct
                    }
                )
    print response
    notify.send("> ECS service: " + service)
    return response

# input: { "cluster": CLUSTER, "service": SERVICE, "lb_arn": lb_rn, "port": port }
def service_creation_status(event, context):
    print("Received event: " + json.dumps(event, indent=2))
    response = ecs.describe_services(
                cluster=event['cluster'],
                services=[ event['service'] ]
    )
    print(response)
    desired_count = response['services'][0]['deployments'][0]['desiredCount']
    running_count = response['services'][0]['deployments'][0]['runningCount']
    print("running_count: " + str(running_count))
    print("desired_count: " + str(desired_count))
    if (running_count != 0 and running_count == desired_count):
        lb_arn = event['lb_arn']
        port = event['port']
        alb_endpoint = alb.describe_load_balancers(LoadBalancerArns=[lb_arn])['LoadBalancers'][0]['DNSName']
        alb_url = "http://" + alb_endpoint + ":" + str(port) + "/"
        notify.send("> :rocket: *Endpoint:* " + alb_url + " \nPlease wait for deployment...", username='ECS', icon_url='https://www.shippable.com/assets/images/logos/amazon-ecs.jpg')
        event['service_created'] = True
        #data = { "branch": branch }
    else:
        notify.send("service: creating")
        event['service_created'] = False
    return event

#-----------DELETE-------------
def destroy(event, context):
    print("Received event: " + json.dumps(event, indent=2))
    
    cluster = event['cluster']
    lb_arn = event['lb_arn']
    body = event['body']
    branch = body['ref']
    tg_branch = branch.rsplit('/', 1)[-1]
    app = body['repository']['name']
    tg = app + '-' + tg_branch + '-tg'
    service = app + '-' + tg_branch + '-service'
    
    notify.send("Destroying " + app + " environment for `" + branch + "` branch...")
    
    data = {
        "cluster": cluster,
        "service": service,
        "lb_arn": lb_arn,
        "tg": tg
    }

    # TODO: combine with stop_tasks?

    print(data)
    return(data) # pass to stop_tasks

# input: { "cluster": CLUSTER, "service": SERVICE }
def stop_tasks(event, context):
    print("Received event: " + json.dumps(event, indent=2))
    cluster=event['cluster']
    service=event['service']
     
    current_services = ecs.describe_services(cluster=cluster, services=[service])['services']
    if not current_services:
        # TODO: do nothing do not notify, only log
        raise Exception("ecs service does not exist")
    if any(s.get('status', None) != 'INACTIVE' for s in current_services):
        response = ecs.update_service(cluster=cluster, service=service, desiredCount=0)
        print(response)
    return(event)

# input: { "cluster": CLUSTER, "service": SERVICE }
def task_status(event, context):
    print("Received event: " + json.dumps(event, indent=2))
    response = ecs.describe_services(
                cluster=event['cluster'],
                services=[ event['service'] ]
    )
    print(response)
    if response['services'][0]['runningCount'] == 0:
    	status = 'stopped'
        notify.send(":x: tasks: stopped")
    else:
	status = 'running'
        notify.send("tasks: running")
    print(status)
    event['task'] = status
    return(event)

# input: { "cluster": CLUSTER, "service": SERVICE }
def delete_service(event, context):
    print("Received event: " + json.dumps(event, indent=2))
    cluster=event['cluster']
    service=event['service']
     
    current_services = ecs.describe_services(cluster=cluster, services=[service])['services']
    if any(s.get('status', None) != 'INACTIVE' for s in current_services):
        response = ecs.delete_service(cluster=cluster, service=service)
        print(response)
    return(event)

# input: { "cluster": CLUSTER, "service": SERVICE }
def service_status(event, context):
    print("Received event: " + json.dumps(event, indent=2))
    response = ecs.describe_services(
                cluster=event['cluster'],
                services=[ event['service'] ]
    )
    print(response)
    status =  response['services'][0]['status']
    if status == 'INACTIVE':
        notify.send(":x: service: stopped")
    else:
        notify.send("service: " + status)
    event['status'] =  status
    return(event)

def get_listener_arn(lb_arn, tg_arn):
    listeners = alb.describe_listeners(LoadBalancerArn=lb_arn)['Listeners']
    print(listeners)
    for n in range(0, len(listeners)):
        l = listeners[n]
        t = l['DefaultActions'][0]['TargetGroupArn']
        if t == tg_arn:
            return l['ListenerArn']
    return False    

def get_target_group_arn(tg_name):
    tgs = alb.describe_target_groups()['TargetGroups']
    tg = [ (t) for t in tgs if t['TargetGroupName'] == tg_name ]
    if tg:
        return tg[0]['TargetGroupArn']
    return False

# input: { "cluster": CLUSTER, "service": SERVICE, "lb_arn": LB_ARN }
def delete_listener_and_tg(event, context):
    print("Received event: " + json.dumps(event, indent=2))
    tg = event['tg']
    lb_arn = event['lb_arn']
    tg_arn = get_target_group_arn(tg)
    listener_arn = get_listener_arn(lb_arn, tg_arn)
    if listener_arn:
        r = alb.delete_listener(ListenerArn=listener_arn)
        print(r)
        notify.send(":x: listner: " + listener_arn)
    if tg_arn:
        r = alb.delete_target_group(TargetGroupArn=tg_arn)
        print(r)
        notify.send(":x: target group: " + tg)
    notify.send(":fire: Destroyed! :fire:")
    return

