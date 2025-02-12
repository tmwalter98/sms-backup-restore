ECR_URL=093896728566.dkr.ecr.us-east-1.amazonaws.com
REPO_NAME=sms-backup-restore
IMAGE_TAG=latest
AWS_REGION=us-east-1
LAMBDA_FUNCTION_NAME=sms-backup-restore
AWS_ACCESS_KEY_ID := $(shell op item get AWS --vault Development --fields AWS_ACCESS_KEY_ID --reveal)
AWS_SECRET_ACCESS_KEY := $(shell op item get AWS --vault Development --fields AWS_SECRET_ACCESS_KEY --reveal)
GH_TOKEN := $(shell gh auth token)
OP_SERVICE_ACCOUNT_TOKEN = $(shell op item get b5qzkycoj2blgnusludltk7bd4 --vault Development --fields credential --reveal)
OP_VAULT_SECRET_PREFIX=op://5wgkiijpbgxwzonxspjk6bx3re/jl66ow2gdpwczbz6vkc5jnqypq

ECR_URL=$(shell aws ecr describe-repositories --repository-names $(REPO_NAME) --query 'repositories[0].repositoryUri' --output text)

.PHONY: login-ecr build push update-lambda

login-ecr:
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(ECR_URL)

build:
	docker build --platform linux/arm64 --no-cache --load --provenance=false -t $(REPO_NAME) .
	docker tag $(REPO_NAME):latest $(ECR_URL):latest

run:
	docker run -rm -e AWS_ACCESS_KEY_ID=$(AWS_ACCESS_KEY_ID) -e AWS_SECRET_ACCESS_KEY=$(AWS_SECRET_ACCESS_KEY)  -p 9090:8080 093896728566.dkr.ecr.us-east-1.amazonaws.com/sms-backup-restore:latest

test: build run

push:
	docker push $(ECR_URL):$(IMAGE_TAG)

update-lambda:
	aws lambda update-function-code --function-name $(LAMBDA_FUNCTION_NAME) --image-uri $(ECR_URL):$(IMAGE_TAG)

act-cdk-deploy:
	act -j aws-cdk-deploy -s OP_SERVICE_ACCOUNT_TOKEN=$(OP_SERVICE_ACCOUNT_TOKEN) -s GITHUB_TOKEN=$(GH_TOKEN) --var OP_VAULT_SECRET_PREFIX=$(OP_VAULT_SECRET_PREFIX)

act-build-deploy:
	act -j build-image-deploy -s OP_SERVICE_ACCOUNT_TOKEN=$(OP_SERVICE_ACCOUNT_TOKEN) -s GITHUB_TOKEN=$(GH_TOKEN) --var OP_VAULT_SECRET_PREFIX=$(OP_VAULT_SECRET_PREFIX)

pre-commit:
	pre-commit

all: login-ecr build push update-lambda
