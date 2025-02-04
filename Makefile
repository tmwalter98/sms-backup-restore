ECR_URL=093896728566.dkr.ecr.us-east-1.amazonaws.com
REPO_NAME=sms-backup-restore
IMAGE_TAG=latest
AWS_REGION=us-east-1
LAMBDA_FUNCTION_NAME=sms-backup-restore
AWS_ACCESS_KEY_ID := $(shell op item get AWS --vault Development --fields AWS_ACCESS_KEY_ID --reveal)
AWS_SECRET_ACCESS_KEY := $(shell op item get AWS --vault Development --fields AWS_SECRET_ACCESS_KEY --reveal)
GH_TOKEN := $(shell gh auth token)

ECR_URL=$(shell aws ecr describe-repositories --repository-names $(REPO_NAME) --query 'repositories[0].repositoryUri' --output text)

.PHONY: login build push update-lambda

login:
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(ECR_URL)

build:
	docker build --platform linux/arm64 --no-cache --load --provenance=false -t $(REPO_NAME) .
	docker tag $(REPO_NAME):latest $(ECR_URL):latest

run:
	docker run -e AWS_ACCESS_KEY_ID=$(AWS_ACCESS_KEY_ID) -e AWS_SECRET_ACCESS_KEY=$(AWS_SECRET_ACCESS_KEY)  -p 9090:8080 093896728566.dkr.ecr.us-east-1.amazonaws.com/sms-backup-restore:latest

push:
	docker push $(ECR_URL):$(IMAGE_TAG)

update-lambda:
	aws lambda update-function-code --function-name $(LAMBDA_FUNCTION_NAME) --image-uri $(ECR_URL):$(IMAGE_TAG)

act:
	act -s AWS_REGION=$(AWS_REGION) -s AWS_ACCESS_KEY_ID=$(AWS_ACCESS_KEY_ID) -s AWS_SECRET_ACCESS_KEY=$(AWS_SECRET_ACCESS_KEY) -s AWS_ECR_REGISTRY_URL=$(ECR_URL) -s GITHUB_TOKEN=$(GH_TOKEN) --var LAMBDA_FUNCTION_NAME=$(LAMBDA_FUNCTION_NAME)

all: login build push update-lambda
