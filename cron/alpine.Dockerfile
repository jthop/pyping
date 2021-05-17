# FROM ubuntu:latest
# MAINTAINER docker@ekito.fr
#
# RUN apt-get update && apt-get -y install cron
#
# # Copy hello-cron file to the cron.d directory
# COPY hello-cron /etc/cron.d/hello-cron
#
# # Give execution rights on the cron job
# RUN chmod 0644 /etc/cron.d/hello-cron
#
# # Apply cron job
# RUN crontab /etc/cron.d/hello-cron
#
# # Create the log file to be able to run tail
# RUN touch /var/log/cron.log
#
# # Run the command on container startup
# CMD cron && tail -f /var/log/cron.log

FROM alpine:3.6

# copy crontabs for root user
COPY hello-cron /etc/crontabs/root

# gotta have curl
RUN apk --no-cache add curl

# Create the log file to be able to run tail
RUN touch /var/log/cron.log

# start crond with log level 8 in foreground, output to stderr
CMD ["crond", "-f", "-d", "8"]