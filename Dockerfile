FROM public.ecr.aws/lambda/python:3.12 AS base

ARG DEV=false

FROM base AS poetry-builder

# Install Poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache \
    POETRY_HOME=/opt/poetry

ENV PATH="$POETRY_HOME/bin:$PATH"
RUN curl -sSL https://install.python-poetry.org | POETRY_VERSION=2.0.0 python3 -
RUN poetry self add poetry-plugin-export

FROM poetry-builder AS builder
# Generate Python dependencies as requirements.txt using Poetry
WORKDIR ${LAMBDA_TASK_ROOT}
COPY poetry.lock pyproject.toml ./

# Generate requirements
RUN poetry export --without-hashes --without dev,old,test,deploy -f requirements.txt > requirements.txt

FROM base

COPY --from=builder ${LAMBDA_TASK_ROOT} ${LAMBDA_TASK_ROOT}

COPY src ${LAMBDA_TASK_ROOT}
RUN pip install --no-cache-dir -r ./requirements.txt

CMD ["lambda_function.handler"]
