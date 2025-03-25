FROM postgres:alpine

RUN apk add --no-cache bash aws-cli

COPY credentials /root/.aws/credentials
COPY backup_postgresql.sh /usr/local/bin/backup_postgresql.sh
COPY backup_mysql.sh /usr/local/bin/backup_mysql.sh
COPY backup_mongo.sh /usr/local/bin/backup_mongo.sh
COPY apprise_config /etc/backup/apprise_config

RUN chmod +x /usr/local/bin/backup_postgresql.sh /usr/local/bin/backup_mysql.sh /usr/local/bin/backup_mongo.sh