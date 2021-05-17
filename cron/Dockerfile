FROM ubuntu:latest
MAINTAINER jh@mode14.com

#Install Cron
RUN apt-get update && apt-get -y install cron curl

# Add crontab file in the cron directory
COPY hello-cron /etc/cron.d/hello-cron

# Give execution rights on the cron job
RUN chmod 0644 /etc/cron.d/hello-cron

# Apply cron job
RUN crontab /etc/cron.d/hello-cron

# Create the log file to be able to run tail
#RUN touch /var/log/cron.log

# Run the command on container startup
CMD ["cron", "-f"]

