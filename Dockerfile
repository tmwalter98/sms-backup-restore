FROM public.ecr.aws/lambda/python:3.12 AS build_arm64

# Install Poetry
ENV POETRY_HOME=/opt/poetry
ENV PATH="$POETRY_HOME/bin:$PATH"
RUN curl -sSL https://install.python-poetry.org | POETRY_VERSION=2.0.0 python3 -

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

# Generate Python dependencies as requirements.txt using Poetry
WORKDIR /app
COPY poetry.lock pyproject.toml /app/

# Install Requirements
RUN target=$POETRY_CACHE_DIR poetry install --without dev,old,test --no-root


# RUN poetry export --without-hashes -f requirements.txt > requirements.txt
# RUN pip install --no-cache-dir --target "/var/task" -r requirements.txt


FROM public.ecr.aws/lambda/python:3.12

ENV VIRTUAL_ENV=/app/.venv PATH="/app/.venv/bin:$PATH"
COPY --from=build_arm64 ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# COPY --from=builder /var/task /var/task

COPY src ${LAMBDA_TASK_ROOT}

CMD ["lambda_function.handler"]