FROM python:3.11

LABEL authors="savvas"

# Fix the warning from your logs by adding the '=' sign
ENV INSTALL_PATH=/utilities-cp
RUN mkdir -p ${INSTALL_PATH}
WORKDIR ${INSTALL_PATH}

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["python", "app.py"]