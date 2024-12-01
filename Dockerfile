FROM python:3.13-alpine
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apk add gcc bash musl-dev git libffi-dev npm

WORKDIR /app

COPY . /app

# allows git to work with the directory, making commands like /about better
RUN git config --global --add safe.directory /app

RUN uv pip install --system -r requirements.txt
RUN python -m prisma generate

CMD [ "python", "main.py" ]