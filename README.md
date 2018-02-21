# ECS Deity

Creates and destroys on-demand environments through separate ECS services

![ecs deity diagram](https://lh3.googleusercontent.com/9eXmgANkPMjNl7UeWqcwuP4M5-xuGnhyWxSNfUagJWniwnnpxv4I-owKDQld-nJx8pI5joskjsRgEnihSrcLP6r44OLS1N0oAwsD0SnqKINu98zhAKQ668e8N6jvO8gZ-A_RXyCJPA=w824-h367-no)

## How it works

ECS Deity provisions on-demand testing environments based on github branch names by creating separate ECS services on the same testing cluster. On creation, it creates a target group and listner and assigns a random unused port to a shared ALB and creates a branch-specific service based on a currently deployed task definition. On destruction, the proccess is reversed, after stopping all running tasks. Step functins are used for orchestration.

For example, when a branch named `feature/test123` is pushed for a repository named `my-project`, the following is created:

- Target group named `my-project-test123-tg` 
- ALB listner with a random port which routes to the target group
- ECS service named `my-project-test123-service`

Any necessary app-specific deployments like database migration, data loading, etc. are de-coupled. A lambda arn is configurable for such tasks.

Notifications to the user are sent via SNS. 

![ecs deity create](https://lh3.googleusercontent.com/FdRvgy-OwOnIN0ouQWsNV-JeiBURfOujH49arMUpqkCZZTBnYRcpUTuO1xwc4fvHQqCcgzDpyWIe-yUkMh55_GUGMJaotRqhjdj7QfVi7dBv4UyJOF9A4WCggIlouYDDtCxHujluaw=w600-h346-no)

## Pre-requisites

An ECS cluster using dynamic ALB, with a base service deployed by a sample definition.
A system which consumes SNS for notifying users (not provided)
A lambda function which handles deployment (can be blank)

## Install

```
npm install -g serverless
sls plugin install -n serverless-step-functions
sls plugin install -n serverless-pseudo-parameters
sls plugin install -n serverless-prune-plugin
```

## Deploy

Edit conf.yml

```
sls deploy -s dev
```

## Configure

### YAML file

look at conf.yml.example

### GitHub

1. Add API Gateways's endpoint as GitHub's webhook
2. Configure trigger events (create, delete)

![GitHub webhook config](https://lh3.googleusercontent.com/ZRyW_XGsRLFHgS3cTA8gzNQdqRMH3PBGt4G1qfCHshTYgNQR_4ZO_I5mINBfP7saKQwcJ-bfpJzbOQiPCKbrhUU8s-JPVNF8dmgcI3aR8RVCgB5aoaS2ye1RJEcI0afBWY0uzdf2Bw=w509-h164-no)

### Notification

To receive Slack notifications, create a lambda function which consumes the notification SNS and posts to Slack. Example here:
https://github.com/ijin/sns-slack

Notification is de-coupled, since including the function in this project will create unnecessary duplicates for multiple configurations.

### Deployment

The deployment lambda fits to your project's needs. If using CircleCI, you can simply call the API with `build_parameters[CIRCLE_JOB]=build` from lambda. Tasks may include databae migration, data loading, etc. A blank lambda function can be set if deployment is unnecessary.

### CircleCI

It's best to only build on pull requests if you use CircleCI for deployments to avoid double runs.

![CircleCI confi](https://lh3.googleusercontent.com/vjkdZudv3amafajN7aDLPHR1YjIRLRzlHsgxMY_p433u897T43hc4SMBi7B37Wq6GBFRexNyAtpzZogGvCdhif1YiqJq3aYyw-WNXo7svMINbdiL5iVZSeEADAt9ALM75u7Asy7qxw=w700-h144-no)


