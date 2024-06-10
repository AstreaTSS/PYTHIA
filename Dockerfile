FROM python:3.11-alpine

RUN apk add --no-cache gcc bash musl-dev git libffi-dev npm

WORKDIR /app

COPY . /app

# allows git to work with the directory, making commands like /about better
RUN git config --global --add safe.directory /app

RUN pip install --no-cache-dir -r requirements.txt
RUN python -m prisma generate
RUN python -m prisma migrate deploy

CMD [ "python", "main.py" ]