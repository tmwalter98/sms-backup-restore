FROM public.ecr.aws/lambda/python:3.11 as final
FROM public.ecr.aws/lambda/python:3.11 as build

# Install Poetry
ENV POETRY_HOME=/opt/poetry
ENV PATH="$POETRY_HOME/bin:$PATH"
RUN curl -sSL https://install.python-poetry.org | POETRY_VERSION=1.5.1 python3 -

# Generate Python dependencies as requirements.txt using Poetry
WORKDIR /app
COPY poetry.lock pyproject.toml /app/
RUN poetry export --without-hashes -f requirements.txt > /app/requirements.txt

FROM final

# Copy code
COPY src ${LAMBDA_TASK_ROOT}

# Copy requirements.txt and install
COPY --from=build /app/requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install -r requirements.txt

CMD [ "lambda_function.handler" ]